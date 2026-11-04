# E04 learning-effect study protocol (draft v0.1)

Owner: evaluation workstream. Status: draft for team and T&L review. This is a **protocol**, not an efficacy claim: with a hackathon-sized cohort we report descriptive numbers only.

## Question

Does the adaptive path (validation + `route_next` with the adaptive policy) produce more **unaided** learning on Concept 3 (CSTA HS-PRO-RD-18) than the non-adaptive fallback path, in the same lesson time?

## Design

| Element | Choice | Why |
| --- | --- | --- |
| Conditions | **Adaptive**: routing policy `agent` (Stance Decider) or `stage_rules`. **Control**: the non-adaptive fallback (`fixed_order`), which the MVP already requires. | The fallback path is a ready-made control; no extra content is needed. |
| Assignment | Randomize students within each class, 1:1, stratified by pre-test band (low: mean stage < 1, mid: 1–2, high: ≥ 2). | Balances prior skill across groups within a small sample. |
| Time | Same time budget in both groups: one lesson, about 45 minutes (12 tasks max). | Prevents "more time" from looking like "better routing". |
| Pre-test | Task C3-L6-T1 form A, scored with `validate_submission`, before the lesson. | Same rubric as the outcome. |
| Post-test | Parallel form B, right after the lesson, with the in-lesson AI hints **off**. | Measures the end state, not assisted performance. |
| Transfer (primary outcome) | Parallel form C on a new context (e.g. a school club sign-up page instead of the magazine home page), unaided, same rubric. Ideally a few days later. | "Performance while the AI helps is not learning." Transfer is the measure the router cannot game. |
| Form order | Counterbalance forms B and C across students if forms are not yet shown to be equivalent. | Controls for form difficulty. |

Parallel forms must be written and checked by T&L before the study: same rubric, same sub-skill demands, different wireframe and AI-output mismatches.

## Outcomes and analysis

Primary: transfer gain = transfer stage − pre stage, averaged over the three sub-skills, per student.

Secondary: post gain per sub-skill; share of students reaching Stage 2 on all sub-skills; minutes used; hint count; E07 fallback events.

Report for each condition: n, mean and median of each outcome, the distribution (stage counts), and the difference between conditions with a bootstrap 95% interval. Report a standardized difference only as a descriptive number. No significance claim from the hackathon pilot.

The analysis pipeline already runs end to end on simulated data: `python -m evaluation.harness.cohort_sim` → `data/prepost_synthetic.jsonl` and the E04 table in `results/synthetic_cohort_report.md`.

## Sample size (for a later real study, not the pilot)

Detecting a difference of 0.3 stages on a gain with SD ≈ 0.8 at 80% power and α = 0.05 needs about 110 students per group. The hackathon pilot will be far below that; state this in any report.

## Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Grader noise looks like learning or regression | Use the same grader version for pre, post, and transfer; report E02 stability next to the result. Prefer human-scored transfer items if T&L can score them. |
| Router tuned to raise stages without teaching | Transfer is unaided and on a new context. |
| Contamination (students in both groups share answers) | Randomize within class but keep forms B and C hidden until the post-test window. |
| Students feel tested (formative principle) | Students see feedback only, never stages. Pre/post are framed as practice. |
| Novelty effect | Report as a limitation; a later study runs over a full unit. |

## Ethics and data

- No PII: pseudonymous `STU-` IDs; the key linking IDs to students stays with the teacher.
- Teacher and district consent per CodeAI policy; students can opt out with no effect on grades.
- Event log rows follow `schemas/event_log.schema.json`; retained only for the evaluation period.

## Sign-off needed

1. T&L: parallel forms B and C, and whether transfer is scored by humans or the grader.
2. Teammates: a switch that forces a student into the fallback path (control) without it being logged as a failure.
3. Staff: whether a classroom pilot is possible during the hackathon at all, or whether E04 stays a protocol.
