# Evaluation harness and MCP standard (draft v0.2)

Owner: evaluation workstream (Pengcheng Lu). Status: **draft for team review**. Nothing here is agreed until the team signs off.
Scope: evaluation only. Routing, the skill tree, agents, and UI belong to other teammates; this document only fixes the interfaces the evaluation harness needs from them.

| File | What it is |
| --- | --- |
| [`README.md`](README.md) | Evaluation plan (layers L0-L3, items E01-E16) |
| [`schemas/`](schemas/) | Contracts: `validate_submission`, `route_next`, event log, telemetry event |
| [`rubrics/concept3_task_rubric.json`](rubrics/concept3_task_rubric.json) | Draft task-level rubric, Concept 3 / CSTA HS-PRO-RD-18 |
| [`harness/`](harness/) | Generators, reference grader, metrics, run and analysis scripts, MCP server |
| [`data/`](data/) | Synthetic students, submissions, adversarial set, simulated cohort sets ([`data/README.md`](data/README.md)) |
| [`annotation/`](annotation/) | Rating sheets for human raters (E01, E10) |
| [`protocols/`](protocols/) | E04 study protocol; E12 / E13 / E15 instruments |
| [`results/`](results/) | Reports from harness runs |

## 1. MCP standard

### 1.1 Why MCP, and what it does not decide

MCP standardizes how an agent discovers and calls tools (`tools/list`, `tools/call`, JSON Schema inputs and outputs). It does **not** decide routing between agents; that stays the routing teammates' design choice. Plain HTTP/JSON with the same schemas is an acceptable alternative: the schemas are the contract, the transport is not.

### 1.2 Tools

| Tool | Owner | Served by | Called by |
| --- | --- | --- | --- |
| `validate_submission` | Validation service (teammates); reference implementation by evaluation | `harness/mcp_server.py` (draft) | Lesson agent, router, evaluation harness |
| `route_next` | Routing (teammates) | Routing service | Lesson flow, evaluation harness (E06) |
| `get_rubric` | Evaluation | `harness/mcp_server.py` | Any client that displays or checks the rubric |

### 1.3 Contract rules (v0.2)

1. **Versioning.** Every output and every event-log row carries `contract_version`. Below 1.0, breaking changes are allowed with a changelog entry (section 1.6). From 1.0: adding an optional field is a minor bump; renaming, removing, or changing the meaning of a field is a major bump and needs team agreement.
2. **The rubric defines the shape.** Sub-skill names (`subskill_order`) and the stage range (`0..stage_max`) come from the rubric referenced by `rubric_id`. The schemas do not hard-code Concept 3, so a new lesson needs a new rubric, not a new schema.
3. **One result per sub-skill**, in `subskill_order`, each scored independently.
4. **Strict output.** `stage` is an integer in range, or `null`. The grader never guesses a stage for unscorable input; non-JSON grader output becomes `parse_error` with null stages.
5. **Flag effects are fixed** (a flag never raises a stage):

   | Class | Flags | Effect |
   | --- | --- | --- |
   | BLOCKING | `empty`, `too_short`, `gibberish`, `guardrail_blocked` | `scorable = false`; every stage `null` |
   | REVIEW | `prompt_injection`, `inappropriate`, `suspected_ai_paste` | scored on the evidence; `needs_review = true` (teacher checks before it affects routing beyond the lesson) |
   | ERROR | `parse_error` | stages `null` |

6. **Evidence.** Every non-null stage has a one-sentence `rationale` and at least one verbatim `evidence_quotes` entry.
7. **Confidence is uncalibrated** until E11 reports a calibration curve. Do not use it as a routing threshold before then.
8. **Errors.** Tool errors return `isError: true` (MCP convention). The caller then uses the non-adaptive fallback path, keeps the last known stages, and logs `fallback_triggered = true` (E07).
9. **Model abstraction.** Callers never pass provider parameters. The output records the actual `model_id` (and `cost_usd`), so a model swap (E11) needs no caller change.
10. **Field names are shared.** The task is `task_id` everywhere (tool input, event log, telemetry). `level_id` is a deprecated alias until 1.0.
11. **No PII.** `student_id` matches `^(SIM|ADV|STU)-`: synthetic, adversarial, or pseudonymous. No names, emails, or school IDs in input, output, or logs. Telemetry logs prompt length, not prompt text.

### 1.4 Security requirements for any `validate_submission` implementation

- Wrap student text in `<student_submission>…</student_submission>`, escape `<` inside it, and tell the grader the content is data.
- Require JSON-only output; anything else is `parse_error`.
- Run the rule-based pre-filter before any model call.
- Put Bedrock Guardrails on student input (and on hint output in production). The evaluation baseline guardrail and its results are in `results/E08_guardrail_report.md`.
- Set `maxTokens` explicitly on every model call.

