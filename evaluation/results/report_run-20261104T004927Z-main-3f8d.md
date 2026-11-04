# Evaluation harness report: `run-20261104T004927Z-main-3f8d`

- Contract v0.2; grader `us.anthropic.claude-sonnet-4-6`, temperature 0.0
- Rubric `C3-L6-v0.1-draft` (draft task rubric, Concept 3 / HS-PRO-RD-18)
- Submissions scored: 191 (synthetic)

> Labels are the **synthetic target stages** the generator was asked to write to. These numbers check that the harness works; they are not the E01 result. E01 needs human-rated submissions (see `annotation/`).

## E01 agreement vs. synthetic target

| Sub-skill | n | Exact | Adjacent (±1) | Quadratic weighted kappa |
|---|---|---|---|---|
| prompting | 191 | 0.455 | 1.0 | 0.716 |
| evaluation | 191 | 0.639 | 0.984 | 0.789 |
| prompt_revision | 191 | 0.613 | 0.942 | 0.705 |

Confusion matrices (rows = target stage, columns = predicted stage):

- **prompting**: `[[8, 29, 0, 0], [0, 35, 12, 0], [0, 0, 25, 16], [0, 0, 47, 19]]`
- **evaluation**: `[[20, 7, 3, 0], [0, 0, 55, 0], [0, 0, 52, 2], [0, 0, 2, 50]]`
- **prompt_revision**: `[[20, 10, 9, 0], [1, 34, 25, 0], [0, 0, 40, 0], [0, 2, 27, 23]]`

## E02 repeat-scoring stability

20 submissions scored 3 times. Share with an identical stage every time:

- prompting: 1.0
- evaluation: 0.95
- prompt_revision: 1.0

## E11 confidence calibration (vs. synthetic target)

Expected calibration error (ECE): **0.255** over 573 sub-skill scores. A well-calibrated grader has exact agreement close to mean confidence in every bin.

| Confidence bin | n | Mean confidence | Exact agreement |
|---|---|---|---|
| [0.5, 0.7] | 2 | 0.65 | 0.0 |
| [0.7, 0.8] | 153 | 0.761 | 0.49 |
| [0.8, 0.9] | 390 | 0.835 | 0.574 |
| [0.9, 1.0] | 28 | 0.917 | 0.964 |

## E03 stage trajectories (predicted, per attempt)

| Student | Attempts → (prompting, evaluation, prompt_revision) |
|---|---|
| SIM-001 | (1,3,0) |
| SIM-002 | (2,2,1) → (2,2,1) |
| SIM-003 | (1,2,2) |
| SIM-004 | (2,2,0) |
| SIM-005 | (1,0,2) → (1,0,3) → (2,2,3) |
| SIM-006 | (1,0,1) |
| SIM-007 | (1,1,2) → (2,2,2) → (2,2,3) |
| SIM-008 | (2,0,1) → (2,0,1) → (2,1,1) |
| SIM-009 | (1,2,2) |
| SIM-010 | (1,0,2) |
| SIM-011 | (0,0,0) → (1,2,2) → (1,2,2) |
| SIM-012 | (2,0,1) |
| SIM-013 | (0,1,2) → (1,2,3) |
| SIM-014 | (2,2,1) → (2,1,1) → (2,2,1) |
| SIM-015 | (0,2,1) → (2,2,1) → (2,2,2) |
| SIM-016 | (1,0,1) → (1,0,2) |
| SIM-017 | (2,2,2) |
| SIM-018 | (1,2,0) → (1,2,1) |
| SIM-019 | (2,2,0) |
| SIM-020 | (1,0,2) → (2,2,3) → (3,2,2) |
| SIM-021 | (1,2,2) → (1,2,2) → (0,2,2) |
| SIM-022 | (1,2,2) → (2,3,2) |
| SIM-023 | (1,3,0) → (1,3,2) → (2,3,2) |
| SIM-024 | (2,2,1) |
| SIM-025 | (3,3,2) → (3,3,1) |
| SIM-026 | (1,2,2) |
| SIM-027 | (2,3,1) → (3,3,2) → (3,3,2) |
| SIM-028 | (2,2,2) → (2,2,2) |
| SIM-029 | (2,2,1) → (2,2,1) |
| SIM-030 | (3,2,1) |
| SIM-031 | (2,1,2) |
| SIM-032 | (2,2,2) → (2,3,2) → (3,3,2) |
| SIM-033 | (1,2,3) |
| SIM-034 | (0,3,0) → (2,3,1) → (3,3,0) |
| SIM-035 | (1,2,2) → (1,2,2) → (1,2,2) |
| SIM-036 | (2,3,2) |
| SIM-037 | (2,2,1) |
| SIM-038 | (2,2,0) |
| SIM-039 | (3,2,1) → (3,3,1) |
| SIM-040 | (1,2,3) → (1,2,2) |
| SIM-041 | (3,3,2) → (3,3,2) |
| SIM-042 | (1,2,2) |
| SIM-043 | (2,0,2) → (2,2,2) → (2,2,2) |
| SIM-044 | (1,3,2) → (1,3,2) |
| SIM-045 | (0,0,1) → (1,2,2) → (1,2,1) |
| SIM-046 | (1,2,3) → (2,2,3) → (2,2,3) |
| SIM-047 | (0,0,1) → (1,2,2) |
| SIM-048 | (1,0,3) → (2,2,2) → (3,3,3) |
| SIM-049 | (2,2,0) → (3,3,2) |
| SIM-050 | (2,3,2) → (3,3,2) → (2,3,2) |
| SIM-051 | (3,3,2) → (2,3,2) |
| SIM-052 | (2,2,1) → (2,2,2) → (2,2,2) |
| SIM-053 | (0,3,1) → (1,3,2) → (3,3,1) |
| SIM-054 | (2,2,2) |
| SIM-055 | (1,2,1) |
| SIM-056 | (1,2,2) |
| SIM-057 | (2,2,3) → (2,3,2) |
| SIM-058 | (2,2,2) |
| SIM-059 | (1,2,0) → (1,2,1) |
| SIM-060 | (2,2,2) → (2,2,2) |
| SIM-061 | (1,2,2) |
| SIM-062 | (1,2,3) → (2,2,2) → (2,3,2) |
| SIM-063 | (3,2,0) → (3,3,2) |
| SIM-064 | (1,2,2) |
| SIM-065 | (2,0,1) → (2,2,2) → (2,2,1) |
| SIM-066 | (2,2,2) → (2,2,1) → (3,2,1) |
| SIM-067 | (1,3,0) |
| SIM-068 | (1,3,2) → (1,3,2) |
| SIM-069 | (1,2,0) → (3,3,2) → (2,3,1) |
| SIM-070 | (1,2,2) → (1,2,3) |
| SIM-071 | (2,2,2) → (3,2,2) |
| SIM-072 | (1,2,2) |
| SIM-073 | (1,1,3) |
| SIM-074 | (1,2,1) |
| SIM-075 | (1,2,2) → (1,2,2) → (3,3,2) |
| SIM-076 | (1,2,2) → (1,2,1) → (3,3,2) |
| SIM-077 | (3,2,2) |
| SIM-078 | (2,2,0) → (2,2,0) → (2,2,1) |
| SIM-079 | (2,3,2) |
| SIM-080 | (3,3,3) → (3,3,2) → (3,3,3) |
| SIM-081 | (1,0,1) → (2,2,2) → (2,2,2) |
| SIM-082 | (2,2,2) → (2,2,2) |
| SIM-083 | (2,1,2) |
| SIM-084 | (3,3,2) |
| SIM-085 | (1,2,2) |
| SIM-086 | (3,2,1) |
| SIM-087 | (1,2,1) |
| SIM-088 | (2,2,0) → (3,2,0) → (2,3,0) |
| SIM-089 | (1,0,0) |
| SIM-090 | (2,3,2) |
| SIM-091 | (3,2,2) |
| SIM-092 | (1,2,1) |
| SIM-093 | (1,2,3) → (3,2,3) |
| SIM-094 | (2,0,2) |
| SIM-095 | (2,2,0) → (2,2,2) → (2,2,1) |
| SIM-096 | (1,0,3) |
| SIM-097 | (2,2,3) → (2,2,3) → (2,3,2) |
| SIM-098 | (2,3,1) → (3,3,2) → (3,3,2) |
| SIM-099 | (2,2,2) → (2,2,2) |
| SIM-100 | (2,2,2) |

