# CodeAI Adaptive Engine: Weather Station Demo

A Python prototype of an adaptive lesson. Students write four functions against a synthetic weather database. The engine grades each submission, tracks a stage (0 Missing to 3 Exceeding) for each concept, and picks the next problem. Students who need more practice get a practice problem before moving on. Everyone finishes on the same final level. If routing breaks, the lesson continues in a fixed order.

Needs Python 3.9 or later and PyYAML. The core lesson runs without cloud access. Themes and AI hints use Amazon Bedrock and need boto3 (see below).

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

## Pick your own theme (Amazon Bedrock)

Students can ask for the same project in a theme they like. The concepts, levels, and checks stay the same; only the story, names, and data change.

```bash
python3 -m engine.cli theme --student ID "I love pokemon, can my project be a pokedex?"
python3 -m engine.cli theme --student ID --reset      # back to the weather project
python3 -m engine.theme_demo "Minecraft mobs"         # presentation demo (add --offline without network)
```

What happens:

1. The request is screened: local word and personal-information rules, then a separate Bedrock moderation call. Anything inappropriate is refused with a friendly message.
2. Bedrock designs the theme through a forced tool call. It only picks names, words, and number ranges, such as a `pokedex` table with `region`, `attack`, and `speed`.
3. The engine validates every identifier (it ends up in SQL and Python) and filters all student-visible text. If the spec is invalid, the model gets up to two retries with the errors listed.
4. The engine generates the data, the tests, and the reference solution from templates, then runs the content check. Only a project that passes reaches the student. Otherwise the student keeps the weather project.

In live testing, 17 of 18 themes passed. The one failure was a scale problem that is now fixed in the request schema. Builds take 4 to 16 seconds. Real franchise names are used for the demo, but the stats are made up. Using trademarked names in production needs a decision.

## AI tutor hints (Amazon Bedrock)

When a check fails, Bedrock writes one hint about the student's actual mistake. The model sees the level instructions, the failing checks, the teacher-written hints, and the student's code. It never sees the reference solution or the student id. A hint is rejected if it contains code, copies the reference solution, is too long, or fails the content filter. Student code with personal information is never sent. Any rejection or model error falls back to the teacher-written hint.

Settings: `--ai off` (or `CODEAI_AI=off`) turns both AI features off. `CODEAI_MODEL_ID` changes the model (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`). `CODEAI_AWS_REGION` changes the region (default `us-west-2`). Needs `pip install --user boto3` and AWS credentials. Each hint or theme event is logged in `.codeai-data/logs/events.jsonl` with its source and model.

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

- AI rubric grading of written answers and the grader-agreement benchmark (requirements 10 and 11).
- Bedrock Guardrails. The content filter is local rules plus a model moderation call; AI hints get the local rules only.
- Stages don't carry over between projects: a themed project starts every concept at Stage 0.
- Student code runs in a separate process with a time limit and its own database copy, but not in a security sandbox. It's fine for a demo, but not for untrusted code in production.

The spec is in `.kiro/specs/weather-station-adaptive-lesson/`.