### 1.5 Running the draft MCP server

```bash
python -m evaluation.harness.mcp_server        # stdio transport
```

```json
{"mcpServers": {"codeai-eval": {"command": "python", "args": ["-m", "evaluation.harness.mcp_server"], "cwd": "<repo root>"}}}
```

The draft implements the MCP JSON-RPC methods (`initialize`, `tools/list`, `tools/call`, `ping`) directly because the `mcp` Python SDK requires Python 3.10+. Port it to `FastMCP` with the same tool names and schemas when the environment allows. Tool schemas are served self-contained (local `$ref`s inlined).

### 1.6 Changelog

| Version | Change |
| --- | --- |
| 0.2 | `level_id` → `task_id` (alias kept). Sub-skills and stage range from the rubric. Added `contract_version`, `rubric_id`, `scorable`, `needs_review`, `cost_usd` to the output; `stages` map to the event log (flat `stage_*` columns deprecated). Flag classes and effects defined; added `guardrail_blocked`; `suspected_ai_paste` now implemented. `route_next.validation_results` typed; `last_task_id` and `LESSON_COMPLETE` added; `policy` in the output is the policy actually used. Confidence semantics defined. Telemetry event schema added. |
| 0.1 | First draft. |

## 2. Harness standard

### 2.1 What the harness is

A repeatable program that sends fixed datasets through the tool contracts, writes one event-log row per call, and computes the evaluation items from that log. It talks only to the contracts, so it works with the reference grader now and with the teammates' services later.

```
data/*.jsonl ──► validate_submission ──► event log (JSONL) ──► metrics ──► results/*.md
                        │                                        ▲
                        └──► route_next (per policy, E06) ───────┘
```

### 2.2 Datasets

| Set | File | Labels | Used for | Rule |
| --- | --- | --- | --- | --- |
| Synthetic submissions | `data/mock_submissions.jsonl` | `target_stage` given to the generator | Harness debugging, E02, E03, E09, E11, E14 proxy | **Never report E01 from this set.** It overstates agreement. |
| Adversarial / abnormal | `data/adversarial_set.jsonl` | `expected_flags`, `expected_scorable` | E08, E16 | Hand-written; extend whenever a new failure is found. |
| Routing cohort (simulated) | `data/routing_sim_events.jsonl` | Simulated true stage per step (`sim` block) | E05, E06, E07 | No model calls; policies and learning model are assumptions. |
| Pre / post / transfer (simulated) | `data/prepost_synthetic.jsonl` | Simulated true stage before and after | E04 pipeline | Tests the analysis only. |
| Lesson telemetry (simulated) | `data/telemetry_synthetic.jsonl` | Simulated stuck episodes | Proactive-hint trigger recall / precision | Schema `schemas/telemetry_event.schema.json`. |
| Benchmark (human-rated) | to add: `data/benchmark/submissions.jsonl` | Two independent raters (`annotation/`) | E01, E10 | Required before any agreement number is reported. |

