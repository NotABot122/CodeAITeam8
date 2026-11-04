# Diagnostic to lesson, end to end

40 simulated students (diagnosis branch cohort generator, seed 2026) with a known true stage per concept. Each student runs the real diagnostic quest, its handoff, and the lesson through `engine.course.Course` (what the student web API uses), in four conditions with the same random draws. No engine or diagnostic code is changed.

## The handoff standard, checked on today's code

| Check | Requirement | Result | Detail |
|---|---|---|---|
| same_student | The student app opens the student who took the diagnostic. | pass | diagnostic id fa9c6bcc… vs student app rule ^([0-9a-f]{32}|STU-[0-9a-f]{16,32})$ |
| stages_carried | What the diagnostic found (stage per concept) reaches the lesson. | pass | diagnostic {'database_retrieval': 3, 'conditionals': 2, 'loops': 2, 'functions': 0}; confident and used {'database_retrieval': 3, 'loops': 2, 'functions': 0}; lesson starts with {'database_retrieval': 3, 'conditionals': 0, 'loops': 2, 'functions': 0} |
| practice_carried | Every gap the diagnostic found is planned in the lesson, not only the first one. | **fail** | 2 of 40 students: 2 practice problem(s) the quest planned are not in the lesson plan (only gaps the diagnostic is confident about are planned) |
| message_matches | What the student is told comes next is what the lesson starts with. | pass | 0 of 40 students are told a different first stop than the lesson starts with |
| same_grade | The diagnostic and the lesson are written for the same grades. | pass | diagnostic grade band 9-12; lesson tutor and filters are written for high school |
| fails_safe | If the handoff fails, the lesson still starts normally. | pass | handoff applied=False; lesson starts at level-1 |
| no_overwrite | A diagnostic never resets a lesson the student has already started. | pass | the lesson has already started, so it was left as it is |

## What happens in the lesson

| | No diagnostic | No diagnostic, in-lesson help on | Diagnostic handoff | Diagnostic handoff, in-lesson help on | Perfect knowledge, in-lesson help on (upper bound) |
|---|---|---|---|---|---|
| Finished the lesson | 100% | 100% | 100% | 100% | 100% |
| Failed attempts on levels (mean) | 1.7 | 1.7 | 1.35 | 1.35 | 1.23 |
| Submissions to finish (mean) | 5.78 | 5.8 | 5.72 | 5.75 | 5.8 |
| Gaps that got practice before their level | 0% | 0% | 52% | 52% | 86% |
| Practice given where it was not needed | 0 | 0 | 0 | 0 | 0 |
| In-lesson help given (practice inserted) | 0 | 3 | 0 | 1 | 0 |
| Diagnostic overrated a concept (caught in the lesson) | 0 | 0 | 0 | 0 | 0 |

Failed attempts on levels, by the student's true level:

| Student level | No diagnostic | No diagnostic, in-lesson help on | Diagnostic handoff | Diagnostic handoff, in-lesson help on | Perfect knowledge, in-lesson help on (upper bound) |
|---|---|---|---|---|---|
| low | 4 (n=6) | 4 (n=6) | 2.33 (n=6) | 2.33 (n=6) | 1.5 (n=6) |
| middle | 2.07 (n=15) | 2.07 (n=15) | 1.8 (n=15) | 1.8 (n=15) | 1.8 (n=15) |
| high | 0.68 (n=19) | 0.68 (n=19) | 0.68 (n=19) | 0.68 (n=19) | 0.68 (n=19) |

Diagnostic vs. true stage: exact 84%, within one stage 96%, true gaps (stage 0) found 71%. Today's handoff uses 42% of the diagnosed stages (only confident, non-borderline ones); the lesson starts every concept at stage 0 for 22% of students.

## Assumptions

- Learner model: pass chance per attempt {0: 0.2, 1: 0.5, 2: 0.8, 3: 0.95} by true stage, +0.12 per extra attempt, +0.15 on practice problems; passing practice (or a level after struggling) lifts stage 0 to 1. Real students will differ; the comparison between conditions is the point, not the absolute numbers.
- In-lesson help: after 3 failed attempts on a level the engine inserts that concept's practice once and returns to the level (catalog `intervention.struggle_after`).
- The diagnostic quest uses rules only (no model); the simulated children come from `diagnostic/simulation.py`.
