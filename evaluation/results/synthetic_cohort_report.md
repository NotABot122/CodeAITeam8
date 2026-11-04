# Synthetic cohort report: `sim-seed8-n100`

- Students: 100 (from `data/mock_students.json`), seed 8
- Lesson budget: 12 tasks (~45 min); mastery = Stage 2 on every sub-skill
- Simulated grader noise: 0.67 exact, 0.97 within one stage (from the first harness run)
- Simulated validation failure rate per call: 0.03

> **Everything here is simulated.** The learning model and the `agent` policy are assumptions written by the evaluation workstream. These tables check that the E04 / E06 / E07 / telemetry analyses run end to end; they say nothing about whether a real policy works.

## E06 routing policy comparison (same cohort, 4 policies)

| Policy | Mastered in budget | Median steps to mastery | Declared complete | Declared complete too early | Wasted steps / student | Repeats / student | A-B-A-B loops / student |
|---|---|---|---|---|---|---|---|
| stage_rules | 0.51 | 3 | 0.93 | 0.44 | 0.76 | 1.63 | 0.11 |
| agent | 0.5 | 4.0 | 0.83 | 0.33 | 1.22 | 1.48 | 0.05 |
| fixed_order | 0.35 | 6 | 0.57 | 0.22 | 3.83 | 0 | 0 |
| random | 0.24 | 4.0 | 0.49 | 0.27 | 3.79 | 0.59 | 0.06 |

Wasted = a task at or below the student's true stage. Declared complete too early = the observed stages reached mastery because of grader noise while the true stages had not.

## E07 fallback (validation failure → next step from the authored order)

| Policy | Validation failures | Students affected | Fallback steps | Stages reset after failure | Mastered rate of affected students |
|---|---|---|---|---|---|
| stage_rules | 4 | 4 | 4 | 0 | 0.75 |
| agent | 17 | 14 | 17 | 0 | 0.286 |
| fixed_order | 35 | 28 | 32 | 0 | 0.25 |
| random | 21 | 18 | 20 | 0 | 0.111 |

## E05 lesson funnel (agent policy, observed stages from the event log)

| Task | Attempts | Observed stage went up | Rate | Failed calls |
|---|---|---|---|---|
| C3-L6-E1 | 91 | 49 | 0.538 | 1 |
| C3-L6-E2 | 68 | 37 | 0.544 | 4 |
| C3-L6-E3 | 1 | 1 | 1.0 | 0 |
| C3-L6-P1 | 88 | 49 | 0.557 | 3 |
| C3-L6-P2 | 105 | 51 | 0.486 | 5 |
| C3-L6-P3 | 3 | 1 | 0.333 | 0 |
| C3-L6-R1 | 77 | 46 | 0.597 | 1 |
| C3-L6-R2 | 44 | 24 | 0.545 | 0 |
| C3-L6-R3 | 1 | 1 | 1.0 | 0 |
| C3-L6-X1 | 101 | 62 | 0.614 | 3 |

Share of students whose highest observed stage reached each level (Stage 3 column = Stage 3 evidence coverage):

| Sub-skill | ≥ 1 | ≥ 2 | ≥ 3 |
|---|---|---|---|
| prompting | 1.0 | 1.0 | 0.582 |
| evaluation | 1.0 | 0.923 | 0.516 |
| prompt_revision | 1.0 | 0.879 | 0.352 |

## E04 pre / post / unaided transfer (adaptive = agent policy, control = fixed order)

| Group | Sub-skill | Pre | Post | Transfer | Gain (post) | Gain (transfer) |
|---|---|---|---|---|---|---|
| adaptive (n=50) | prompting | 1.58 | 2.28 | 1.94 | 0.7 | 0.36 |
| adaptive (n=50) | evaluation | 1.46 | 2.1 | 2.1 | 0.64 | 0.64 |
| adaptive (n=50) | prompt_revision | 1.22 | 1.86 | 1.58 | 0.64 | 0.36 |
| control (n=50) | prompting | 1.4 | 1.82 | 1.66 | 0.42 | 0.26 |
| control (n=50) | evaluation | 1.24 | 1.96 | 2.06 | 0.72 | 0.82 |
| control (n=50) | prompt_revision | 1.48 | 1.94 | 1.9 | 0.46 | 0.42 |

Transfer gain, adaptive minus control (mean over sub-skills): -0.05 stages (standardized -0.08). A real pilot of this size is reported descriptively as a protocol check, not as an efficacy claim.

## Lesson-mode telemetry: baseline proactive-hint trigger

Rule under test: idle ≥ 60 s within 3 events of an error, or the same error 3 times in a row; 120 s cooldown. Ground truth = simulated stuck episodes.

| Sessions | Stuck episodes | Detected | Episode recall | Trigger precision | False triggers / session | Median detection delay (s) |
|---|---|---|---|---|---|---|
| 100 | 97 | 72 | 0.742 | 0.766 | 0.39 | 132.5 |
