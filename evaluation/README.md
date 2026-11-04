# Evaluation plan (draft)

Owner: Pengcheng Lu. Status: draft for team discussion. Nothing here is agreed yet.

This document proposes how we evaluate the adaptive lesson. It is written against **interfaces, not implementations**, so it works whatever we decide for routing and agents. The full list of items, with owner and status columns, is in [`Evaluation_Plan.xlsx`](Evaluation_Plan.xlsx).

## Why evaluation is more than "does the grader agree"

The vision doc's Definition of Done asks for validation agreement, a verified fallback, and verified filtering. We also want to answer questions that the stakeholders will ask:

| Stakeholder | Question | Layer |
| --- | --- | --- |
| Students | Am I making progress, and what is next? (feedback, never scores) | L1 |
| Teachers | Who is stuck on which sub-skill? (report or export only; the dashboard is out of scope) | L1, L3 |
| Teaching & Learning (T&L) | Is the rubric reliable and is the content working? | L0, L3 |
| CodeAI leadership, districts | Does it work, and what does it cost? | L2, cost |

## Four layers

| Layer | Question | Example metrics |
| --- | --- | --- |
| L0 Evaluator | Is the mastery signal trustworthy? | Weighted kappa and adjacent-stage agreement vs. human raters; repeat-scoring stability |
| L1 Student performance | Where is each student on each sub-skill, and how did they get there? | Stage trajectory, attempts to reach Stage 2, hint dependence |
| L2 Learning effect | Does the adaptive path improve learning? | Pre/post on the same rubric; fallback path as the control; unaided transfer task |
| L3 Lesson / course | Which lessons fail to move students? | Per-lesson stage-transition funnel; Stage 3 evidence coverage |

Notes:

- The non-adaptive fallback path required by the MVP is a ready-made control for L2.
- Performance while the AI helps is not learning. L2 therefore uses an unaided transfer task.
- With a small test cohort we can only report descriptive numbers. L2 is delivered as a protocol, not an efficacy claim.

## Items beyond the four layers

Must items come from the Definition of Done, the core hypothesis, or the risk table.

| ID | Item | Metric / approach | Priority |
| --- | --- | --- | --- |
| E06 | Routing quality | Same simulated cohort under stage-rules, agent, fixed-order, and random policies; loop and repeated-content checks | Must |
| E07 | Fallback trigger and quality | Trigger rate; usability after the switch; progress preserved | Must |
| E08 | Content filtering (input and output) | Adversarial set (jailbreak, injection, inappropriate content); false-positive rate | Must |
| E09 | Cost and latency | Tokens and dollars per call, P50/P95, peak-load extrapolation | Must |
| E10 | Rubric validity | Human-human agreement, which is the ceiling for LLM agreement | Should |
| E11 | Calibration and model drift | Confidence calibration; agreement across models, temperatures, prompt wordings | Should |
| E16 | Abnormal input | Empty, gibberish, pasted-AI, and copied submissions | Should |
| E12 | Hint quality | Small human rating; hint strength per attempt | Nice-to-have |
| E13 | Engagement and experience | Log proxies; 2 to 3 item survey; completion within 45 minutes | Nice-to-have |
| E14 | Fairness | Bias check against prompt length and language style | Nice-to-have |
| E15 | Teacher trust | 1 to 2 interviews with T&L staff | Nice-to-have |

## Proposed interface contract (MCP or plain HTTP/JSON)

MCP standardizes how agents call tools. It does not decide how agents route between each other, so routing logic stays a separate design choice. The harness only needs these two tools plus an event log.

```json
{
  "tool": "validate_submission",
  "input": {
    "lesson_id": "string", "level_id": "string", "attempt_no": 1,
    "submission_text": "string", "rubric_id": "string"
  },
  "output": {
    "results": [{
      "subskill": "prompting | evaluation | prompt_revision",
      "stage": 0,
      "confidence": 0.0,
      "rationale": "string",
      "evidence_quotes": ["string"]
    }],
    "model_id": "string", "latency_ms": 0, "filter_flags": []
  }
}
```

```json
{
  "tool": "route_next",
  "input": { "student_id": "string", "lesson_id": "string", "validation_results": ["..."], "policy": "stage_rules | agent | fixed_order | random" },
  "output": { "next_task_id": "string", "reason": "string", "policy": "string", "fallback": false }
}
```

Event log, one row per call: timestamp, student_id (synthetic), lesson_id, task_id, tool, input hash, output, stage per sub-skill, model_id, tokens in and out, cost, latency, filter result, fallback triggered. Every evaluation item reads from this log, so the fields should be agreed early.

Keep the model choice behind an abstraction (required by the technical doc, and needed for E11).

## Benchmark plan (proposal)

1. Pick the sample lesson. My working assumption is Concept 3 (AI Collaboration and Iterative Prompting), because submissions are text and the rubric criteria are checkable.
2. Collect or write student-like submissions that cover Stage 0 to 3 for each sub-skill (Prompting, Evaluation, Prompt Revision). Size is open; for example, a few dozen submissions.
3. Have two people rate them independently against the rubric. Their agreement gives the ceiling (E10).
4. Score the same set with the validation service and report weighted kappa, adjacent agreement, and the confusion matrix (E01).
5. Set the pass threshold after seeing the human-human number, not before.