Synthetic-data rules: generator model ≠ grader model; every stage 0-3 present for every sub-skill; writing style balanced (E14 proxy, since there is no group data); 1-3 attempts per student; profiles reference CSTA 2026 PK-12 standards (task targets **HS-PRO-RD-18**, builds on MS-PRO-RD-17; [csteachers.org/pk12standards](https://csteachers.org/pk12standards/)).

### 2.3 Event log

One JSON row per tool call (`schemas/event_log.schema.json`). Every evaluation item reads from it, so the fields must be agreed before teammates' services start writing it. `input_hash` (sha256 of the canonical input) is used for caching repeated validations and for grouping repeat-scoring runs (E02). The `sim` block appears only in synthetic data.

### 2.4 Run protocol

1. Pin the run: grader `model_id`, `temperature`, `rubric_id`, contract version, dataset files (all written to the summary).
2. Main pass; repeat pass (first N submissions, K times) for E02; adversarial pass for E08 / E16.
3. Drift runs (E11): same sample, second model and a higher temperature; compare with `analyze_runs drift`.
4. Cohort simulation (E04 / E05 / E06 / E07 / telemetry): `cohort_sim`, no model calls.
5. Guardrail test (E08): `guardrail_eval`, ApplyGuardrail only.
6. Human agreement (E01 / E10): `annotation make` → raters fill sheets → `annotation score`.

```bash
python -m evaluation.harness.simulate --students 20 --seed 8
python -m evaluation.harness.simulate --students 80 --seed 21 --append --start-weights uniform
python -m evaluation.harness.run_eval --repeat-n 20 --repeats 3 --tag main
python -m evaluation.harness.run_eval --model us.anthropic.claude-sonnet-4-5-20250929-v1:0 --sample 60 --repeats 1 --skip-adversarial --tag drift-sonnet45
python -m evaluation.harness.run_eval --temperature 0.7 --sample 60 --repeats 1 --skip-adversarial --tag drift-t07
python -m evaluation.harness.analyze_runs drift --base <main run_id> --other <drift run_ids>
python -m evaluation.harness.analyze_runs cost --run <main run_id>
python -m evaluation.harness.cohort_sim --seed 8
python -m evaluation.harness.guardrail_eval --create        # --delete to remove it
python -m evaluation.harness.annotation make --source real --raters A B
python -m evaluation.harness.annotation score --source real --grader-log results/event_log_<run>.jsonl
```

### 2.5 Metrics

| Item | Metric | Where |
| --- | --- | --- |
| E01 / E10 | Exact, adjacent (±1), quadratic weighted kappa, 4x4 confusion matrix per sub-skill; human-human first, then grader-human | `metrics.py`, `annotation.py` |
| E02 | Share of submissions with an identical stage across K repeats | `run_eval.py` |
| E03 | Stage per attempt per student | run report |
| E04 | Pre / post / transfer gain by condition | `cohort_sim.py`, `protocols/E04_learning_effect_protocol.md` |
| E05 | Per-task "observed stage went up" rate; per-sub-skill funnel; Stage 3 evidence coverage | `cohort_sim.py` |
| E06 | Mastery within budget, steps to mastery, premature completion, wasted steps, repeats, loops, per policy | `cohort_sim.py` |
| E07 | Failures, fallback steps, stages reset after failure (must be 0), outcome of affected students | `cohort_sim.py` |
| E08 / E16 | Flags raised as expected; scorability as expected; no stage raised by injection; guardrail catch rate and false-positive rate | run report, `guardrail_eval.py` |
| E09 | Tokens, P50 / P95 latency, cost per call; class / school / district and peak-load projection vs. $500 | `analyze_runs cost` |
| E11 | Calibration bins and ECE; stage agreement across models and temperatures | run report, `analyze_runs drift` |
| E12 / E13 / E15 | Hint rating sheet, log proxies + 3-item survey, interview guide | `protocols/E12_E13_E15_instruments.md` |
| E14 | Mean (predicted − target) by writing style and by length band | run report |

### 2.6 Pass criteria

The E01 threshold is not set yet, on purpose: set it after human-human agreement (E10) on the benchmark is known, because that is the ceiling. Hard requirements that do not depend on the benchmark:

- 0 parse errors and 0 unhandled exceptions in a run.
- 100% of BLOCKING-flag cases return `scorable = false` and null stages.
- No injection case scored at Stage 2 or above.
- 0 stages reset after a validation failure (E07).
- Guardrail false-positive rate on normal submissions ≤ 1% (to be re-checked on real writing).

### 2.7 Budget guardrails

Budget is $500 on Bedrock in us-west-2. Cost per scoring call and projections are in `results/E09_cost_projection.md`. Before larger runs: set an AWS Budgets alert, cache by `input_hash`, and cap calls per run.

## 3. Open questions for the team

1. Do teammates accept these schemas as v0.2, or want changes before they start logging?
2. MCP over stdio, MCP over HTTP, or plain HTTP/JSON for the deployed services?
3. Where does the event log live in production (S3 JSONL, Aurora table, or Langfuse traces)? The schema works for all three.
4. Who provides the human-rated benchmark submissions and the two raters for E01 / E10?
5. Production guardrail policy (filters, strengths, denied topics) is a T&L decision; the evaluation baseline is only a starting point.

## 4. Changes in contract v0.2 and the diagnostic runner

Added by the Weather Station readiness diagnostic (`diagnostic/`). All changes are additive; v0.1 data still validates.

| Schema | Change |
|---|---|
| `validate_submission` | `subskill` also allows `database_retrieval`, `conditionals`, `loops`, `functions`. `filter_flags` also allows `personal_info`. A task may target one sub-skill, so `results` holds only the sub-skills the task targets. |
| `event_log` | Optional `stages` object (stage per sub-skill, any names). `cost_usd` may be `null`, which is how `run_eval.py` already writes it when no price is configured. |
| `route_next` | Unchanged. |

New files: `rubrics/weather_diag_rubric.json` (generated from the diagnostic's content by `python3 -m diagnostic.cli export-rubric`;
`"provider": "diagnostic"` routes the MCP `validate_submission` tool to it), `harness/run_diag_eval.py`, `harness/diag_cases.py`,
`data/diag_*`. `harness/mcp_server.py` now imports the Concept 3 reference grader lazily, so the server starts without `boto3`.

```bash
python3 -m evaluation.harness.run_diag_eval --provider mock      # offline; also: off, bedrock
```

Hard requirements are checked in every run (section 2.6, plus quest length, schema conformance, no scores shown to students, and fallback
on model failure and on selector failure). Agreement with simulated children is a pipeline check, not E01.
