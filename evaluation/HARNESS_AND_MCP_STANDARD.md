# Evaluation harness and MCP standard (draft v0.1)

Owner: evaluation workstream (Pengcheng Lu). Status: **draft for team review**. Nothing here is agreed until the team signs off.
Scope: evaluation only. Routing, the skill tree, agents, and UI are owned by other teammates; this document only fixes the interfaces the evaluation harness needs from them.

Related files:

| File | What it is |
| --- | --- |
| [`README.md`](README.md) | Evaluation plan (layers L0-L3, items E01-E16) |
| [`schemas/validate_submission.schema.json`](schemas/validate_submission.schema.json) | Tool contract: grading |
| [`schemas/route_next.schema.json`](schemas/route_next.schema.json) | Tool contract: routing (consumed, not implemented, by evaluation) |
| [`schemas/event_log.schema.json`](schemas/event_log.schema.json) | One row per tool call |
| [`rubrics/concept3_task_rubric.json`](rubrics/concept3_task_rubric.json) | Draft task-level rubric, Concept 3 / HS-PRO-RD-18 |
| [`harness/`](harness/) | Harness code: mock data, reference grader, metrics, MCP server |
| [`data/`](data/) | Mock students, mock submissions, adversarial set |

## 1. MCP standard

### 1.1 Why MCP, and what it does not decide

MCP standardizes how an agent discovers and calls tools (`tools/list`, `tools/call`, JSON Schema inputs and outputs). It does **not** decide routing between agents. Routing stays a separate design choice owned by the routing teammates. Plain HTTP/JSON with the same schemas is an acceptable alternative; the schemas are the contract, the transport is not.

### 1.2 Tools

| Tool | Owner | Served by | Called by |
| --- | --- | --- | --- |
| `validate_submission` | Validation service (teammates); reference implementation by evaluation | `harness/mcp_server.py` (draft) | Lesson agent, router, evaluation harness |
| `route_next` | Routing (teammates) | Routing service | Lesson flow, evaluation harness (E06 policy comparison) |
| `get_rubric` | Evaluation | `harness/mcp_server.py` | Any client that needs to display or check the rubric |

### 1.3 Contract rules

1. **Schemas are versioned.** `$id` ends in `/vMAJOR.MINOR`. Adding an optional field is a minor bump. Renaming, removing, or changing the meaning of a field is a major bump and needs team agreement.
2. **Strict output.** `validate_submission` returns exactly the schema shape. `stage` is an integer 0-3, or `null` when the input was filtered or unscorable. The grader never guesses a stage for unscorable input.
3. **One result per sub-skill.** Concept 3 has three sub-skills: `prompting`, `evaluation`, `prompt_revision`. Each is scored independently.
4. **Evidence.** Every non-null stage carries a one-sentence `rationale` and at least one `evidence_quotes` entry taken from the student's text.
5. **Filtering is reported.** Pre-filter and guardrail decisions appear in `filter_flags` (enum in the schema). A flag never silently changes a stage.
6. **Errors.** Tool errors return `isError: true` with a message (MCP convention). The caller must then use the non-adaptive fallback path and log `fallback_triggered = true` (E07).
7. **Model abstraction.** Callers never pass provider-specific parameters. The service records the actual `model_id` in the output, so swapping models (E11) needs no caller change.
8. **No PII.** `student_id` is synthetic (`SIM-`), adversarial (`ADV-`), or pseudonymous (`STU-`). No names, emails, or school IDs anywhere in tool input, output, or logs.

### 1.4 Security requirements for any `validate_submission` implementation

- Wrap student text in delimiters (`<student_submission>…</student_submission>`), escape `<` inside it, and tell the grader that the content is data.
- Require JSON-only output; treat anything else as `parse_error` with null stages.
- Run the abnormal-input pre-filter before the model call: `empty`, `too_short`, `gibberish`, `prompt_injection`, `inappropriate`.
- In production, put Bedrock Guardrails on both input and output; the rule-based pre-filter in the harness is only a stand-in.
- Set `maxTokens` explicitly on every model call.

### 1.5 Running the draft MCP server

```bash
python -m evaluation.harness.mcp_server        # stdio transport
```

Example MCP client config:

```json
{"mcpServers": {"codeai-eval": {"command": "python", "args": ["-m", "evaluation.harness.mcp_server"], "cwd": "<repo root>"}}}
```

The draft speaks the MCP JSON-RPC methods directly because the `mcp` Python SDK requires Python 3.10+. Port it to `FastMCP` with the same tool names and schemas when the environment allows.

## 2. Harness standard

### 2.1 What the harness is

A repeatable program that sends a fixed set of submissions through the tool contracts, writes one event-log row per call, and computes the evaluation items from that log. It talks only to the contracts, so it works with the reference grader today and with the teammates' services later.

