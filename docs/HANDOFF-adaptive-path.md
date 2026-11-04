# Handoff: Adaptive Path for the UI

For: Pratheek (frontend and `webapi/`). From: Kiro-Demo, `proto-branch`.

The engine now chooses what a student does **after** a project, and adds quiz steps. All of it is behind one class, `engine.course.Course`. The current `webapi/service.py` still works unchanged, because `Engine` and `start_workspace` keep their signatures. To get the new behavior, route the service through `Course`.

## What students see

1. They finish a project. The response includes `nextStep`: a sentence on why, plus options. The first option is the recommended one.
2. They pick an option:
   - **`revision`:** a short review project. Step 1 is a quiz, step 2 is a scaffolded coding task.
   - **`next_topic`:** a new topic, such as Lists and Dictionaries.
   - **`new_theme`:** the same topic again in a theme they type in.
   - **`all_done`:** nothing left to start.
3. Concept stages carry across projects. Show all six concepts, not only the ones in the current project.

## Course API

```python
from engine.course import Course
course = Course(data_dir, provider=provider_or_None, adaptive=True)

course.new_student()                          # -> student id
course.state(sid)                             # -> dict, see below (use this for every screen)
course.submit(sid, path_to_code_file)         # -> SubmitOutcome   (code steps)
course.answer(sid, {"q1": 1, "q3": "text"})   # -> SubmitOutcome   (quiz steps)
course.next_step(sid)                         # -> dict or None    (None until the project is complete)
course.start(sid, option_index, theme_request=None)   # -> {"message", "project", "state", ["built"]}
course.build_theme(sid, "pokemon")            # -> {"message", "project", "state", "built"}
course.reset_theme(sid)                       # -> state
```

`CourseError` means a user mistake, such as choosing an option that doesn't exist or leaving out a theme. Show its message. `UnknownStudent` means the ID doesn't exist.

Write the code to the student's workspace file with `engine.cli.start_workspace(data_dir, sid, course.project_for(sid))`, as `service.py` already does.

## `course.state(sid)`

```json
{
  "studentId": "…",
  "project": {"id": "revision-loops", "title": "Review: Loops", "topic": "revision"},
  "complete": false,
  "notices": [],
  "problem": {
    "id": "level-1", "kind": "level", "format": "quiz", "title": "Review Quiz", "label": "Level 1",
    "instructions": "# Review: Loops …",
    "questions": [
      {"id": "q1", "type": "predict", "prompt": "What does this code print?", "code": "total = 0\n…", "choices": ["3", "8", "413"]},
      {"id": "q3", "type": "explain", "prompt": "In your own words, …"}
    ]
  },
  "concepts": [{"id": "loops", "name": "Loops", "stage": 1, "stageName": "Beginning", "inProject": true}, "…"],
  "nextStep": null
}
```

- `problem.format` is `"code"` (show the editor) or `"quiz"` (show the questions; `questions` is null for code).
- Questions never include answers, explanations, or rubrics.
- `problem` is null when `complete` is true. Then `nextStep` is set.

## Quiz answers: `course.answer(sid, answers)`

- `answers` maps each question id to a choice index (int, for `predict`) or text (for `explain`, 1 to 2,000 characters).
- `outcome.question_results` has one entry per question: `{id, type, correct, message, explanation, score, feedback}`.
  - `explanation` is set only after a wrong `predict` answer. Show it: it's how the quiz teaches.
  - `score` (0 to 3) and `feedback` come from the AI rubric grader. Both are null when AI is off or the grader failed. The answer still counts as given.
- A quiz passes when every `predict` is right and every `explain` has an answer. Attempts are unlimited.

## `nextStep`

```json
{
  "kind": "revision",
  "reason": "Database Retrieval took some extra tries, so here's a short review with a few questions to lock it in.",
  "options": [
    {"kind": "revision", "label": "Review Database Retrieval", "project": "revision-database-retrieval", "concept": "database_retrieval", "topic": null},
    {"kind": "next_topic", "label": "Start Lists and Dictionaries", "project": "weather-collections", "concept": null, "topic": "collections"}
  ],
  "evidence": {"database_retrieval": {"level": "struggled", "max_attempts": 4, "total_hints": 3, "practice": true}}
}
```

Show `reason` and a button per option, with `options[0]` highlighted. For a `new_theme` option, ask for the theme text and pass it as `theme_request`. Starting an option resets that project's progress, so a student can redo a review.

## Suggested routes

| Route | Calls |
|---|---|
| `GET /api/students/<id>` | `course.state` |
| `POST /api/students/<id>/submit {code}` | write file, then `course.submit` |
| `POST /api/students/<id>/answer {answers}` | `course.answer` |
| `GET /api/students/<id>/next` | `course.next_step` |
| `POST /api/students/<id>/next {option, theme}` | `course.start` |

## Not done yet

- Revision projects and Lists and Dictionaries use the weather data. Themes still apply only to the first topic.
- The rubric score doesn't change stages yet. The AI grader needs checking against human scores first (Requirement 11).
- The thresholds are in `projects/catalog.yaml`, so they can be changed without code.
