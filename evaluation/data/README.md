# Evaluation data (all synthetic)

Every file here is generated. None of it comes from real students, and none of it should be used to report E01 agreement or any efficacy number. Student IDs start with `SIM-` (simulated) or `ADV-` (adversarial).

| File | Rows | Generator | Model calls | Used for |
| --- | --- | --- | --- | --- |
| `mock_students.json` | 100 profiles | `harness/simulate.py` | no | Shared student IDs for every set below |
| `mock_submissions.jsonl` | one per attempt, 1-3 per student | `harness/simulate.py` | yes (Haiku 4.5 writes the text) | Harness debugging, E02, E03, E09, E14 proxy |
| `adversarial_set.jsonl` | 13 | `harness/simulate.py` | no (hand-written) | E08, E16 |
| `routing_sim_events.jsonl` | event-log rows | `harness/cohort_sim.py` | no | E06 policy comparison, E07 fallback |
| `prepost_synthetic.jsonl` | one per student | `harness/cohort_sim.py` | no | E04 analysis pipeline (pre / post / unaided transfer) |
| `telemetry_synthetic.jsonl` | editor events | `harness/cohort_sim.py` | no | Testing proactive-hint triggers in lesson mode |

## Students

- SIM-001 to SIM-020: start stages weighted toward Stage 0-1, like a typical class.
- SIM-021 to SIM-100: uniform start stages (`start_weights: uniform`), added to fill thin cells such as Stage 3.
- Writing style (`terse`, `standard`, `verbose`, `informal`, `esl`) rotates across students; it is the fairness proxy for E14.
- The task targets CSTA 2026 **HS-PRO-RD-18** (builds on MS-PRO-RD-17). See `../rubrics/concept3_task_rubric.json`.

## What the labels mean

- `target_stage` in `mock_submissions.jsonl` is the stage the generator was told to write at. It is not a human rating.
- The `sim` block in the cohort files holds simulated ground truth (true stage, stuck episodes). Real data will not have it.
- The learning model, the `agent` routing policy, and the telemetry behavior in `cohort_sim.py` are assumptions made by the evaluation workstream. They exist so the analyses can be built and tested before the real routing and lesson services exist.

## Regenerate

```bash
python -m evaluation.harness.simulate --students 20 --seed 8                                  # SIM-001..020
python -m evaluation.harness.simulate --students 80 --seed 21 --append --start-weights uniform # SIM-021..100
python -m evaluation.harness.cohort_sim --seed 8                                               # cohort sets + report
```
