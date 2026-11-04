# Frontend gaps: backend features with no screen yet

**From:** evaluation team (Kiro-Eval) · **For:** Pratheek-Claude (student UI, teacher view, `webapi/`) · **Date:** 2026-11-04 · **Base:** `main` @ `bcebda5`

The backend already produces everything below; the student app and teacher view do not show it yet. Each item lists where the data lives, what to show, and how to check it. Items 1-5 are the teacher view, 6-9 the student app. Items 2, 8 and 9 are about **in-lesson help**, which is now **on by default** (`projects/catalog.yaml` `intervention.struggle_after: 3`): after 3 failed tries on a level, the engine inserts that concept's practice once and then returns the student to the level.

Priority: **P0** for the demo, **P1** soon after.

---

## Teacher view (`webapi/teacher.py`, `frontend/src/teacher/TeacherApp.tsx`)

### 1. Show which stages came from the readiness check (P0)

- **Data:** `GET /api/teacher/students/<id>` already returns `seededFromQuest` (`{concept: stage}`), from `profile["diagnostic"]["seeded"]`.
- **Gap:** not rendered. A teacher cannot tell a stage the student earned in the lesson from one the readiness check gave them.
- **Show:** next to each concept's stage, a small "from readiness check" tag when the concept is in `seededFromQuest`. In the readiness section, list the concepts the check found but did not use, with the reason (`profile["diagnostic"]["decisions"][c]["reason"]`, e.g. "stage 1 rests on 1 correct answer; 2 are needed").
- **Done when:** a student who took the check shows the tag on exactly the seeded concepts.

### 2. Show planned practice and in-lesson help (P0)

- **Data:**
  - `profile["planned_practice"] = {"project": id, "problems": [practice ids]}`, written by `Course.apply_diagnostic` for every gap the check is confident about.
  - Event log (`.codeai-data/logs/events.jsonl`) rows with `"event": "intervention"` and `reason` = `struggle_practice` (practice inserted after repeated failures on a level) or `diagnostic_mismatch` (the check rated the concept above 0, the student struggled, the stage was reset to 0).
  - In-lesson help is on by default (`intervention.struggle_after: 3` in `projects/catalog.yaml`; `null` turns it off).
- **Gap:** the teacher API returns none of this.
- **Backend (small):** add `plannedPractice` (titles, done/not done) and `interventions` (`[{problemId, practiceId, reason, at}]`, read from the event log for this student) to `Teacher.student()`. Add a count of `diagnostic_mismatch` per concept to `Teacher.overview()`.
- **Show:** in the student detail, "Planned practice" and "Extra help given" lists. In the class overview, a column or badge "Readiness check overrated" per concept. This is the most useful signal for a teacher: where the check overrates students.
- Also: `needsHelp` in the overview counts tries on the *current* step. With in-lesson help on, a stuck student moves to practice and the count restarts, so the overview can miss them. Count failed tries on the level the student will return to (`ProgressRecord.return_to`) as well.
- **Done when:** a student who fails Level 1 three times shows one "Extra help given" entry; if Level 1's concept had a seeded stage, the overview counts one mismatch for that concept.

### 3. Translate route reasons into plain words (P0)

- **Data:** `projects[].route[].reason` is shown raw (`Path: practice-db-count (planned_practice) → level-1 (back_to_level)`).
- **Show a label per reason:**

| reason | label |
|---|---|
| `next_level` | Next level |
| `practice_assigned` | Practice after a level |
| `planned_practice` | Planned practice (readiness check) |
| `struggle_practice` | Extra practice after repeated tries |
| `back_to_level` | Back to the level |
| `diagnostic_placement` | Start set by the readiness check |
| `fallback_next_level` | Standard path (fallback) |
| `no_practice_remaining` | Next level (no practice left) |
| `project_complete` | Finished |

- Show problem titles instead of ids (`selected` → title from the project).
- **Done when:** no raw reason code or problem id is visible on the teacher screen.

### 4. Show completed projects (P1)

- **Data:** `completed` (`[{project, topic, at}]`) is returned but not rendered.
- **Show:** a "Completed projects" list with dates in the student detail.

### 5. Teacher token for the demo (P0, config)