Synthetic LLM-written submissions are fine for debugging the harness. They are cleaner than real student work and will overstate agreement, so the reported number should come from human-written or real submissions rated by humans.

## Risks

- Heavy measurement conflicts with the formative-assessment principle; collect in the background and show students feedback only.
- A router tuned to raise Stage may stop teaching; keep the unaided transfer task.
- LLM-human agreement is typically lower than human-human; do not promise a number up front.
- Student prompts are themselves sent to the scoring model, so isolate them with delimiters and require strict JSON output (prompt injection).
- Budget is $500 on Bedrock in us-west-2. Set AWS Budgets alerts, cache repeated validations, and cap calls. Confirm with staff whether credits cover Anthropic models and Guardrails.

## Questions for staff

1. Which lesson is the sample lesson? Are there task-level rubrics and human-scored submissions we can use as the benchmark?
2. What does the 73-lesson hexagonal progression map belong to, and should our skill tree follow its Needs / Unlocks format?
3. Which stage transitions in the Concept Learning Trajectories belong to our lesson? (L6 appears under both Stage 0 to 1 and Stage 1 to 2 for Concept 3.)
4. What agreement threshold counts as passing? Does "Level" mean a sub-lesson step or a student's skill level?
5. Do the hackathon credits cover Anthropic models on Bedrock and Guardrails in us-west-2?

## Suggested order

1. Agree the interface contract and event-log fields.
2. Write the metric spec and benchmark plan.
3. Generate simulated students and get the evaluation harness running.
4. Build the adversarial and abnormal-input sets (E08, E16).
5. Add the implementation-dependent metrics (E06, E07, E09) once routing and the agents exist.

## Harness, MCP standard, and mock data (draft v0.1)

Suggested-order steps 1 and 3 now have a first draft. See [`HARNESS_AND_MCP_STANDARD.md`](HARNESS_AND_MCP_STANDARD.md) for the contracts, run protocol, and metrics.

| Path | Contents |
| --- | --- |
| `schemas/` | JSON Schemas for `validate_submission`, `route_next`, and the event log |
| `rubrics/concept3_task_rubric.json` | Draft task-level rubric for Concept 3 (HS-PRO-RD-18); expected to be replaced by T&L |
| `harness/` | Mock-data generator, reference grader, metrics, run script, draft MCP server |
| `data/` | 100 synthetic students, 191 synthetic submissions (1-3 attempts each), 13 adversarial cases, simulated routing cohort (E06/E07), pre/post/transfer set (E04), lesson telemetry. See [`data/README.md`](data/README.md) |
| `results/` | Event logs, summaries, and markdown reports from harness runs |

```bash
pip install -r evaluation/requirements.txt
export AWS_DEFAULT_REGION=us-west-2           # plus AWS credentials
python -m evaluation.harness.simulate --students 20
python -m evaluation.harness.simulate --students 80 --seed 21 --append --start-weights uniform
python -m evaluation.harness.cohort_sim --seed 8   # E04 / E06 / E07 / telemetry, no model calls
python -m evaluation.harness.run_eval --repeat-n 20 --repeats 3
python -m evaluation.harness.mcp_server       # MCP over stdio
```

Mock submissions are synthetic. Agreement with their target stages only shows that the harness works; it is not the E01 result.

## Evaluating the proto-branch engine (and the Evaluation Console)

These scripts import `engine/` from the repo root (the layout after proto-branch is merged) and never change engine code. Set `CODEAI_PROTO_ROOT` to point elsewhere.

| Script | Item | Model calls | Output |
| --- | --- | --- | --- |
| `harness/proto_validation_bench.py` | E01: grader pass/fail vs. a draft human key (26 submissions) | none | `results/E01_proto_validation_*` |
| `harness/proto_fallback_eval.py` | E07: 12 injected failures (routing, grading, storage, AI hint) | none | `results/E07_proto_fallback_*` |
| `harness/proto_safety_eval.py` | E08: theme requests (input) and hint texts (output) through proto's filters and our Guardrail | Bedrock | `results/E08_proto_safety_*` |
| `harness/proto_hint_eval.py` | E12: AI vs. teacher hints, LLM judge + AgentCore Evaluations, blind rating sheet | Bedrock, AgentCore | `results/E12_proto_hint_*`, `annotation/E12_proto_hint_*` |
| `harness/agentcore_eval.py` | AgentCore on-demand `Evaluate` on spans we build (no Runtime needed); custom evaluator `codeai_team8_hint_socratic` | AgentCore | – |

The **Evaluation Console** is the interactive front end for presenting these results: a requirements page (customer requirement → status → evidence), live tools (grade any code, check any text through every filter layer, get and score a hint, re-run E01/E07), and a blind human-rating page for validating the judge.

```bash
cd evaluation/console && npm install && npm run build && cd ../..
python -m evaluation.harness.console_server          # http://127.0.0.1:8090 (needs PyYAML; AWS creds for live AI)
# development: run the server, then `npm run dev` in evaluation/console (http://127.0.0.1:5174)
```

The console runs student code through proto's grader (separate process, time limit, no security sandbox). Keep it on localhost.
