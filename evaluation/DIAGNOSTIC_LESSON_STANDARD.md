# Diagnostic → lesson handoff standard (draft v0.1)

**Goal.** Any student can take the readiness diagnostic and start the adaptive lesson at their own level, with no teacher in between.

This page lists what the handoff must do, who owns each part, and the automated check for it. The checks run in `harness/diag_lesson_eval.py` (40 simulated students through the real quest, `Course.apply_diagnostic` and the lesson); results are in `results/diag_lesson_report.md`. The evaluation team writes and runs the checks; the owners change their code. Nothing here changes engine, diagnostic or student-app code.

## Requirements

| Check | Requirement | Why | Owner | Status (2026-11-04, after fixes) |
|---|---|---|---|---|
| `same_student` | The student app opens the student who took the diagnostic: one student id format across `diagnostic/`, `engine/` and `webapi/`. | Today the app rejects diagnostic ids (`STU-…` vs. 32 hex characters) and starts a new student, so the diagnostic result is lost. | Diagnostic + student app | pass: one 32-hex id across quest, lesson and app |
| `stages_carried` | The stage per concept found by the diagnostic reaches the lesson. The engine already supports this: `Course` reads the profile's `concepts` as `Engine(initial_stages=…)`. | Without it the lesson treats every student as stage 0 on every concept. | Engine (`Course.apply_diagnostic`) | pass: confident stages with at least 2 correct answers are used |
| `practice_carried` | Every gap the diagnostic found is planned in the lesson, not only the first one (`practice_ahead`). | Today only the start problem is handed over; later gaps are found again the hard way, through failed attempts. | Diagnostic + engine (router needs a "practice before this level" input) | by design: 2 of 40 students: 2 practice problem(s) the quest planned are not in the lesson plan (only gaps the diagnostic is confident about are planned) |
| `message_matches` | What the student is told comes next ("next stop") is what the lesson starts with. | Today the quest can name one zone while the lesson starts with another concept. | Diagnostic | pass: next stop names where the lesson starts |
| `same_grade` | The diagnostic and the lesson are written for the same grade band. | The diagnostic is built for grades 3-5; the lesson, tutor prompts and filters are written for high school (Vision: grades 9-12). | Team decision | pass: diagnostic rewritten for grades 9-12 |
| `fails_safe` | If the diagnostic or handoff fails, the lesson still starts normally at the first level. | Customer requirement: fall back to a working non-adaptive path. | Diagnostic (passes today) | pass |
| `no_overwrite` | A diagnostic never resets a lesson the student has already started. | Protects student work. | Diagnostic (passes today) | pass |

## Outcome targets (measured with simulated students, then a pilot)

| Measure | Target (proposal) |
|---|---|
| Diagnosed gaps that get practice before their level | ≥ 80% |
| Failed attempts on levels, low-level students | at most half of the no-diagnostic condition |
| Practice given where it was not needed (true stage ≥ 2) | close to 0 |
| Students who finish the lesson, in every level band | 100% |
| Diagnostic finds true gaps (true stage 0 reported as 0) | ≥ 80%, then confirmed against teacher ratings |

## Decisions the team needs to make

1. **Grade band.** Rewrite the diagnostic for high school, or target a grades 3-5 lesson. The handoff cannot be judged fair until both sides target the same students.
2. **Stage meaning.** The diagnostic's stage comes from the hardest question tier passed; the lesson's stage comes from attempts and hints on a pass. Both should map to the stage descriptors in `documentation/resources/concept_learning_trajectories_draft.md`, or state clearly that they do not.
3. **Depth for strong students.** The Vision asks that advanced students go deeper on the same objectives. Today a stage-3 student does the same four levels as everyone else; the handoff could unlock extension problems instead of skipping levels.
4. **Where the handoff lives.** Proposed: the diagnostic writes the student profile (`concepts`, planned practice) through the lesson's store; the engine router reads planned practice. The owners decide.

## Result so far (simulated students)

Failed attempts on levels for students who start low: no diagnostic 4, diagnostic 2.33, diagnostic with in-lesson help 2.33, perfect knowledge 1.5. Diagnosed gaps that get practice before their level: 52% (perfect knowledge 86%). See `results/diag_lesson_report.md`; the learner model is an assumption.

## In-lesson help (new)

`projects/catalog.yaml` `intervention.struggle_after` (off by default): after that many failed attempts on a level, the engine inserts the concept's practice once and returns to the level. If the diagnostic had rated the concept above 0, that rating is dropped and a `diagnostic_mismatch` event is logged, which gives live evidence of where the diagnostic overrates students.
