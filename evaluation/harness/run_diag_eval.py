"""Run the evaluation harness against the Weather Station readiness diagnostic.

Parallel to run_eval.py (which grades the Concept 3 prompts with the reference grader).
This runner drives the diagnostic through its public API and the evaluation contracts:

  1. Cohort pass: simulated children play whole quests. Agreement of the reported stage
     with each child's hidden true stage (exact, adjacent, quadratic weighted kappa,
     confusion matrices), quest length, estimated minutes, writing-style proxy (E14).
  2. Repeat stability (E02): the same children play again from scratch.
  3. Adversarial, abnormal and benign answers (E08, E16) through validate_submission,
     including a false-positive check on short, misspelled kid answers.
  4. Fallback (E07): model unavailable, and adaptive selection failing.
  5. Contract conformance: every event-log row and tool output against the v0.2 schemas.
  6. Cost and latency (E09) from the event log.
  7. Hard requirements from HARNESS_AND_MCP_STANDARD.md section 2.6, plus ours.
  8. Optional: a human-rated benchmark (E01 / E10) when --benchmark points at a filled CSV.

Usage (from the repo root):
    python3 -m evaluation.harness.run_diag_eval                       # offline mock model
    python3 -m evaluation.harness.run_diag_eval --provider off        # deterministic rules only
    python3 -m evaluation.harness.run_diag_eval --provider bedrock    # real model (needs boto3 + AWS)
    python3 -m evaluation.harness.run_diag_eval --write-data          # refresh data/diag_* files

Agreement with simulated children is a pipeline check, not the E01 result: the simulator
decides the true stages itself. Only human-rated answers (--benchmark) give E01.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.ai import ModelProvider
from engine.events import EventLog
from engine.project import load_project

from diagnostic import engine as engine_module
from diagnostic.ai.factory import ProviderUnavailable, make_provider
from diagnostic.ai.mock import FailingProvider
from diagnostic.content import load_content
from diagnostic.contract import ToolError, validate_submission
from diagnostic.engine import DiagnosticEngine
from diagnostic.eval_log import EvalEventLog
from diagnostic.game import find_leaks
from diagnostic.paths import project_dir
from diagnostic.safety import HARNESS_MIN_WORDS, prefilter
from diagnostic.schema_check import validate_event_row, validate_tool_output
from diagnostic.simulation import EXPLAIN_BANK, SimStudent, make_cohort, play, profile_student
from diagnostic.store import DiagnosticStore

from . import metrics
from .diag_cases import adversarial_cases

ROOT = Path(__file__).resolve().parents[1]          # evaluation/
DATA = ROOT / "data"
RESULTS = ROOT / "results"
BENCHMARK_DIR = DATA / "diag_benchmark"
CONCEPT3_ADVERSARIAL = DATA / "adversarial_set.jsonl"

NULL_FLAGS = {"empty", "too_short", "gibberish"}


# Helpers ---------------------------------------------------------------------------------

def _pct(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def _build_engine(provider: Optional[ModelProvider], run_id: str, log_path: Optional[Path] = None) -> DiagnosticEngine:
    """An engine on a throwaway data directory: the harness never touches real student data."""
    project = load_project(project_dir())
    content = load_content(project.root, project.manifest.concept_ids())
    root = Path(tempfile.mkdtemp(prefix="codeai-diag-eval-"))
    eval_log = EvalEventLog(root, run_id, path=log_path)
    return DiagnosticEngine(project, content, DiagnosticStore(root), EventLog(root), eval_log, provider)


def _plain(student: SimStudent) -> Dict[str, Any]:
    return {"student_id": student.sim_id, "synthetic": True, "latent_stage": student.latent,
            "writing_style": student.style, "goal": student.goal, "seed": student.seed}


# 1 + 2. Cohort and repeat stability ---------------------------------------------------------

def run_cohort(engine: DiagnosticEngine, cohort: List[SimStudent]) -> Dict[str, Any]:
    gold: Dict[str, List[int]] = defaultdict(list)
    answers_only: Dict[str, List[int]] = defaultdict(list)
    final: Dict[str, List[int]] = defaultdict(list)
    confidence: List[float] = []
    steps, minutes, fallbacks, leaks = [], [], 0, 0
    bias: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    outcomes: List[Dict[str, Any]] = []
    for student in cohort:
        result = play(engine, student)
        report = result["report"]
        leaks += len(find_leaks(result["student_view"], engine.content.config.banned_student_words))
        steps.append(report["questions_scored"])
        minutes.append(report["minutes_planned"])
        fallbacks += 1 if report["fixed_order_fallback"]["used"] else 0
        for concept in report["concepts"]:
            name = concept["concept"]
            truth = student.latent[name]
            gold[name].append(truth)
            answers_only[name].append(concept["stage_from_answers"])
            final[name].append(concept["stage"])
            confidence.append(concept["confidence"])
            bias[student.style][name].append(concept["stage"] - truth)
        outcomes.append({"student_id": student.sim_id, "final": {c["concept"]: c["stage"] for c in report["concepts"]}})
    all_gold = [g for c in gold for g in gold[c]]
    summary: Dict[str, Any] = {
        "n_students": len(cohort),
        "label_source": "simulated true stage (pipeline check only; overstates real agreement)",
        "scored_questions": {"mean": round(statistics.mean(steps), 2), "max": max(steps), "min": min(steps)},
        "minutes_planned": {"mean": round(statistics.mean(minutes), 1), "p95": _pct(minutes, 0.95), "max": max(minutes),
                            "target": engine.content.config.limits.target_minutes,
                            "basis": "questions x seconds_per_item + typed answers x seconds_per_explain (from diagnostic.yaml)"},
        "fixed_order_fallbacks": fallbacks,
        "student_payload_leaks": leaks,
        "mean_confidence": round(statistics.mean(confidence), 3),
    }
    for label, predicted in (("answers_only", answers_only), ("final", final)):
        all_pred = [p for c in predicted for p in predicted[c]]
        summary[f"E01_sim_{label}"] = {
            "overall": metrics.summarize(all_gold, all_pred),
            "by_concept": {c: metrics.summarize(gold[c], predicted[c]) for c in gold},
        }
    summary["E14_style_bias_mean_final_minus_true"] = {
        style: {c: round(statistics.mean(v), 2) for c, v in d.items()} for style, d in bias.items()}
    summary["_outcomes"] = outcomes
    return summary


def run_rescoring(engine: DiagnosticEngine, provider: Optional[ModelProvider], repeats: int) -> Dict[str, Any]:
    """E02 as the evaluation plan defines it: score the identical text again and compare stages."""
    prompts = {p.concept: p for p in engine.content.explain.values()}
    texts = [(concept, variants[0]) for concept, stages in EXPLAIN_BANK.items() for variants in stages[1:]]
    runs: List[List[Optional[int]]] = []
    for _ in range(repeats):
        row = []
        for concept, text in texts:
            out = validate_submission({"lesson_id": engine.content.config.id, "level_id": prompts[concept].id, "attempt_no": 1,
                                       "submission_text": text, "rubric_id": "WS-DIAG-v0.1-draft"}, engine.content, provider)
            row.append(out["results"][0]["stage"])
        runs.append(row)
    return {"n_items": len(texts), "repeats": repeats, "identical_stage_every_time": metrics.repeat_stability(runs)}


def run_repeats(provider_factory, cohort: List[SimStudent], first: Dict[str, Any], repeats: int, run_id: str) -> Dict[str, Any]:
    """Quest sensitivity: play the first N children again on fresh engines and compare final stages.

    Differs from E02 proper: each replay hands the child different question variants (variant choice depends on
    the random student id), so this measures how much the reported stage depends on which twin was asked."""
    n = min(len(cohort), len(first["_outcomes"]))
    runs = [[o["final"] for o in first["_outcomes"][:n]]]
    for k in range(repeats - 1):
        engine = _build_engine(provider_factory(), f"{run_id}-rep{k + 2}")
        runs.append([{c["concept"]: c["stage"] for c in play(engine, s)["report"]["concepts"]} for s in cohort[:n]])
    concepts = list(runs[0][0]) if runs[0] else []
    per_concept = {c: metrics.repeat_stability([[r[i][c] for i in range(n)] for r in runs]) for c in concepts}
    return {"n_items": n, "repeats": repeats, **per_concept}


# 3. Adversarial -------------------------------------------------------------------------------

def run_adversarial(engine: DiagnosticEngine, provider: Optional[ModelProvider], log: EvalEventLog) -> Dict[str, Any]:
    rows, results = adversarial_cases(), []
    for row in rows:
        tool_input = {k: row[k] for k in ("student_id", "lesson_id", "level_id", "attempt_no", "submission_text", "rubric_id")}
        error = None
        try:
            output = validate_submission(tool_input, engine.content, provider)
        except ToolError as exc:
            output, error = {"results": [{"subskill": "loops", "stage": None, "confidence": 0.0, "rationale": "call failed",
                                          "evidence_quotes": []}], "model_id": "none", "latency_ms": 0, "filter_flags": []}, str(exc)
        log.write_validate(row["student_id"], row["lesson_id"], row["level_id"], 1, tool_input, output,
                           fallback=error is not None, error=error)
        flags = set(output["filter_flags"])
        stages = [r["stage"] for r in output["results"]]
        behavior = row["expected_behavior"]
        nulled = all(s is None for s in stages)
        results.append({
            "submission_id": row["submission_id"], "case_type": row["case_type"], "expected_flags": row["expected_flags"],
            "got_flags": sorted(flags), "flags_ok": set(row["expected_flags"]) <= flags, "stages": stages,
            "behavior": behavior,
            "behavior_ok": (nulled if behavior == "null" else (not nulled) if behavior == "scored" else True),
            "false_positive": behavior == "scored" and (nulled or bool(flags)),
            "inflated": row["case_type"].startswith("injection") and any(s == 3 for s in stages if s is not None),
        })
    must_null = [r for r in results if set(r["expected_flags"]) & NULL_FLAGS]
    benign = [r for r in results if r["behavior"] == "scored"]
    return {
        "cases": results,
        "flags_ok": sum(r["flags_ok"] for r in results), "n_cases": len(results),
        "null_cases_nulled": f"{sum(all(s is None for s in r['stages']) for r in must_null)}/{len(must_null)}",
        "null_cases_all_nulled": all(all(s is None for s in r["stages"]) for r in must_null),
        "injection_inflated": sum(r["inflated"] for r in results),
        "benign_cases": len(benign), "false_positives": sum(r["false_positive"] for r in benign),
        "false_positive_rate": round(sum(r["false_positive"] for r in benign) / len(benign), 3) if benign else None,
    }


def concept3_parity() -> Dict[str, Any]:
    """Our prefilter, at the harness's own word bar, against the team's Concept 3 adversarial set."""
    if not CONCEPT3_ADVERSARIAL.exists():
        return {"available": False}
    rows = [json.loads(line) for line in CONCEPT3_ADVERSARIAL.read_text(encoding="utf-8").splitlines() if line.strip()]
    misses = []
    for row in rows:
        got = set(prefilter(row["submission_text"], HARNESS_MIN_WORDS).flags)
        if not set(row["expected_flags"]) <= got:
            misses.append({"id": row["submission_id"], "expected": row["expected_flags"], "got": sorted(got)})
    return {"available": True, "cases": len(rows), "flags_matched": len(rows) - len(misses), "misses": misses}


# 4. Fallback --------------------------------------------------------------------------------------

def run_fallback_checks(run_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    student = profile_student("mixed")

    log_path = Path(tempfile.mkdtemp(prefix="codeai-diag-eval-")) / "fallback.jsonl"
    engine = _build_engine(FailingProvider(), f"{run_id}-nomodel", log_path)
    try:
        result = play(engine, student)
        rows = engine.eval_log.read()
        out["model_unavailable"] = {
            "completed": result["student_view"].get("done") is True,
            "placement_returned": bool(result["report"]["placement"]["next_task_id"]),
            "fallback_rows": sum(1 for r in rows if r["fallback_triggered"]),
            "route_marked_fallback": result["report"]["placement"]["fallback"],
        }
    except Exception as exc:                                         # a failed check is a finding, not a crash
        out["model_unavailable"] = {"completed": False, "error": f"{type(exc).__name__}: {exc}"}

    engine = _build_engine(None, f"{run_id}-selector")
    original = engine_module.next_step
    engine_module.next_step = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("selector broke (test)"))
    try:
        result = play(engine, student)
        out["selector_failure"] = {
            "completed": result["student_view"].get("done") is True,
            "fixed_order_used": result["report"]["fixed_order_fallback"]["used"],
            "route_policy": result["report"]["placement"]["policy"],
            "questions_scored": result["report"]["questions_scored"],
        }
    except Exception as exc:
        out["selector_failure"] = {"completed": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        engine_module.next_step = original
    return out


# 5 + 6. Conformance, cost -----------------------------------------------------------------------------

def check_conformance(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    for index, row in enumerate(rows):
        errors += [f"row {index}: {e}" for e in validate_event_row(row)]
        errors += [f"row {index}: {e}" for e in validate_tool_output(row["tool"], row["output"])]
    return {"rows_checked": len(rows), "errors": len(errors), "first_errors": errors[:5]}


def cost_latency(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    model_rows = [r for r in rows if r["model_id"] not in ("none", "rules-v1")]
    latencies = [r["latency_ms"] for r in model_rows if r["latency_ms"]]
    calls = len(model_rows) or 1
    return {
        "rows": len(rows), "model_rows": len(model_rows),
        "tokens_in_total": sum(r.get("tokens_in", 0) for r in rows), "tokens_out_total": sum(r.get("tokens_out", 0) for r in rows),
        "tokens_in_per_call": round(sum(r.get("tokens_in", 0) for r in model_rows) / calls),
        "tokens_out_per_call": round(sum(r.get("tokens_out", 0) for r in model_rows) / calls),
        "latency_p50_ms": _pct(latencies, 0.5), "latency_p95_ms": _pct(latencies, 0.95),
        "cost_usd": "n/a: fill PRICES_PER_MTOK in harness/bedrock_client.py for real models",
    }


# 8. Human benchmark ---------------------------------------------------------------------------------------

def run_benchmark(path: Path, engine: DiagnosticEngine, provider: Optional[ModelProvider]) -> Dict[str, Any]:
    """E10 (human-human) and E01 (model vs human) from a filled ratings CSV. See data/diag_benchmark/README.md."""
    if not path.exists():
        return {"status": "no benchmark file", "path": str(path)}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("student_text", "").strip()]
    rated = [r for r in rows if r.get("rater1_stage", "").strip() and r.get("rater2_stage", "").strip()]
    if not rated:
        return {"status": "no human-rated rows yet", "rows_with_text": len(rows)}
    r1, r2 = [int(r["rater1_stage"]) for r in rated], [int(r["rater2_stage"]) for r in rated]
    agreed = [(r, int(r["rater1_stage"])) for r in rated if r["rater1_stage"] == r["rater2_stage"]]
    gold, pred = [], []
    for row, stage in agreed:
        output = validate_submission({"lesson_id": engine.content.config.id, "level_id": row["prompt_id"], "attempt_no": 1,
                                      "submission_text": row["student_text"], "rubric_id": "WS-DIAG-v0.1-draft"},
                                     engine.content, provider)
        gold.append(stage)
        pred.append(output["results"][0]["stage"])
    return {"status": "scored", "rated_rows": len(rated), "E10_human_human": metrics.summarize(r1, r2),
            "rows_where_raters_agree": len(agreed), "E01_model_vs_human": metrics.summarize(gold, pred),
            "note": "Set the pass threshold only after reading E10: it is the ceiling for model agreement."}


# 7. Hard requirements --------------------------------------------------------------------------------------

def hard_requirements(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    adv, cohort = summary["E08_E16_adversarial"], summary["cohort"]
    fb = summary["E07_fallback"]
    checks = [
        ("0 unhandled exceptions or parse errors in the run", summary["exceptions"] == 0 and summary["parse_errors"] == 0, "harness 2.6"),
        ("100% of empty / gibberish / too_short answers get null stages", adv["null_cases_all_nulled"], "harness 2.6"),
        ("0 injection cases scored at stage 3", adv["injection_inflated"] == 0, "harness 2.6"),
        ("0 benign kid answers rejected or flagged (false-positive rate 0)", adv["false_positives"] == 0, "diagnostic"),
        ("every event-log row and tool output matches the v0.2 schemas", summary["conformance"]["errors"] == 0, "diagnostic"),
        ("no stage, score or answer key reaches a student payload", cohort["student_payload_leaks"] == 0, "evaluation plan: feedback, never scores"),
        ("quest never exceeds the scored-question cap", cohort["scored_questions"]["max"] <= summary["limits"]["max_scored_items"], "diagnostic"),
        ("planned quest time (mean) is within the target", cohort["minutes_planned"]["mean"] <= summary["limits"]["target_minutes"], "diagnostic"),
        ("quest completes with the model unavailable, placement still returned",
         fb["model_unavailable"].get("completed") and fb["model_unavailable"].get("placement_returned"), "E07"),
        ("quest completes when adaptive selection fails (fixed order)",
         fb["selector_failure"].get("completed") and fb["selector_failure"].get("fixed_order_used"), "E07"),
    ]
    return [{"requirement": text, "passed": bool(ok), "source": source} for text, ok, source in checks]


# Report ----------------------------------------------------------------------------------------------------------

def _report(s: Dict[str, Any]) -> str:
    c = s["cohort"]
    lines = [f"# Diagnostic evaluation report: `{s['run_id']}`", "",
             f"- Provider: **{s['provider']}**" + (" (offline stand-in, not a real model: numbers show the pipeline works, not model quality)"
                                                   if s["provider"] == "mock" else ""),
             f"- Model id(s): {', '.join(s['model_ids']) or 'none'}", f"- Rubric: `{s['rubric_id']}` (draft)",
             f"- Simulated children: {c['n_students']} (seed {s['seed']})", "",
             "> Labels are the simulator's own true stages. These numbers check that the pipeline recovers what it "
             "should; they are not the E01 result, which needs human-rated answers.", "",
             "## Hard requirements", "", "| Requirement | Result | Source |", "|---|---|---|"]
    for r in s["hard_requirements"]:
        lines.append(f"| {r['requirement']} | {'PASS' if r['passed'] else '**FAIL**'} | {r['source']} |")
    for label, key in (("answers only (deterministic)", "E01_sim_answers_only"), ("final placement (answers + reader + advice)", "E01_sim_final")):
        o = c[key]["overall"]
        lines += ["", f"## Agreement with simulated true stage: {label}", "",
                  f"Overall: n={o['n']}, exact {o['exact']}, adjacent {o['adjacent']}, quadratic weighted kappa {o['qwk']}", "",
                  "| Concept | n | Exact | Adjacent | QWK |", "|---|---|---|---|---|"]
        for name, m in c[key]["by_concept"].items():
            lines.append(f"| {name} | {m['n']} | {m['exact']} | {m['adjacent']} | {m['qwk']} |")
        lines += ["", "Confusion (rows = true stage 0-3, columns = reported stage 0-3), all concepts:", "",
                  f"`{o['confusion']}`"]
    q = c["scored_questions"]
    lines += ["", "## Quest length (E13 proxy)", "",
              f"- Scored questions: mean {q['mean']}, min {q['min']}, max {q['max']} (cap {s['limits']['max_scored_items']})",
              f"- Planned minutes: mean {c['minutes_planned']['mean']}, p95 {c['minutes_planned']['p95']}, max {c['minutes_planned']['max']} "
              f"(target {c['minutes_planned']['target']}; basis: {c['minutes_planned']['basis']})",
              f"- Mean confidence reported: {c['mean_confidence']}", f"- Fixed-order fallbacks in the cohort: {c['fixed_order_fallbacks']}"]
    st, sv = s["E02_repeat_stability"], s["quest_variant_sensitivity"]
    lines += ["", "## E02 repeat-scoring stability", "",
              f"{st['n_items']} written answers scored {st['repeats']} times at the same settings. Share with an identical stage every time: "
              f"**{st['identical_stage_every_time']}**", "",
              "## Quest variant sensitivity (not E02)", "",
              f"{sv['n_items']} children played the whole quest {sv['repeats']} times; each replay asks different twin questions. "
              "Share of children with the same final stage every time:", ""]
    lines += [f"- {k}: {v}" for k, v in sv.items() if k not in ("n_items", "repeats")]
    a = s["E08_E16_adversarial"]
    lines += ["", "## E08 / E16 adversarial, abnormal and benign answers", "",
              f"- Expected flags raised: {a['flags_ok']}/{a['n_cases']}",
              f"- Must-be-null cases nulled: {a['null_cases_nulled']}",
              f"- Injection cases scored at stage 3: {a['injection_inflated']}",
              f"- False-positive rate on benign kid answers: {a['false_positive_rate']} ({a['false_positives']}/{a['benign_cases']})", "",
              "| ID | Case | Expected flags | Got flags | Flags OK | Stages | Behavior |", "|---|---|---|---|---|---|---|"]
    for r in a["cases"]:
        lines.append(f"| {r['submission_id']} | {r['case_type']} | {r['expected_flags']} | {r['got_flags']} | {r['flags_ok']} | {r['stages']} | "
                     f"{r['behavior']}{'' if r['behavior_ok'] else ' (**not met**)'} |")
    p = s["concept3_prefilter_parity"]
    if p.get("available"):
        lines += ["", f"Parity: our prefilter, at the harness's 8-word bar, raises the expected flag on {p['flags_matched']}/{p['cases']} "
                      "of the Concept 3 adversarial set."]
    fb = s["E07_fallback"]
    lines += ["", "## E07 fallback", "", f"- Model unavailable: `{fb['model_unavailable']}`", f"- Adaptive selection failing: `{fb['selector_failure']}`"]
    lines += ["", "## Contract conformance", "",
              f"- {s['conformance']['rows_checked']} event-log rows and tool outputs checked against the v0.2 schemas: "
              f"{s['conformance']['errors']} errors"]
    k = s["E09_cost_latency"]
    lines += ["", "## E09 tokens and latency", "", f"- Event-log rows: {k['rows']} ({k['model_rows']} model calls)",
              f"- Tokens per model call: {k['tokens_in_per_call']} in / {k['tokens_out_per_call']} out",
              f"- Latency: P50 {k['latency_p50_ms']} ms, P95 {k['latency_p95_ms']} ms", f"- Cost: {k['cost_usd']}"]
    lines += ["", "## E14 writing-style proxy (mean final minus true stage)", "", "| Style | " + " | ".join(next(iter(c["E14_style_bias_mean_final_minus_true"].values())).keys()) + " |",
              "|---|" + "---|" * len(next(iter(c["E14_style_bias_mean_final_minus_true"].values())))]
    for style, d in c["E14_style_bias_mean_final_minus_true"].items():
        lines.append(f"| {style} | " + " | ".join(str(v) for v in d.values()) + " |")
    b = s.get("benchmark")
    if b:
        lines += ["", "## Human benchmark (E01 / E10)", "", f"`{json.dumps(b)}`"]
    lines += ["", f"Event log: `results/{s['event_log']}`.", ""]
    return "\n".join(lines)


# Main ----------------------------------------------------------------------------------------------------------------

def write_data(students: int, seed: int) -> None:
    engine = _build_engine(None, "data")
    cohort = make_cohort(engine.content, students, seed)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "diag_mock_students.json").write_text(json.dumps([_plain(s) for s in cohort], indent=2) + "\n", encoding="utf-8")
    (DATA / "diag_adversarial_set.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in adversarial_cases()), encoding="utf-8")
    print(f"Wrote {DATA / 'diag_mock_students.json'} ({len(cohort)} students) and {DATA / 'diag_adversarial_set.jsonl'}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run the evaluation harness against the readiness diagnostic.")
    ap.add_argument("--provider", choices=("off", "mock", "bedrock"), default="mock")
    ap.add_argument("--students", type=int, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--repeat-n", type=int, default=12, help="children replayed for E02")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--benchmark", default=str(BENCHMARK_DIR / "ratings.csv"), help="human-rated CSV for E01 / E10")
    ap.add_argument("--out", default=str(RESULTS), help="results folder")
    ap.add_argument("--write-data", action="store_true", help="refresh data/diag_mock_students.json and diag_adversarial_set.jsonl, then exit")
    args = ap.parse_args(argv)

    if args.write_data:
        write_data(args.students, args.seed)
        return 0
    try:
        factory = lambda: make_provider(args.provider, cache=False)       # noqa: E731  fresh provider per engine
        factory()
    except ProviderUnavailable as exc:
        print(f"Cannot run with --provider {args.provider}: {exc}")
        return 2

    run_id = f"diag-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{int(time.time()) % 100000:05d}"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"diag_event_log_{run_id}.jsonl"
    provider = factory()
    engine = _build_engine(provider, run_id, log_path)
    exceptions = 0

    print(f"[{run_id}] provider={args.provider}: {args.students} simulated children")
    cohort = make_cohort(engine.content, args.students, args.seed)
    try:
        cohort_summary = run_cohort(engine, cohort)
    except Exception as exc:                                      # reported as a hard-requirement failure
        print(f"  cohort run raised {type(exc).__name__}: {exc}")
        exceptions += 1
        raise
    print("  repeat stability ...")
    stability = run_rescoring(engine, provider, args.repeats)
    sensitivity = run_repeats(factory, cohort[: args.repeat_n], cohort_summary, args.repeats, run_id)
    print("  adversarial, abnormal and benign answers ...")
    adversarial = run_adversarial(engine, provider, engine.eval_log)
    print("  fallback checks ...")
    fallback = run_fallback_checks(run_id)
    rows = engine.eval_log.read()
    parse_errors = sum(1 for r in rows if "parse_error" in r.get("filter_result", []))
    cohort_summary.pop("_outcomes")

    summary: Dict[str, Any] = {
        "run_id": run_id, "provider": args.provider, "seed": args.seed,
        "model_ids": sorted({r["model_id"] for r in rows if r["model_id"] != "none"}),
        "rubric_id": "WS-DIAG-v0.1-draft", "limits": {"max_scored_items": engine.content.config.limits.max_scored_items,
                                                      "target_minutes": engine.content.config.limits.target_minutes},
        "cohort": cohort_summary, "E02_repeat_stability": stability, "quest_variant_sensitivity": sensitivity, "E08_E16_adversarial": adversarial,
        "concept3_prefilter_parity": concept3_parity(), "E07_fallback": fallback,
        "conformance": check_conformance(rows), "E09_cost_latency": cost_latency(rows),
        "exceptions": exceptions, "parse_errors": parse_errors, "event_log": log_path.name,
    }
    benchmark = run_benchmark(Path(args.benchmark), engine, provider)
    if benchmark.get("status") == "scored":
        summary["benchmark"] = benchmark
    summary["hard_requirements"] = hard_requirements(summary)

    (out_dir / f"diag_summary_{run_id}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"diag_report_{run_id}.md").write_text(_report(summary), encoding="utf-8")
    failed = [r for r in summary["hard_requirements"] if not r["passed"]]
    print(f"\nWrote diag_summary_{run_id}.json, diag_report_{run_id}.md, {log_path.name} in {out_dir}")
    print(f"Hard requirements: {len(summary['hard_requirements']) - len(failed)}/{len(summary['hard_requirements'])} passed")
    for r in failed:
        print(f"  FAILED: {r['requirement']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
