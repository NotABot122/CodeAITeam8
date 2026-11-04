# Diagnostic to lesson, end to end

40 simulated students (diagnosis branch cohort generator, seed 2026) with a known true stage per concept. Each student runs the real diagnostic quest, its handoff, and the lesson through `engine.course.Course` (what the student web API uses), in four conditions with the same random draws. No engine or diagnostic code is changed.

## The handoff standard, checked on today's code

| Check | Requirement | Result | Detail |
|---|---|---|---|
| same_student | The student app opens the student who took the diagnostic. | **fail** | diagnostic id STU-9bd9… vs student app rule ^[0-9a-f]{32}$ |
| stages_carried | What the diagnostic found (stage per concept) reaches the lesson. | pass | diagnostic {'database_retrieval': 3, 'conditionals': 1, 'loops': 2, 'functions': 0}; confident and used {'database_retrieval': 3, 'loops': 2, 'functions': 0}; lesson starts with {'database_retrieval': 3, 'conditionals': 0, 'loops': 2, 'functions': 0} |
| practice_carried | Every gap the diagnostic found is planned in the lesson, not only the first one. | **fail** | 9 of 40 students had practice planned by the diagnostic (10 problems) that the lesson never receives |
| message_matches | What the student is told comes next is what the lesson starts with. | **fail** | 31 of 40 students are told a different first stop than the lesson starts with |
| same_grade | The diagnostic and the lesson are written for the same grades. | **fail** | diagnostic grade band 3-5; lesson tutor and filters are written for high school |
| fails_safe | If the handoff fails, the lesson still starts normally. | pass | handoff applied=False; lesson starts at level-1 |
| no_overwrite | A diagnostic never resets a lesson the student has already started. | pass | the lesson has already started, so it was left as it is |

## What happens in the lesson

| | No diagnostic | Diagnostic, handoff as built today | Diagnostic, proposed handoff | Perfect knowledge of the student (upper bound) |
|---|---|---|---|---|
| Finished the lesson | 100% | 100% | 100% | 100% |
| Failed attempts on levels (mean) | 1.7 | 1.48 | 1.05 | 1.02 |
| Submissions to finish (mean) | 5.78 | 5.5 | 5.33 | 5.3 |
| Gaps that got practice before their level | 0% | 19% | 67% | 86% |
| Practice given where it was not needed | 0 | 0 | 0 | 0 |

Failed attempts on levels, by the student's true level:

| Student level | No diagnostic | Diagnostic, handoff as built today | Diagnostic, proposed handoff | Perfect knowledge of the student (upper bound) |
|---|---|---|---|---|
| low | 4 (n=6) | 3.17 (n=6) | 1.5 (n=6) | 0.83 (n=6) |
| middle | 2.07 (n=15) | 1.8 (n=15) | 1.53 (n=15) | 1.53 (n=15) |
| high | 0.68 (n=19) | 0.68 (n=19) | 0.53 (n=19) | 0.68 (n=19) |

Diagnostic vs. true stage: exact 81%, within one stage 96%, true gaps (stage 0) found 71%. Today's handoff uses 51% of the diagnosed stages (only confident, non-borderline ones); the lesson starts every concept at stage 0 for 20% of students.

## Assumptions

- Learner model: pass chance per attempt {0: 0.2, 1: 0.5, 2: 0.8, 3: 0.95} by true stage, +0.12 per extra attempt, +0.15 on practice problems; passing practice (or a level after struggling) lifts stage 0 to 1. Real students will differ; the comparison between conditions is the point, not the absolute numbers.
- The proposed handoff uses only what exists: the student profile's `concepts` (read by `Course` as initial stages), `apply_placement` for the start problem, and the lesson's own progress record for practice before a level. The engine and diagnostic owners decide how to build it for real.
- The diagnostic quest uses rules only (no model); the simulated children come from `diagnostic/simulation.py`.
