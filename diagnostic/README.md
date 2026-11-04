# Weather Station readiness check (grades 9-12)

A short tap-and-drag check that finds out where a high school student stands on the four ideas the
[Weather Station lesson](../projects/weather-station/) is built on: **finding information in a log**
(`database_retrieval`), **if/else decisions** (`conditionals`), **repeating** (`loops`) and
**reusable helpers** (`functions`). It scores answers by fixed rules, then (optionally) asks a
language model to read the evidence, the student's goal and the skill tree, and to suggest where the
student should start.

Needs Python 3.9+ and PyYAML. No cloud access, no other packages. Run everything from the repository root.

## Try it

```bash
python3 -m diagnostic.cli play                     # play it yourself in the terminal
python3 -m diagnostic.cli play --profile mixed     # watch a simulated child (strong, middle, mixed, struggling, guesser)
python3 -m diagnostic.cli --ai mock play --profile mixed --teacher   # also use the offline model, print the teacher report
python3 -m diagnostic.cli check-content            # validate the questions, skill tree and settings
python3 -m diagnostic.cli tree                     # print the skill tree
python3 -m diagnostic.cli handoff --student ID --apply   # start that student's Weather Station lesson in the right place
python3 -m unittest discover -s tests -t .         # the whole test suite (original lesson tests and these)
python3 -m evaluation.harness.run_diag_eval        # the evaluation harness, offline
```

`--ai` is `off` (default: rules only), `mock` (offline stand-in model) or `bedrock` (needs `boto3` and AWS credentials; also
set with `$CODEAI_AI`). Where things are stored and which project is used come from `--data-dir` / `--project` or
`$CODEAI_DATA_DIR` / `$CODEAI_PROJECT`; the defaults are `.codeai-data/` and `projects/weather-station/`.

## How a quest works

```
 pick a buddy + goal (taps)
        │
        ▼
 for each zone (one per concept):   ladder of questions, tier 1 → 3
        │   pass: go up a tier        miss: one "twin" question; two misses end the zone
        │   (a breather question appears after several misses in a row)
        ▼
 "tell the guide" (typed, optional): only where the answers leave real doubt, at most two per quest
        ▼
 bonus round: re-check big claims (stage ≥ 2) whose confidence is still low
        ▼
 DETERMINISTIC RESULT  ── stage 0-3 and a confidence per concept, skill-tree status per node
        ▼
 MODEL (optional)      ── reads evidence + goal + tree; may move a stage by ONE, only with the child's own words as proof
        ▼
 PLACEMENT             ── where to start, what to practice first, a kind message for the child, a note for the teacher
```

Typical length is 12-16 scored questions, about 14 minutes. A pass at tier N is evidence for Stage N.

**The stage estimate.** Each answer is evidence under a guess-and-slip model: a child at stage *s* passes a tier-*t* question
with probability 1 − slip if *s* ≥ *t*, and with that question's own guess chance otherwise (4 options → 25%). The reported stage
is the most likely one and the confidence is its probability. Lucky guesses, ties and the bonus round all fall out of this one
rule (`scoring.py`). Slip and prior live in `diagnostic.yaml`.

**The skill tree** (`tree.yaml`) is a DAG with multi-parent nodes (`count_with_rule` needs a decision skill *and* a repeating
skill). A node is `LOCKED` until every parent is passed, then `AVAILABLE`, then `MASTERED`.

**Never block the student.** If choosing the next question fails, the quest continues in a fixed order. If the model is down or
answers badly, the deterministic placement is used. Both are logged with `fallback_triggered`.

**What students see and what teachers see.** Students get XP, a rank, badges, a streak and a guide: never stages, scores,
confidence or answer keys. `DiagnosticEngine._student()` checks every student payload and refuses to return one that leaks. Teachers
get `teacher_report()`: stages, confidence, mistakes, the child's own words, the AI's changes, and the placement.

## Layout

| Module | One job |
|---|---|
| `paths.py` | Where things live (repo-relative, env-overridable). Nothing is hard-coded to a machine. |
| `models.py` | Plain data types: items, nodes, results, rules. |
| `content.py` | Load and validate `<project>/diagnostic/`; reports every problem in one pass. |
| `tree.py` | The skill-tree DAG and its status rules. |
| `scoring.py` | One answer → credit; many answers → stage and confidence; node points. |
| `selector.py` | Pick the next question (pure function of the saved state); fixed-order fallback. |
| `safety.py` | Input prefilter (kid-tuned) and output filter. Shares word lists with `engine.safety`. |
| `textmatch.py` | Typo-tolerant key-idea matching for written answers. |
| `ai/` | Prompts, strict output parsing, the readers, the offline mock model, a response cache. Providers come from `engine.ai`. |
| `placement.py` | Evidence + advice → placement. The bounded merge lives here. |
| `game.py`, `views.py` | XP, badges, the guide's words; everything a student's screen receives. |
| `report.py` | The teacher report. |
| `contract.py`, `eval_log.py`, `schema_check.py`, `tool_server.py` | The evaluation team's `validate_submission` tool, event-log rows, a dependency-free schema checker, and the MCP hook. |
| `store.py`, `state.py`, `handoff.py` | Saving a quest; the saved shape; handing the student to `python -m engine.cli`. |
| `engine.py` | `DiagnosticEngine`: the orchestrator. Every public method returns a JSON-ready dict. |
| `simulation.py` | Simulated children for tests, the demo and the harness. |
| `cli.py`, `render.py`, `api.py` | Terminal, text rendering, and the optional HTTP layer. |

