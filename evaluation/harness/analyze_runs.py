"""Cross-run analyses that read finished harness runs.

  drift  (E11): compare per-submission stages between a baseline run and one or
         more runs that changed the model or temperature.
  cost   (E09): project cost and throughput from a run's measured tokens and
         latency to class and peak-load scenarios, against the $500 budget.

Usage:
  python -m evaluation.harness.analyze_runs drift --base <main run_id> --other <run_id> [<run_id> ...]
  python -m evaluation.harness.analyze_runs cost --run <main run_id>
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import metrics
from .bedrock_client import PRICES_PER_MTOK, cost_usd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SUBS = ("prompting", "evaluation", "prompt_revision")
BUDGET_USD = 500.0


def _first_pass(run_id: str) -> dict:
    """submission key -> stages, from the first scoring of each input in a run."""
    out = {}
    for line in (RESULTS / f"event_log_{run_id}.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["tool"] != "validate_submission" or not e["student_id"].startswith("SIM-"):
            continue
        stages = e.get("stages") or {s: e.get(f"stage_{s}") for s in SUBS}
        out.setdefault(e["input_hash"], stages)
    return out


def _summary(run_id: str) -> dict:
    return json.loads((RESULTS / f"summary_{run_id}.json").read_text(encoding="utf-8"))


def drift(base: str, others: list[str]) -> None:
    b, bs = _first_pass(base), _summary(base)
    L = ["# E11 model and temperature drift", "",
         f"Baseline: `{base}` (`{bs['model_id']}`, t={bs['temperature']}). Each comparison uses the "
         "submissions both runs scored. Agreement here is grader vs. grader, not grader vs. human.", "",
         "| Comparison run | Model | Temp | n | Sub-skill | Exact | Adjacent | QWK | Mean shift (other − base) |",
         "|---|---|---|---|---|---|---|---|---|"]
    out = {"base": base, "comparisons": []}
    for o in others:
        os_, od = _summary(o), _first_pass(o)
        keys = [k for k in od if k in b]
        row = {"run_id": o, "model_id": os_["model_id"], "temperature": os_["temperature"], "n": len(keys), "subskills": {}}
        for s in SUBS:
            g = [b[k][s] for k in keys]
            p = [od[k][s] for k in keys]
            m = metrics.summarize(g, p)
            pairs = [(x, y) for x, y in zip(g, p) if x is not None and y is not None]
            shift = round(sum(y - x for x, y in pairs) / len(pairs), 2) if pairs else None
            row["subskills"][s] = {**m, "mean_shift": shift}
            L.append(f"| `{o}` | `{os_['model_id']}` | {os_['temperature']} | {len(keys)} | {s} | {m['exact']} | "
                     f"{m['adjacent']} | {m['qwk']} | {shift} |")
        out["comparisons"].append(row)
    L += ["", "Read: a model swap behind the abstraction layer should not move stages. Exact agreement well "
          "below the E02 repeat stability, or a non-zero mean shift, means a model change needs re-validation "
          "(E01) before it goes live.", ""]
    (RESULTS / "E11_drift_report.md").write_text("\n".join(L), encoding="utf-8")
    (RESULTS / "E11_drift_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote results/E11_drift_report.md")


def cost(run_id: str) -> None:
    s = _summary(run_id)
    c = s["E09_cost_latency"]
    model = s["model_id"]
    tin, tout = c["tokens_in_per_call"], c["tokens_out_per_call"]
    per_call = cost_usd(model, tin, tout)
    p50, p95 = c["latency_p50_ms"] / 1000, c["latency_p95_ms"] / 1000
    # Scenario assumptions (edit here): attempts scored per student per lesson,
    # from the simulated cohort (median ~7 tasks in a 12-task budget).
    calls_per_student_lesson = 8
    scen = [("One class, one lesson", 30, 1), ("One school, one lesson (10 classes)", 300, 1),
            ("District pilot, one lesson (100 classes)", 3000, 1), ("One class, full unit (8 lessons)", 30, 8)]
    L = [f"# E09 cost and latency projection (from `{run_id}`)", "",
         f"- Grader `{model}`; measured per scoring call: {tin} input / {tout} output tokens; "
         f"P50 {p50:.1f} s, P95 {p95:.1f} s.",
         f"- Price used: ${PRICES_PER_MTOK[model][0]} / ${PRICES_PER_MTOK[model][1]} per 1M input / output tokens "
         "(see `harness/bedrock_client.py`; verify against the Bedrock pricing page).",
         f"- **Cost per scoring call: ${per_call:.4f}.** Budget ${BUDGET_USD:.0f} covers "
         f"**{int(BUDGET_USD / per_call):,} scoring calls** at this rate.",
         f"- Assumption: {calls_per_student_lesson} scored attempts per student per lesson.", "",
         "| Scenario | Students | Lessons | Scoring calls | Cost (USD) | Share of $500 |", "|---|---|---|---|---|---|"]
    for name, n, lessons in scen:
        calls = n * lessons * calls_per_student_lesson
        L.append(f"| {name} | {n:,} | {lessons} | {calls:,} | {calls * per_call:,.2f} | {calls * per_call / BUDGET_USD:.1%} |")
    # Peak load: every student submits within the same 60 s window.
    L += ["", "## Peak load", "",
          "Worst case: a whole class or school submits within the same minute. Required concurrency "
          "≈ arrivals per second × P95 latency.", "",
          "| Students submitting within 60 s | Arrivals / s | Concurrent calls at P95 | Output tokens / min |",
          "|---|---|---|---|"]
    for n in (30, 300, 3000):
        rate = n / 60
        L.append(f"| {n:,} | {rate:.1f} | {math.ceil(rate * p95)} | {n * tout:,} |")
    L += ["", "Compare the output-tokens-per-minute column with the account's Bedrock quota for the model "
          "(`aws service-quotas list-service-quotas --service-code bedrock`). maxTokens is set to 900 per "
          "scoring call; quota is reserved against that value, not the ~500 tokens actually used.", "",
          "## Ways to cut cost", "",
          f"- Cache by `input_hash`: re-scoring identical input (resubmits, E02 repeats) costs nothing.",
          "- Prompt caching on the rubric system prompt (~1,100 tokens repeated on every call).",
          f"- Lower `maxTokens` from 900 toward the observed ~{tout} to reserve less quota.",
          "- A smaller grader only if E01/E11 show it agrees as well; never swap without re-running E01.", ""]
    (RESULTS / "E09_cost_projection.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote results/E09_cost_projection.md")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("drift")
    d.add_argument("--base", required=True)
    d.add_argument("--other", nargs="+", required=True)
    c = sp.add_parser("cost")
    c.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    drift(args.base, args.other) if args.cmd == "drift" else cost(args.run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