```
data/*.jsonl ──► validate_submission ──► event log (JSONL) ──► metrics ──► results/report_*.md
                        │                                        ▲
                        └──► route_next (per policy, E06) ───────┘
```

### 2.2 Datasets

| Set | File | Labels | Used for | Rule |
| --- | --- | --- | --- | --- |
| Mock (synthetic) | `data/mock_submissions.jsonl` | `target_stage` given to the generator | Debugging the harness, E02, E03, E09, E14 proxy | **Never report E01 from this set.** It overstates agreement. |
| Adversarial / abnormal | `data/adversarial_set.jsonl` | `expected_flags` | E08, E16 | Hand-written; extend whenever a new failure is found. |
| Benchmark (human-rated) | to be added: `data/benchmark/` | Two independent human raters | E01, E10 | Required before any agreement number is reported. |

Mock data rules:

- The generator model differs from the grader model (`GENERATOR_MODEL` vs `GRADER_MODEL` in `harness/bedrock_client.py`), to reduce self-agreement.
- Every stage 0-3 appears for every sub-skill. Start stages are weighted toward 0-1, like a real class.
- Writing style (`terse`, `standard`, `verbose`, `informal`, `esl`) is balanced across students. It is the proxy variable for the fairness check (E14), because there is no group data.
- Students have 1-3 attempts with mostly rising target stages, so stage trajectories (E03) exist.
- Profiles reference CSTA 2026 PK-12 standards: the task targets **HS-PRO-RD-18**, which builds on **MS-PRO-RD-17** ([csteachers.org/pk12standards](https://csteachers.org/pk12standards/), workbook in `curriculum database/`).

### 2.3 Event log

One JSON row per tool call, schema in `schemas/event_log.schema.json`. Every evaluation item reads from this log, so the fields must be agreed before teammates' services start writing it. Key fields: `run_id`, `student_id`, `lesson_id`, `task_id`, `attempt_no`, `tool`, `input_hash`, per-sub-skill stages, `model_id`, `temperature`, tokens, `cost_usd`, `latency_ms`, `filter_result`, `fallback_triggered`, `error`.

`input_hash` (sha256 of the canonical input) is used for caching repeated validations (budget) and for grouping repeat-scoring runs (E02).

### 2.4 Run protocol

1. Pin the run: grader `model_id`, `temperature`, `rubric_id`, dataset files. All are written into the summary.
2. Main pass over the dataset.
3. Repeat pass: re-score the first N submissions K times (default N=8, K=3) at the same settings (E02).
4. Adversarial pass (E08, E16).
5. Compute metrics and write `results/summary_<run_id>.json`, `results/report_<run_id>.md`, `results/event_log_<run_id>.jsonl`.
6. For drift (E11), repeat the run with a second model or temperature and compare per-submission stages.

```bash
python -m evaluation.harness.simulate --students 20     # writes data/
python -m evaluation.harness.run_eval --repeat-n 8 --repeats 3
```

### 2.5 Metrics

| Item | Metric | Implementation |
| --- | --- | --- |
| E01 | Exact agreement, adjacent (±1) agreement, quadratic weighted kappa, 4x4 confusion matrix per sub-skill | `harness/metrics.py` |
| E02 | Share of submissions with an identical stage across all K repeats | `metrics.repeat_stability` |
| E03 | Stage per attempt per student | report table |
| E08 / E16 | Expected flag raised; stages null where expected; no stage raised by injection text | report table |
| E09 | Tokens in/out per call, P50/P95 latency; cost once prices are filled in | `bedrock_client.PRICES_PER_MTOK` |
| E14 | Mean (predicted minus target) stage by writing style | report table |

### 2.6 Pass criteria

Not set yet, on purpose. Following the evaluation plan: set the E01 threshold only after the human-human agreement (E10) on the benchmark set is known, because that is the ceiling for model agreement. Proposed hard requirements that do not depend on the benchmark:

- 0 parse errors and 0 unhandled exceptions in a run.
- 100% of `empty` / `gibberish` / `too_short` cases return null stages.
- 0 injection cases scored at Stage 3.

### 2.7 Budget guardrails

Budget is $500 on Bedrock in us-west-2. A full mock run (about 40 submissions, 16 repeats, 13 adversarial cases) is roughly 70 grader calls. Before larger runs: set an AWS Budgets alert, cache by `input_hash`, and cap calls per run.

## 3. Open questions for the team

1. Do teammates' services accept these schemas as v0.1, or do they want changes before they start logging?
2. MCP over stdio, MCP over HTTP, or plain HTTP/JSON for the deployed services?
3. Where does the event log live in production (S3 JSONL, Aurora table, or Langfuse traces)? The schema works for all three.
4. Who provides the human-rated benchmark submissions for E01 / E10?