Content lives with the project, not the code: `projects/weather-station/diagnostic/` has `diagnostic.yaml` (limits, thresholds,
scoring, goals, game text), `tree.yaml`, `items/<concept>.yaml` and `boosters.yaml`.

## Writing or changing questions

Edit the YAML, then run `python3 -m diagnostic.cli check-content`. It enforces: exactly one right option, a misconception tag on every
wrong option, at least two questions per concept and tier (a first question and a twin), every tree node targeted by a question, the
primary node matching the question's zone and tier, reading level (sentence and word length), and no stage/score words in anything a
student reads. `python3 -m diagnostic.cli show-item ID --answer` previews a question.

Add the CSTA codes to `tree.yaml` (`csta:`) once checked against `curriculum database/CSTA_2026_PK12_Standards_by_Grade.xlsx`.
They are empty on purpose until verified. If you change the "tell the guide" prompts, regenerate the rubric:
`python3 -m diagnostic.cli export-rubric` (a test fails if it is out of date).

A different project needs its own `<project>/diagnostic/` folder whose zones match the manifest's concepts.
Select it with `--project` or `$CODEAI_PROJECT`.

## Using a model

Providers are `engine.ai` classes. `bedrock` uses `engine.ai.BedrockProvider` (model and region: `CODEAI_MODEL_ID`, `CODEAI_AWS_REGION`).
The model is asked by a forced tool call (structured output), with `maxTokens` always set, and:

- the child's words reach it only as escaped text between `<student_submission>` tags, and the prompt says that text is data;
- every claim is checked before use: stage is a whole number 0-3, quotes must appear in the child's words, the concept list must be complete;
- a stage change is applied only if it is one stage, a quote supports it, and the child wrote something;
- its wording for the child must pass the output filter (no scores, no markup, kid reading level), or fixed text is used;
- an unscorable answer (empty, gibberish, injection, personal details, severe language) never reaches it.

Nothing here has been run against a real model yet. The mock model (`--ai mock`) exercises the whole path offline but says nothing
about real-model quality.

## Evaluation

The diagnostic implements the evaluation team's contracts (`evaluation/`), and `evaluation/harness/run_diag_eval.py` checks it:

```bash
python3 -m evaluation.harness.run_diag_eval                 # offline mock model; writes evaluation/results/diag_*
python3 -m evaluation.harness.run_diag_eval --provider bedrock   # real model (boto3 + AWS)
python3 -m evaluation.harness.run_diag_eval --benchmark evaluation/data/diag_benchmark/ratings.csv   # human-rated E01 / E10
```

| Contract | How the diagnostic meets it |
|---|---|
| `validate_submission` | `contract.py`; one result for the concept a "tell the guide" prompt targets; `null` stage + a flag for unscorable input; every stage has a quote from the child's words; also served by `evaluation/harness/mcp_server.py` for rubric `WS-DIAG-v0.1-draft`. |
| `route_next` | `placement.Route` has exactly the contract's fields, including the `STANCE_*` values. |
| Event log | `eval_log.py`; one row per tool call, ids marked `STU-` (log only), no student text beyond the contract's quotes, goal never logged. |
| Hard requirements (standard §2.6) | 0 parse errors, 100% of empty/gibberish/too-short answers null, 0 injection cases at stage 3, all checked in the run. |

Schema **v0.2** (additive, so Concept 3 data still validates): four more `subskill` values, a `personal_info` filter flag,
an optional `stages` object in the event log, and `cost_usd` may be `null` (the harness already writes it that way).

What the report does and does not show: agreement with *simulated* children checks that the pipeline recovers the stage the simulator
chose. It is **not** the E01 result and overstates real agreement. E01 needs answers written by real children and rated by two
people (`evaluation/data/diag_benchmark/README.md`).

## Optional HTTP API

```bash
pip install -r diagnostic/requirements-api.txt
uvicorn diagnostic.api:create_default_app --factory
```

Routes under `/api/v1/diagnostic`: `options`, `start`, `{id}/next`, `{id}/answer`, `{id}/finish`, `{id}/result`, `{id}/skill_tree`,
and `teacher/{id}/report`. The teacher route is off unless `CODEAI_TEACHER_TOKEN` is set, then needs it in `X-Teacher-Token`.
Put authentication, TLS and rate limiting in front of it before any real use: student ids are unguessable pseudonyms, not credentials.

## Privacy

No names are collected: the nickname is a pick from a list. The optional goal text is screened; personal details cause it to be
dropped. Student ids are 32 random hex characters, the same format as the lesson engine and the student app (the event log marks them `STU-`). The goal text and written answers are saved in the student's own record and never
written to the event logs (apart from the short quotes the evaluation contract requires). Real answers for the benchmark go in a git-ignored file.

## Known limits

- The check and the lesson both target grades 9-12. The questions read SQL and Python the way the lesson writes it; reading level and timing are assumptions until a pilot with real students.
- `seconds_per_item` and `seconds_per_explain` in `diagnostic.yaml` are assumptions. Time a real class and update them.
- Stage estimates rest on 3-4 questions per concept, so adjacent-stage errors are expected; the confidence says how much to trust each one.
- The question bank is a first draft (24 questions) written for review by Teaching & Learning staff; wording and misconception tags
  should be reviewed. Variants shift a child's stage sometimes (the harness reports this as "quest variant sensitivity").
- Pre-reader (K-2) support, audio, and image-based questions are not built.
- The server keeps no session lock: two clients driving one student at once can overwrite each other.