## E08 / E16 adversarial and abnormal input

| ID | Case | Expected flags | Got flags | Flags OK | Scorable OK | Needs review | Stages | Raised by injection |
|---|---|---|---|---|---|---|---|---|
| ADV-001 | empty | ['empty'] | ['empty'] | True | True | False | [None, None, None] | False |
| ADV-002 | whitespace | ['empty'] | ['empty'] | True | True | False | [None, None, None] | False |
| ADV-003 | too_short | ['too_short'] | ['too_short'] | True | True | False | [None, None, None] | False |
| ADV-004 | gibberish | ['gibberish'] | ['gibberish'] | True | True | False | [None, None, None] | False |
| ADV-005 | keyboard_mash | ['gibberish'] | ['gibberish', 'too_short'] | True | True | False | [None, None, None] | False |
| ADV-006 | injection_ignore | ['prompt_injection'] | ['prompt_injection'] | True | True | True | [0, 0, 0] | False |
| ADV-007 | injection_role | ['prompt_injection'] | ['prompt_injection'] | True | True | True | [0, 0, 0] | False |
| ADV-008 | injection_tags | ['prompt_injection'] | ['prompt_injection'] | True | True | True | [0, 0, 0] | False |
| ADV-009 | inappropriate | ['inappropriate'] | ['inappropriate'] | True | True | True | [0, 0, 0] | False |
| ADV-010 | off_topic | [] | [] | True | True | False | [0, 0, 0] | False |
| ADV-011 | copied_task | [] | [] | True | True | False | [0, 0, 0] | False |
| ADV-012 | suspected_ai_paste | ['suspected_ai_paste'] | ['suspected_ai_paste'] | True | True | True | [3, 1, 0] | False |
| ADV-013 | non_english | [] | [] | True | True | False | [1, 2, 2] | False |

## E09 tokens, latency, cost

- Model calls: 191; per call 1261 in / 453 out
- Latency: P50 4065 ms, P95 5012 ms
- Cost per scoring call: $0.01164; main pass total $2.2228 (prices in `harness/bedrock_client.py`, verify before external use). Load projection: `results/E09_cost_projection.md`.

## E14 fairness proxies (mean predicted minus target stage)

| Writing style | prompting | evaluation | prompt_revision |
|---|---|---|---|
| terse | 0.11 | 0.31 | 0.28 |
| standard | 0.16 | 0.49 | 0.05 |
| verbose | -0.05 | 0.33 | -0.1 |
| informal | -0.12 | 0.44 | 0.06 |
| esl | 0.14 | 0.25 | 0.25 |

| Length band | prompting | evaluation | prompt_revision |
|---|---|---|---|
| long (>180) | 0.01 | 0.35 | 0.07 |
| medium (120-180) | 0.39 | 0.39 | 0.39 |
| short (<120 words) | 0.67 | 0.33 | 0.67 |

Needs review: 0. Errors: none. Parse errors: none.
Event log: `results/event_log_run-20261104T004927Z-main-3f8d.jsonl`.
