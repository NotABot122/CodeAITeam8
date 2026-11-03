"""Run the evaluation harness end to end.

1. Score every mock submission with validate_submission and write one event-log
   row per call (schemas/event_log.schema.json).
2. Re-score a subset N times to measure repeat stability (E02).
3. Run the adversarial set and check the expected flags / null stages (E08, E16).
4. Write a markdown report with agreement vs. the synthetic target stage (E01,
   debugging only), stage trajectories (E03), the writing-style proxy (E14),
   and tokens / latency (E09).

Usage (from the repo root):
    python -m evaluation.harness.run_eval --repeat-n 8 --repeats 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import metrics
from .bedrock_client import GRADER_MODEL
from .validator import SUBSKILLS, validate_submission

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RUBRIC = ROOT / "rubrics" / "concept3_task_rubric.json"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _tool_input(row: dict) -> dict:
    return {k: row[k] for k in ("student_id", "lesson_id", "level_id", "attempt_no",
                                "submission_text", "rubric_id")}


def _hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _event(run_id: str, row: dict, out: dict, model_id: str, temperature: float,
           error: str | None = None) -> dict:
    stages = {r["subskill"]: r["stage"] for r in out.get("results", [])}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "student_id": row["student_id"],
        "lesson_id": row["lesson_id"],
        "task_id": row["level_id"],
        "attempt_no": row["attempt_no"],
        "tool": "validate_submission",
        "input_hash": _hash(_tool_input(row)),
        "output": out,
        "stage_prompting": stages.get("prompting"),
        "stage_evaluation": stages.get("evaluation"),
        "stage_prompt_revision": stages.get("prompt_revision"),
        "model_id": out.get("model_id", model_id),
        "temperature": temperature,
        "tokens_in": out.get("tokens_in", 0),
        "tokens_out": out.get("tokens_out", 0),
        "cost_usd": None,
        "latency_ms": out.get("latency_ms", 0),
        "filter_result": out.get("filter_flags", []),
        "fallback_triggered": error is not None,
        "error": error,
    }


def _score(row: dict, rubric: dict, model_id: str, temperature: float) -> tuple[dict, str | None]:
    try:
        return validate_submission(_tool_input(row), rubric, model_id, temperature), None
    except Exception as e:  # recorded, not raised: a failed call is a fallback event (E07)
        out = {"results": [{"subskill": s, "stage": None, "confidence": 0.0,
                            "rationale": "call failed", "evidence_quotes": []} for s in SUBSKILLS],
               "model_id": model_id, "latency_ms": 0, "filter_flags": []}
        return out, f"{type(e).__name__}: {e}"[:300]


def _stage(out: dict, sub: str):
    return next((r["stage"] for r in out["results"] if r["subskill"] == sub), None)


def _pct(xs: list[int], q: float):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the evaluation harness.")
    ap.add_argument("--model", default=GRADER_MODEL)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--repeat-n", type=int, default=8, help="Submissions to re-score for E02.")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    subs = _load_jsonl(DATA / "mock_submissions.jsonl")[: args.limit]
    adv = _load_jsonl(DATA / "adversarial_set.jsonl")
    run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    RESULTS.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS / f"event_log_{run_id}.jsonl"
    log = log_path.open("w", encoding="utf-8")

    def record(row, out, err):
        log.write(json.dumps(_event(run_id, row, out, args.model, args.temperature, err),
                             ensure_ascii=False) + "\n")
        log.flush()

    # 1. main pass
    print(f"[{run_id}] scoring {len(subs)} mock submissions with {args.model}")
    scored = []
    for row in subs:
        out, err = _score(row, rubric, args.model, args.temperature)
        record(row, out, err)
        scored.append((row, out, err))
        print(f"  {row['submission_id']} target={row['target_stage']} "
              f"pred={ {s: _stage(out, s) for s in SUBSKILLS} } {err or ''}", flush=True)

    # 2. repeat stability (E02)
    repeat_rows = subs[: args.repeat_n]
    repeat_runs = {s: [[_stage(o, s) for _, o, _ in scored[: args.repeat_n]]] for s in SUBSKILLS}
    for k in range(args.repeats - 1):
        print(f"  repeat pass {k + 2}/{args.repeats}")
        outs = []
        for row in repeat_rows:
            out, err = _score(row, rubric, args.model, args.temperature)
            record(row, out, err)
            outs.append(out)
        for s in SUBSKILLS:
            repeat_runs[s].append([_stage(o, s) for o in outs])

    # 3. adversarial set (E08, E16)
    print(f"  adversarial set: {len(adv)} cases")
    adv_results = []
    for row in adv:
        out, err = _score(row, rubric, args.model, args.temperature)
        record(row, out, err)
        flags = set(out.get("filter_flags", []))
        expected = set(row["expected_flags"])
        stages = [_stage(out, s) for s in SUBSKILLS]
        nulled = all(v is None for v in stages)
        inflated = row["case_type"].startswith("injection") and any(v == 3 for v in stages if v is not None)
        adv_results.append({**row, "got_flags": sorted(flags), "stages": stages,
                            "flags_ok": expected <= flags, "nulled": nulled, "inflated": inflated})
    log.close()

    # ---- metrics ----
    agreement = {}
    for s in SUBSKILLS:
        gold = [r["target_stage"][s] for r, _, _ in scored]
        pred = [_stage(o, s) for _, o, _ in scored]
        agreement[s] = metrics.summarize(gold, pred)
    stability = {s: metrics.repeat_stability(repeat_runs[s]) for s in SUBSKILLS}

    style_bias = defaultdict(lambda: defaultdict(list))
    for r, o, _ in scored:
        for s in SUBSKILLS:
            p = _stage(o, s)
            if p is not None:
                style_bias[r["writing_style"]][s].append(p - r["target_stage"][s])

    traj = defaultdict(list)
    for r, o, _ in scored:
        traj[r["student_id"]].append((r["attempt_no"], {s: _stage(o, s) for s in SUBSKILLS}))

    lat = [o["latency_ms"] for _, o, e in scored if not e and o["latency_ms"]]
    tin = sum(o.get("tokens_in", 0) for _, o, _ in scored)
    tout = sum(o.get("tokens_out", 0) for _, o, _ in scored)
    errors = [r["submission_id"] for r, _, e in scored if e]
    parse_err = [r["submission_id"] for r, o, _ in scored if "parse_error" in o.get("filter_flags", [])]

    summary = {
        "run_id": run_id, "model_id": args.model, "temperature": args.temperature,
        "rubric_id": rubric["rubric_id"], "n_submissions": len(subs),
        "label_source": "synthetic_target (debugging only, overstates real agreement)",
        "E01_agreement_vs_synthetic_target": agreement,
        "E02_repeat_stability": {"n_items": len(repeat_rows), "repeats": args.repeats, **stability},
        "E08_E16_adversarial": [{k: a[k] for k in ("submission_id", "case_type", "expected_flags",
                                                   "got_flags", "flags_ok", "stages", "inflated")}
                                for a in adv_results],
        "E09_cost_latency": {"tokens_in_total": tin, "tokens_out_total": tout,
                             "tokens_in_per_call": round(tin / max(len(subs), 1)),
                             "tokens_out_per_call": round(tout / max(len(subs), 1)),
                             "latency_p50_ms": _pct(lat, 0.5), "latency_p95_ms": _pct(lat, 0.95)},
        "E14_style_bias_mean_pred_minus_target": {
            st: {s: round(statistics.mean(v), 2) if v else None for s, v in d.items()}
            for st, d in style_bias.items()},
        "errors": errors, "parse_errors": parse_err, "event_log": log_path.name,
    }
    (RESULTS / f"summary_{run_id}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (RESULTS / f"report_{run_id}.md").write_text(_report(summary, traj), encoding="utf-8")
    print(f"\nWrote results/summary_{run_id}.json, report_{run_id}.md, {log_path.name}")
    return 0


def _report(s: dict, traj: dict) -> str:
    L = [f"# Evaluation harness report: `{s['run_id']}`", "",
         f"- Grader model: `{s['model_id']}`, temperature {s['temperature']}",
         f"- Rubric: `{s['rubric_id']}` (draft task rubric for Concept 3 / HS-PRO-RD-18)",
         f"- Submissions scored: {s['n_submissions']} (synthetic)", "",
         "> Labels are the **synthetic target stages** the generator was asked to write to. "
         "These numbers check that the harness works; they are not the E01 result. "
         "E01 needs human-rated submissions.", "",
         "## E01 agreement vs. synthetic target", "",
         "| Sub-skill | n | Exact | Adjacent (±1) | Quadratic weighted kappa |", "|---|---|---|---|---|"]
    for sub, m in s["E01_agreement_vs_synthetic_target"].items():
        L.append(f"| {sub} | {m['n']} | {m['exact']} | {m['adjacent']} | {m['qwk']} |")
    L += ["", "Confusion matrices (rows = target stage 0-3, columns = predicted stage 0-3):", ""]
    for sub, m in s["E01_agreement_vs_synthetic_target"].items():
        L.append(f"- **{sub}**: `{m['confusion']}`")
    st = s["E02_repeat_stability"]
    L += ["", "## E02 repeat-scoring stability", "",
          f"{st['n_items']} submissions scored {st['repeats']} times. Share with an identical stage every time:", ""]
    L += [f"- {sub}: {st[sub]}" for sub in ("prompting", "evaluation", "prompt_revision")]
    L += ["", "## E03 stage trajectories (predicted, per attempt)", "",
          "| Student | Attempts → (prompting, evaluation, prompt_revision) |", "|---|---|"]
    for sid, att in sorted(traj.items()):
        seq = " → ".join(f"({a[1]['prompting']},{a[1]['evaluation']},{a[1]['prompt_revision']})"
                         for a in sorted(att, key=lambda x: x[0]))
        L.append(f"| {sid} | {seq} |")
    L += ["", "## E08 / E16 adversarial and abnormal input", "",
          "| ID | Case | Expected flags | Got flags | Flags OK | Stages | Inflated by injection |",
          "|---|---|---|---|---|---|---|"]
    for a in s["E08_E16_adversarial"]:
        L.append(f"| {a['submission_id']} | {a['case_type']} | {a['expected_flags']} | {a['got_flags']} | "
                 f"{a['flags_ok']} | {a['stages']} | {a['inflated']} |")
    c = s["E09_cost_latency"]
    L += ["", "## E09 tokens and latency (main pass)", "",
          f"- Tokens per call: {c['tokens_in_per_call']} in / {c['tokens_out_per_call']} out",
          f"- Latency: P50 {c['latency_p50_ms']} ms, P95 {c['latency_p95_ms']} ms",
          "- Cost: fill `PRICES_PER_MTOK` in `harness/bedrock_client.py` from the Bedrock price list.",
          "", "## E14 writing-style proxy (mean predicted minus target stage)", "",
          "| Style | prompting | evaluation | prompt_revision |", "|---|---|---|---|"]
    for style, d in s["E14_style_bias_mean_pred_minus_target"].items():
        L.append(f"| {style} | {d.get('prompting')} | {d.get('evaluation')} | {d.get('prompt_revision')} |")
    L += ["", f"Errors: {s['errors'] or 'none'}. Parse errors: {s['parse_errors'] or 'none'}.",
          f"Event log: `results/{s['event_log']}`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
