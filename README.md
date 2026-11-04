# CodeAI Adaptive Engine: Weather Station Demo

A Python prototype of an adaptive lesson. Students write four functions against a synthetic weather database. The engine grades each submission, tracks a stage (0 Missing to 3 Exceeding) for each concept, and picks the next problem. Students who need more practice get a practice problem before moving on. Everyone finishes on the same final level. If routing breaks, the lesson continues in a fixed order.

Needs Python 3.9 or later and PyYAML. No cloud access is needed.

## Run the demo

```bash
python3 -m engine.demo
```

This runs three scripted students through the project:

| Student | What happens |
|---|---|
| Strong | Passes each level on the first try: Level 1 → 2 → 3 → 4 |
| Struggling | Needs four tries on Level 1, so the engine assigns a practice problem first. Later breaks the Level 3 loop rule once |
| Router failure | Routing is made to fail after Level 1. The engine logs it and continues in fixed order |

## Try it as a student

```bash
python3 -m engine.cli new                       # prints your id and the file to edit
python3 -m engine.cli submit   --student ID     # grade your file
python3 -m engine.cli show     --student ID     # current instructions
python3 -m engine.cli progress --student ID     # stages and levels passed
```

Add `--no-adaptive` before the command to use the fixed level order. Progress is saved in `.codeai-data/`.

## The lesson

| Level | Function | Concept |
|---|---|---|
| 1 | `get_readings(conn, station_id, start_date, end_date)`: parameterized SQL query | Database Retrieval |
| 2 | `classify_day(row)`: heat wave at 35.0 °C or more, heavy rain at 20.0 mm or more | Conditionals |
| 3 | `summarize(readings)`: counts, totals, and maximum, using a loop and no `sum`, `max`, `min`, `len`, or `sorted` | Loops |
| 4 | `build_report(...)`: combines the three functions above | Functions |

How adaptivity works: a passed problem counts toward the next stage when it took few enough attempts (Stage 1: 3 or fewer, Stage 2: 2 or fewer, Stage 3: first try with no hints). A student must reach Stage 1 on a concept to move past its level. A student who doesn't gets a practice problem for that concept. The rules are in `projects/weather-station/manifest.yaml`.

## For curriculum authors

```bash
python3 -m engine.cli check-content       # the reference passes every check; stored answers match
python3 -m engine.cli generate-expected   # recompute stored answers (marks them unreviewed)
python3 -m engine.cli generate-data       # rebuild the database from its seed
python3 -m unittest discover -s tests -t .
```

A project is a folder under `projects/` with `manifest.yaml`, `dataset/`, `levels/`, `practice/`, and `reference/`. Each problem folder has `instructions.md`, `hints.yaml`, and `checks.py`. A new project with the same layout runs without engine changes.

Expected answers are computed by a separate SQL checker (`reference/independent_checker.py`) and are marked `teacher_reviewed: false` until a teacher checks them.

## Not in this demo yet

- AI grading of written answers through Amazon Bedrock, the content filter, and the grader-agreement benchmark (requirements 10–12).
- Student code runs in a separate process with a time limit and its own database copy, but not in a security sandbox. It's fine for a demo, but not for untrusted code in production.

The spec is in `.kiro/specs/weather-station-adaptive-lesson/`.
