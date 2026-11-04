# Evaluation harness report: `run-20261104T004927Z-drift-sonnet45-1473`

- Contract v0.2; grader `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, temperature 0.0
- Rubric `C3-L6-v0.1-draft` (draft task rubric, Concept 3 / HS-PRO-RD-18)
- Submissions scored: 60 (synthetic)

> Labels are the **synthetic target stages** the generator was asked to write to. These numbers check that the harness works; they are not the E01 result. E01 needs human-rated submissions (see `annotation/`).

## E01 agreement vs. synthetic target

| Sub-skill | n | Exact | Adjacent (±1) | Quadratic weighted kappa |
|---|---|---|---|---|
| prompting | 60 | 0.367 | 1.0 | 0.653 |
| evaluation | 60 | 0.45 | 0.983 | 0.63 |
| prompt_revision | 60 | 0.583 | 0.933 | 0.63 |

Confusion matrices (rows = target stage, columns = predicted stage):

- **prompting**: `[[0, 11, 0, 0], [0, 12, 1, 0], [0, 0, 6, 4], [0, 0, 22, 4]]`
- **evaluation**: `[[2, 7, 1, 0], [0, 0, 19, 0], [0, 0, 16, 1], [0, 0, 5, 9]]`
- **prompt_revision**: `[[3, 3, 4, 0], [0, 7, 11, 0], [0, 0, 16, 0], [0, 0, 7, 9]]`

## E11 confidence calibration (vs. synthetic target)

Expected calibration error (ECE): **0.41** over 180 sub-skill scores. A well-calibrated grader has exact agreement close to mean confidence in every bin.

| Confidence bin | n | Mean confidence | Exact agreement |
|---|---|---|---|
| [0.8, 0.9] | 112 | 0.858 | 0.455 |
| [0.9, 1.0] | 68 | 0.907 | 0.485 |

## E03 stage trajectories (predicted, per attempt)

| Student | Attempts → (prompting, evaluation, prompt_revision) |
|---|---|
| SIM-005 | (1,1,2) → (2,2,3) |
| SIM-007 | (1,2,2) → (3,2,3) |
| SIM-008 | (2,1,1) |
| SIM-010 | (1,0,2) |
| SIM-013 | (1,1,2) → (1,2,2) |
| SIM-014 | (2,1,2) |
| SIM-015 | (1,2,1) |
| SIM-016 | (1,1,1) |
| SIM-018 | (1,2,0) |
| SIM-019 | (2,2,0) |
| SIM-020 | (1,0,2) → (2,2,3) → (3,2,3) |
| SIM-021 | (1,2,2) |
| SIM-026 | (1,2,2) |
| SIM-028 | (2,2,2) |
| SIM-031 | (2,1,2) |
| SIM-032 | (2,2,2) → (2,3,2) |
| SIM-034 | (1,3,2) |
| SIM-035 | (1,2,2) → (1,2,2) |
| SIM-039 | (2,2,1) |
| SIM-045 | (1,2,1) |
| SIM-047 | (1,2,2) |
| SIM-048 | (3,3,3) |
| SIM-049 | (2,3,2) |
| SIM-050 | (2,2,2) → (3,3,2) → (3,3,2) |
| SIM-052 | (2,2,1) → (2,2,2) → (2,2,2) |
| SIM-055 | (1,2,1) |
| SIM-058 | (2,2,2) |
| SIM-060 | (2,2,2) → (2,2,2) |
| SIM-062 | (2,3,2) |
| SIM-064 | (1,2,2) |
| SIM-065 | (2,1,2) → (2,2,2) → (2,2,2) |
| SIM-066 | (2,2,2) |
| SIM-068 | (1,3,2) → (1,2,2) |
| SIM-070 | (1,2,3) |
| SIM-075 | (3,3,3) |
| SIM-080 | (3,3,3) |
| SIM-084 | (2,2,3) |
| SIM-087 | (1,2,1) |
| SIM-088 | (3,2,0) |
| SIM-091 | (2,2,2) |
| SIM-092 | (1,2,1) |
| SIM-095 | (2,2,2) → (2,2,1) |
| SIM-098 | (2,2,2) |
| SIM-099 | (2,2,2) |

## E09 tokens, latency, cost

- Model calls: 60; per call 1264 in / 557 out
- Latency: P50 8839 ms, P95 10971 ms
- Cost per scoring call: $0.01336; main pass total $0.8014 (prices in `harness/bedrock_client.py`, verify before external use). Load projection: `results/E09_cost_projection.md`.

## E14 fairness proxies (mean predicted minus target stage)

| Writing style | prompting | evaluation | prompt_revision |
|---|---|---|---|
| esl | -0.04 | 0.33 | 0.29 |
| standard | -0.09 | 0.73 | 0.36 |
| verbose | 0.09 | 0.27 | -0.18 |
| informal | -0.5 | 0.25 | 0.62 |
| terse | -0.17 | 0.5 | 0.17 |

| Length band | prompting | evaluation | prompt_revision |
|---|---|---|---|
| long (>180) | -0.14 | 0.39 | 0.23 |
| medium (120-180) | 0.67 | 0.67 | 0.67 |

Needs review: 0. Errors: none. Parse errors: none.
Event log: `results/event_log_run-20261104T004927Z-drift-sonnet45-1473.jsonl`.
