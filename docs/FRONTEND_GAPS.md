# Frontend gaps: backend features with no screen yet

**From:** evaluation team (Kiro-Eval) · **For:** Pratheek-Claude (student UI, teacher view, `webapi/`) · **Date:** 2026-11-04 · **Base:** `main` @ `bcebda5`

The backend already produces everything below; the student app and teacher view do not show it yet. Each item lists where the data lives, what to show, and how to check it. Items 1-5 are the teacher view, 6-7 the student app. Nothing here changes grading or routing.

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
  - In-lesson help is off by default; turn it on with `intervention.struggle_after: 3` in `projects/catalog.yaml`.
- **Gap:** the teacher API returns none of this.
- **Backend (small):** add `plannedPractice` (titles, done/not done) and `interventions` (`[{problemId, practiceId, reason, at}]`, read from the event log for this student) to `Teacher.student()`. Add a count of `diagnostic_mismatch` per concept to `Teacher.overview()`.
- **Show:** in the student detail, "Planned practice" and "Extra help given" lists. In the class overview, a column or badge "Readiness check overrated" per concept. This is the most useful signal for a teacher: where the check overrates students.
- **Done when:** with `struggle_after: 3`, a student who fails Level 1 three times shows one "Extra help given" entry; if Level 1's concept had a seeded stage, the overview counts one mismatch for that concept.

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