- The teacher routes return 401 unless `CODEAI_TEACHER_TOKEN` is set when `webapi.server` starts. Set it for the demo and document it in `frontend/README.md` (e.g. `CODEAI_TEACHER_TOKEN=demo python -m webapi.server ...`).

---

## Student app (`frontend/src/quest/`, `frontend/src/App.tsx`)

### 6. Readiness check result: show "next stop" and the goal link (P1)

- **Data:** the final quest step returns `next_stop` (`{zone, activity: {id, title}}`) and `goal_connection` (text), besides `message` and `skill_tree`.
- **Gap:** only `message` and the skill tree are shown.
- **Show:** a "You will start with: <activity title>" card and the `goal_connection` sentence above the "Start the project" button. `next_stop` now always matches the lesson's real first problem.
- **Done when:** the card shows the same problem the lesson opens on.

### 7. Hints on request, and how many are left (P1, needs a small backend route)

- **Data:** every problem in the state has `hintCount` and `hintsSeen`. Hints are only shown after a failed run today.
- **Backend:** add `POST /api/students/<id>/hint` that returns the next authored hint for the current problem and increments `hintsSeen` (the engine already has `engine.feedback.next_hint`). Hints used already lower the Stage 3 criterion, so asking for one has a real cost. Show that honestly ("Using a hint is fine; it counts toward how this level is scored.").
- **Show:** a "Hint (2 left)" button next to Run.
- **Done when:** the button is disabled when `hintsSeen == hintCount`, and the hint counter in the teacher view goes up.

---

### 8. In-lesson help: keep the level visible on the path while the student practices (P0)

- **Data:** while the inserted practice is open, the progress record has `return_to = "level-1"` (the level to go back to). `GET /api/students/<id>` builds `path` with `_status_of()` in `webapi/service.py`, which reports that level as `todo`.
- **Gap:** `PathStrip` draws `todo` as a locked circle, so the level the student was just working on looks locked.
- **Backend (small):** in `_status_of`, return `"paused"` when `problem_id == record.return_to`.
- **Show:** a paused level as in progress (current color, no lock, a small "back after practice" caption). The practice pill already sits after its level via `afterLevelId`.
- **Done when:** after 3 failed tries on Level 1, the path shows Level 1 as paused and the practice as current; after the practice passes, Level 1 is current again.

### 9. In-lesson help: say why, and where the student goes next (P0)

- **Data:** the failed-submit outcome carries the notice "Let's warm up with a short practice problem, then come back to this level." and the new state's `problem` is the practice. The routing log reason is `struggle_practice`.
- **Gap:** the app shows that notice *and* `PracticeDialog`, whose text ("Pass it and you'll head straight back to the main path") is written for practice after a passed level.
- **Show:** one message, not two. When the practice was inserted after repeated tries, the dialog says something like "This one's tricky, so let's practice the idea first: <practice title>. Then you'll come back to <level title>." Keep the student's level work: the workspace is one file for every problem, so after the practice the editor shows the practice code, not their last try on the level (checked: `state.code` on return is the last submitted file). Save a draft per problem (for example in `localStorage`, keyed by student and problem id) and restore it when the student returns to the level.
- **Backend (small):** add `inserted: "after_level" | "struggle" | "planned"` to the problem payload (from the last routing reason), so the UI does not have to guess.
- **Done when:** the student sees one dialog naming the level they will return to, and the editor shows their last try on that level when they return.

## Not needed in the UI

- Author tools: `engine.cli generate-data`, `generate-expected`, `check-content`; `diagnostic.cli show-item`, `export-rubric`, `tree`.
- `diagnostic/api.py` is a separate FastAPI layer that `webapi/` does not use; it duplicates the quest routes. Suggest removing it later.

## How to check

```bash
CODEAI_AI=off CODEAI_TEACHER_TOKEN=demo python -m webapi.server --port 8081 --ai off
python -m unittest discover -s tests -t .     # 255 tests pass on main @ bcebda5
python -m evaluation.harness.diag_lesson_eval  # readiness check -> lesson, 40 simulated students
```

Background and numbers: `evaluation/DIAGNOSTIC_LESSON_STANDARD.md`, `evaluation/results/diag_lesson_report.md`.
