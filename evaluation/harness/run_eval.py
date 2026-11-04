"""Run the evaluation harness end to end (contract v0.2).

1. Score submissions with validate_submission; write one event-log row per call
   (schemas/event_log.schema.json).
2. Re-score the first N submissions K times for repeat stability (E02).
3. Run the adversarial set and check flags, scorability, and that no stage is
   raised by injected text (E08, E16).
4. Write summary JSON + markdown report: agreement vs. synthetic target (E01,
   debugging only), confidence calibration (E11), trajectories (E03), writing-
   style proxy (E14), tokens / latency / cost (E09).

Usage (from the repo root):
    python -m evaluation.harness.run_eval --repeat-n 20 --repeats 3
    python -m evaluation.harness.run_eval --model <other> --sample 60 --repeats 1 --skip-adversarial --tag drift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import metrics
from .bedrock_client import GRADER_MODEL
from .validator import CONTRACT_VERSION, normalize_input, subskills_of, validate_submission

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RUBRIC = ROOT / "rubrics" / "concept3_task_rubric.json"
INPUT_KEYS = ("student_id", "lesson_id", "task_id", "attempt_no", "submission_text", "rubric_id")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def tool_input(row: dict) -> dict:
    row = normalize_input(row)
    return {k: row[k] for k in INPUT_KEYS}


def input_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(tool_input(row), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def stage_of(out: dict, sub: str):
    return next((r["stage"] for r in out["results"] if r["subskill"] == sub), None)


def conf_of(out: dict, sub: str):
    return next((r["confidence"] for r in out["results"] if r["subskill"] == sub), None)


def _event(run_id, row, out, temperature, subs, error=None) -> dict:
    stages = {s: stage_of(out, s) for s in subs}
    ev = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contract_version": out.get("contract_version", CONTRACT_VERSION),
        "run_id": run_id,
        "student_id": row["student_id"],
        "lesson_id": row["lesson_id"],
        "task_id": normalize_input(row)["task_id"],
        "rubric_id": row["rubric_id"],
        "attempt_no": row["attempt_no"],
        "tool": "validate_submission",
        "input_hash": input_hash(row),
        "output": out,
        "stages": stages,
        "needs_review": out.get("needs_review", False),
        "model_id": out["model_id"],
        "temperature": temperature,
        "tokens_in": out.get("tokens_in", 0),
        "tokens_out": out.get("tokens_out", 0),
        "cost_usd": out.get("cost_usd"),
        "latency_ms": out.get("latency_ms", 0),
        "filter_result": out.get("filter_flags", []),
        "fallback_triggered": error is not None,
        "error": error,
    }
    for s in subs:  # deprecated flat columns, kept for v0.1 readers
        ev[f"stage_{s}"] = stages[s]
    return ev


def score(row, rubric, model_id, temperature):
    try:
        return validate_submission(tool_input(row), rubric, model_id, temperature), None
    except Exception as e:  # recorded, not raised: a failed call is a fallback event (E07)
        out = {"contract_version": CONTRACT_VERSION, "rubric_id": rubric["rubric_id"],
               "results": [{"subskill": s, "stage": None, "confidence": 0.0, "rationale": "call failed",
                            "evidence_quotes": []} for s in subskills_of(rubric)],
               "scorable": False, "needs_review": False, "filter_flags": [], "model_id": model_id,
               "latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": None}
        return out, f"{type(e).__name__}: {e}"[:300]


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def calibration(pairs, bins=(0.0, 0.5, 0.7, 0.8, 0.9, 1.01)):
    """pairs = [(confidence, correct_bool)]. Returns per-bin accuracy and ECE."""
    rows, ece, n = [], 0.0, len(pairs)
    for lo, hi in zip(bins, bins[1:]):
        b = [(c, ok) for c, ok in pairs if lo <= c < hi]
        if not b:
            continue
        conf = statistics.mean(c for c, _ in b)
        acc = sum(ok for _, ok in b) / len(b)
        ece += len(b) / n * abs(conf - acc)
        rows.append({"bin": f"[{lo:.1f}, {min(hi, 1.0):.1f}]", "n": len(b),
                     "mean_confidence": round(conf, 3), "exact_agreement": round(acc, 3)})
    return {"bins": rows, "ece": round(ece, 3) if n else None, "n": n}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the evaluation harness.")
    ap.add_argument("--model", default=GRADER_MODEL)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--submissions", default=str(DATA / "mock_submissions.jsonl"))
    ap.add_argument("--sample", type=int, default=None, help="Score a fixed random sample of this size (seed 8).")
    ap.add_argument("--repeat-n", type=int, default=20, help="Submissions to re-score for E02.")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--skip-adversarial", action="store_true")
    ap.add_argument("--tag", default="main")
    args = ap.parse_args(argv)

    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    subs_names = subskills_of(rubric)
    subs = load_jsonl(Path(args.submissions))
    if args.sample:
        subs = sorted(random.Random(8).sample(subs, min(args.sample, len(subs))),
                      key=lambda r: r["submission_id"])
    adv = [] if args.skip_adversarial else load_jsonl(DATA / "adversarial_set.jsonl")
    run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{args.tag}-{uuid.uuid4().hex[:4]}"
    RESULTS.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS / f"event_log_{run_id}.jsonl"
    log = log_path.open("w", encoding="utf-8")

    def record(row, out, err):
        log.write(json.dumps(_event(run_id, row, out, args.temperature, subs_names, err), ensure_ascii=False) + "\n")
        log.flush()

    print(f"[{run_id}] scoring {len(subs)} submissions with {args.model} t={args.temperature}")
    scored = []
    for row in subs:
        out, err = score(row, rubric, args.model, args.temperature)
        record(row, out, err)
        scored.append((row, out, err))
        print(f"  {row['submission_id']} target={row.get('target_stage')} "
              f"pred={ {s: stage_of(out, s) for s in subs_names} } {err or ''}", flush=True)

    repeat_rows = subs[: args.repeat_n] if args.repeats > 1 else []
    repeat_runs = {s: [[stage_of(o, s) for _, o, _ in scored[: len(repeat_rows)]]] for s in subs_names}
    for k in range(args.repeats - 1):
        print(f"  repeat pass {k + 2}/{args.repeats}", flush=True)
        outs = []
        for row in repeat_rows:
            out, err = score(row, rubric, args.model, args.temperature)
            record(row, out, err)
            outs.append(out)
        for s in subs_names:
            repeat_runs[s].append([stage_of(o, s) for o in outs])

    adv_results = []
    if adv:
        print(f"  adversarial set: {len(adv)} cases", flush=True)
    for row in adv:
        out, err = score(row, rubric, args.model, args.temperature)
        record(row, out, err)
        flags = set(out.get("filter_flags", []))
        stages = [stage_of(out, s) for s in subs_names]
        injected = row["case_type"].startswith("injection")
        adv_results.append({
            "submission_id": row["submission_id"], "case_type": row["case_type"],
            "expected_flags": row["expected_flags"], "got_flags": sorted(flags),
            "flags_ok": set(row["expected_flags"]) <= flags,
            "expected_scorable": row.get("expected_scorable"), "scorable": out.get("scorable"),
            "scorable_ok": row.get("expected_scorable") is None or row["expected_scorable"] == out.get("scorable"),
            "needs_review": out.get("needs_review"), "stages": stages,
            "inflated": injected and any(v is not None and v >= 2 for v in stages),
        })
    log.close()

    labeled = [(r, o) for r, o, _ in scored if r.get("target_stage")]
    agreement, calib_pairs = {}, []
    for s in subs_names:
        gold = [r["target_stage"][s] for r, _ in labeled]
        pred = [stage_of(o, s) for _, o in labeled]
        agreement[s] = metrics.summarize(gold, pred)
        calib_pairs += [(conf_of(o, s), stage_of(o, s) == r["target_stage"][s]) for r, o in labeled
                        if stage_of(o, s) is not None]
    stability = {s: metrics.repeat_stability(repeat_runs[s]) for s in subs_names} if repeat_rows else {}

    style_bias = defaultdict(lambda: defaultdict(list))
    length_bias = defaultdict(lambda: defaultdict(list))
    for r, o in labeled:
        nwords = len(r["submission_text"].split())
        band = "short (<120 words)" if nwords < 120 else "medium (120-180)" if nwords <= 180 else "long (>180)"
        for s in subs_names:
            p = stage_of(o, s)
            if p is not None:
                style_bias[r.get("writing_style", "?")][s].append(p - r["target_stage"][s])
                length_bias[band][s].append(p - r["target_stage"][s])

    traj = defaultdict(list)
    for r, o, _ in scored:
        traj[r["student_id"]].append((r["attempt_no"], [stage_of(o, s) for s in subs_names]))

    ok = [o for _, o, e in scored if not e and o.get("tokens_in")]
    lat = [o["latency_ms"] for o in ok]
    tin, tout = sum(o["tokens_in"] for o in ok), sum(o["tokens_out"] for o in ok)
    costs = [o["cost_usd"] for o in ok if o.get("cost_usd") is not None]
    per_call = round(statistics.mean(costs), 5) if costs else None

    summary = {
        "run_id": run_id, "contract_version": CONTRACT_VERSION, "model_id": args.model,
        "temperature": args.temperature, "rubric_id": rubric["rubric_id"], "n_submissions": len(subs),
        "label_source": "synthetic_target (debugging only, overstates real agreement)",
        "E01_agreement_vs_synthetic_target": agreement,
        "E02_repeat_stability": {"n_items": len(repeat_rows), "repeats": args.repeats, **stability},
        "E11_calibration": calibration(calib_pairs),
        "E08_E16_adversarial": adv_results,
        "E09_cost_latency": {"model_calls": len(ok), "tokens_in_per_call": round(tin / max(len(ok), 1)),
                             "tokens_out_per_call": round(tout / max(len(ok), 1)),
                             "cost_per_call_usd": per_call,
                             "cost_main_pass_usd": round(sum(costs), 4) if costs else None,
                             "latency_p50_ms": pct(lat, 0.5), "latency_p95_ms": pct(lat, 0.95)},
        "E14_style_bias_mean_pred_minus_target": {
            k: {s: round(statistics.mean(v), 2) if v else None for s, v in d.items()} for k, d in style_bias.items()},
        "E14_length_bias_mean_pred_minus_target": {
            k: {s: round(statistics.mean(v), 2) if v else None for s, v in d.items()} for k, d in length_bias.items()},
        "needs_review_count": sum(bool(o.get("needs_review")) for _, o, _ in scored),
        "errors": [r["submission_id"] for r, _, e in scored if e],
        "parse_errors": [r["submission_id"] for r, o, _ in scored if "parse_error" in o.get("filter_flags", [])],
        "event_log": log_path.name,
    }
    (RESULTS / f"summary_{run_id}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (RESULTS / f"report_{run_id}.md").write_text(report(summary, traj, subs_names), encoding="utf-8")
    print(f"\nWrote results/summary_{run_id}.json, report_{run_id}.md, {log_path.name}")
    return 0


def report(s, traj, subs) -> str:
    L = [f"# Evaluation harness report: `{s['run_id']}`", "",
         f"- Contract v{s['contract_version']}; grader `{s['model_id']}`, temperature {s['temperature']}",
         f"- Rubric `{s['rubric_id']}` (draft task rubric, Concept 3 / HS-PRO-RD-18)",
         f"- Submissions scored: {s['n_submissions']} (synthetic)", "",
         "> Labels are the **synthetic target stages** the generator was asked to write to. These numbers "
         "check that the harness works; they are not the E01 result. E01 needs human-rated submissions "
         "(see `annotation/`).", "",
         "## E01 agreement vs. synthetic target", "",
         "| Sub-skill | n | Exact | Adjacent (±1) | Quadratic weighted kappa |", "|---|---|---|---|---|"]
    for sub, m in s["E01_agreement_vs_synthetic_target"].items():
        L.append(f"| {sub} | {m['n']} | {m['exact']} | {m['adjacent']} | {m['qwk']} |")
    L += ["", "Confusion matrices (rows = target stage, columns = predicted stage):", ""]
    L += [f"- **{sub}**: `{m['confusion']}`" for sub, m in s["E01_agreement_vs_synthetic_target"].items()]
    st = s["E02_repeat_stability"]
    if st["n_items"]:
        L += ["", "## E02 repeat-scoring stability", "",
              f"{st['n_items']} submissions scored {st['repeats']} times. Share with an identical stage every time:", ""]
        L += [f"- {sub}: {st.get(sub)}" for sub in subs]
    c = s["E11_calibration"]
    L += ["", "## E11 confidence calibration (vs. synthetic target)", "",
          f"Expected calibration error (ECE): **{c['ece']}** over {c['n']} sub-skill scores. "
          "A well-calibrated grader has exact agreement close to mean confidence in every bin.", "",
          "| Confidence bin | n | Mean confidence | Exact agreement |", "|---|---|---|---|"]
    L += [f"| {b['bin']} | {b['n']} | {b['mean_confidence']} | {b['exact_agreement']} |" for b in c["bins"]]
    L += ["", "## E03 stage trajectories (predicted, per attempt)", "",
          f"| Student | Attempts → ({', '.join(subs)}) |", "|---|---|"]
    for sid, att in sorted(traj.items()):
        L.append(f"| {sid} | " + " → ".join("(" + ",".join(str(v) for v in a[1]) + ")"
                                             for a in sorted(att, key=lambda x: x[0])) + " |")
    if s["E08_E16_adversarial"]:
        L += ["", "## E08 / E16 adversarial and abnormal input", "",
              "| ID | Case | Expected flags | Got flags | Flags OK | Scorable OK | Needs review | Stages | Raised by injection |",
              "|---|---|---|---|---|---|---|---|---|"]
        for a in s["E08_E16_adversarial"]:
            L.append(f"| {a['submission_id']} | {a['case_type']} | {a['expected_flags']} | {a['got_flags']} | "
                     f"{a['flags_ok']} | {a['scorable_ok']} | {a['needs_review']} | {a['stages']} | {a['inflated']} |")
    c = s["E09_cost_latency"]
    L += ["", "## E09 tokens, latency, cost", "",
          f"- Model calls: {c['model_calls']}; per call {c['tokens_in_per_call']} in / {c['tokens_out_per_call']} out",
          f"- Latency: P50 {c['latency_p50_ms']} ms, P95 {c['latency_p95_ms']} ms",
          f"- Cost per scoring call: ${c['cost_per_call_usd']}; main pass total ${c['cost_main_pass_usd']} "
          "(prices in `harness/bedrock_client.py`, verify before external use). Load projection: `results/E09_cost_projection.md`.",
          "", "## E14 fairness proxies (mean predicted minus target stage)", "",
          f"| Writing style | {' | '.join(subs)} |", "|---|" + "---|" * len(subs)]
    for k, d in s["E14_style_bias_mean_pred_minus_target"].items():
        L.append(f"| {k} | " + " | ".join(str(d.get(x)) for x in subs) + " |")
    L += ["", f"| Length band | {' | '.join(subs)} |", "|---|" + "---|" * len(subs)]
    for k, d in sorted(s["E14_length_bias_mean_pred_minus_target"].items()):
        L.append(f"| {k} | " + " | ".join(str(d.get(x)) for x in subs) + " |")
    L += ["", f"Needs review: {s['needs_review_count']}. Errors: {s['errors'] or 'none'}. "
          f"Parse errors: {s['parse_errors'] or 'none'}.", f"Event log: `results/{s['event_log']}`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
