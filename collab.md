# Collaboration & Agent Tracking (collab.md)

Welcome to the vibe-coding coordination hub! 🚀
Every autonomous agent or developer **MUST read this file before writing code** to understand ongoing work, avoid duplicate efforts, and coordinate state cleanly.

---

## ⚡ Agent Guidelines & Rules of Engagement

> 👑 **Lead / Authoritative Agent Role (Antigravity):**
> Antigravity acts as the authoritative lead agent for implementation directly on main with atomic, verified commits. When a feature is complex or carries architectural regression risk, Antigravity will branch off (e.g., eat/<feature-name>), verify end-to-end, and merge back to main.


1. **Before Starting Any Task:**
   - Review the **Active Agent Status Table** below to ensure no collision on targeted modules/files.
   - Set your Agent status to `working` with your exact task objective and target model.
   - Review recent entries in the **LRU Task History** to maintain continuity.
   - **MANDATORY Documentation Diff-Check:** Periodically run a diff check on the documentation/ folder (e.g. git diff documentation/) to remain fully aware of evolving specifications, standards, and architecture changes made by teammate agents beyond this file.
2. **While Working:**
   - Commit atomic, verifiable changes.
   - Do not overwrite active files assigned to other agents.
3. **When Finishing a Task:**
   - Mark your status back to `idle`.
   - Prepend your completed task into the **LRU History (Previous 10 Tasks)** below.
   - Maintain strict LRU bounds (keep exactly the last 10 tasks, evicting the oldest).

---

## 🤖 Active Agent Status Table

| Agent ID | Current Model | Status (`idle` / `working`) | Current Task / Focus Area | Started At (Timestamp) |
|---|---|---|---|---|
| `Agent-Bootstrap` | Gemini 3.8 Flash | `idle` | Integrated curriculum database references, added post-project AI reteach loop, created COURSE_FLOW_GRAPH.md, initialized git repository and committed all files | 2026-11-03 15:21 PST |
| `Pratheek-Claude` | Claude Sonnet 5.5 | `idle` | Student "My course" page (`GET /api/students/<id>/course`, `frontend/src/ui/CoursePage.tsx`) | 2026-11-04 13:30 PST |
| `Agent-3` | Unassigned | `idle` | None | - |
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Text/Blocks editor toggle (Python ↔ Blockly, `webapi/blocks.py` + `frontend/src/blocks/`) and per-problem function bank (`functions.yaml`, `ui/FunctionBank.tsx`); on local branch `feat/blocks-function-bank`, not pushed | 2026-11-04 12:15 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Merged `diagnosis` into `proto-branch` and connected the readiness quest to `Course` (confident stages seed the profile; placement sets the first problem) | 2026-11-04 12:05 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Kiro-Eval` | Claude Opus 5.5 (Kiro) | `idle` | Evaluated the proto engine against the customer requirements (E01/E07/E08/E12, AgentCore Evaluations) and built the Evaluation Console (`evaluation/`) | 2026-11-04 10:45 PST |
| `Kiro-Diagnostic` | Claude Sonnet 5.5 (Kiro) | `idle` | Built the gamified grade 3-5 Weather Station readiness diagnostic (`diagnostic/`, `projects/weather-station/diagnostic/`, additive `evaluation/` files) on the `diagnosis` branch | 2026-11-04 |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 020] Student "My Course" Page**
   - **Agent:** `Pratheek-Claude`
   - **Date:** 2026-11-04 13:30 PST
   - **Summary:** Added the whole-course view for students. New `Service.course_view` and `GET /api/students/<id>/course` (topics done / current / upcoming, six ideas with stage, finished reviews, what the quest seeded, next-step reason). Frontend: `ui/CoursePage.tsx`, a "My course" button in the lesson header, `getCourse` in the client. Tests: `test_course_view_tracks_topics_and_reviews`, a render test; tsc, vitest and build pass. No engine changes.
2. **[Task 019] Text/Blocks Editor Toggle & Per-Problem Function Bank**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 12:15 PST
   - **Summary:** A Text | Blocks toggle above the student editor. Blocks mode uses Blockly 13 (lazy-loaded chunk). `POST /api/blocks` (`webapi/blocks.py`) parses and compiles the student's Python (never runs it) into blocks; a syntax error or anything blocks can't show yet (class, lambda, f-string, try, with, default args, chained comparisons) gives an empty workspace plus the line and reason. Blocks → Python runs in the browser (`frontend/src/blocks/python.ts`); text stays untouched until a block is edited, and comments survive. Round trip gives the same Python AST for every starter and reference solution. Text mode gets a function bank on the toolbox side (`ui/FunctionBank.tsx`), with a popup per function, from new per-problem `functions.yaml` files (all 19 code problems); `check-content` fails if a bank lists something the reference solution doesn't use. Themed (AI-built) projects have no bank yet.
3. **[Task 018] Teacher View: Class Overview, Student Detail, Content Check**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 13:10 PST
   - **Summary:** New `webapi/teacher.py` and screens at `/#/teacher`. Class overview (in the quest, coding, finished, needs help), a stacked bar per idea showing where the class stands, a student list that flags 4+ tries, 2+ hints or the fixed-order fallback, a student detail (stages, per-project tries and hints, routing path, and the readiness quest's teacher report with the child's own words and any content-filter holds), and a button that runs the lesson and quest content checks. Read-only. Needs `CODEAI_TEACHER_TOKEN` on the server; unset means the routes return 403. Routes: `GET /api/teacher/overview`, `/api/teacher/students/<id>`, `/api/teacher/content-check`. Engine and `diagnostic/` untouched. Not done: classes or rosters (students are listed together), the evaluation console stays its own app, demo scripts stay in the terminal.
4. **[Task 017] Readiness Quest as the Front Page of the Student UI**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 12:40 PST
   - **Summary:** Merged `main` into `frontend`. The site now opens on the readiness quest (buddy and goal picks, zone bar, XP/rank/badges, tap, order and sort questions, optional typed "explain" step, feedback with tips, skill map at the end). A "Skip to coding" link starts a lesson-only student. When the quest ends, its result is applied through `Course` and the student lands in the lesson at the placement. A refresh resumes a half-finished quest. New `webapi/` routes: `GET /api/quest/options`, `POST /api/quest`, `GET /api/quest/<id>/next`, `POST /api/quest/<id>/answer`, `POST /api/quest/<id>/finish`. Ordering and sorting use buttons, not drag. The free-text goal is not offered. Seeded stages show in the concept meters, still an open design question (see the handoff doc). Engine and `diagnostic/` untouched. Browser run: full quest, hand-off, reload.
5. **[Task 017] Gamified Grade 3-5 Readiness Diagnostic for the Weather Station Lesson**
   - **Model:** Claude Sonnet 5.5 (Kiro)
   - **Agent:** `Kiro-Diagnostic`
   - **Timestamp:** 2026-11-04
   - **Summary:** Added `diagnostic/` on the `diagnosis` branch (merged `proto-branch` and `evaluation-plan` first). A tap-and-drag quest tests the four prerequisite ideas under the lesson (retrieval, conditionals, loops, functions). Answers are scored by a guess-and-slip model (a stage 0-3 and a real confidence per concept) over a poly-hierarchy skill tree. An optional model, through `engine.ai`, gets the evidence, the goal and the tree and may move a stage by one only with the child's own words as proof; Bedrock is untested live (offline mock model). The quest places the student and can set the lesson's starting problem through the lesson engine's own records (`diagnostic.cli handoff --apply`). Evaluation: implements `validate_submission` and `route_next`, writes the event log, schema v0.2 (additive), `evaluation/harness/run_diag_eval.py` (10 hard requirements pass on the mock), and an MCP hook. Students never see stages or scores. 214 tests pass (69 original plus 145 new). Not done: real-model runs, human-rated E01 benchmark, CSTA codes for grades 3-5, K-2 support. See `diagnostic/README.md`.
6. **[Task 018] Readiness Diagnostic Connected to the Adaptive Path**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Demo`
   - **Timestamp:** 2026-11-04 12:05 PST
   - **Summary:** Merged `diagnosis` (Task 014, Kiro-Diagnostic) into `proto-branch`. The only conflict was `collab.md`, kept from both sides, with the diagnostic entry renumbered 014. `Course` now wraps the quest (`diagnostic_start/answer/next/finish`). When a quest ends, `apply_diagnostic` seeds the profile with every concept the quest is confident about (confidence 0.8 or higher, not borderline; set in `projects/catalog.yaml`) and starts the lesson at the quest's placement. A lesson that has already started keeps its place. **@Kiro-Diagnostic:** this changes your "never seed a stage" rule at the user's request. `diagnostic/` itself is unchanged, and the seeding lives in `engine/course.py`. CLI: `engine.cli placement --student STU-...`. 237 tests pass (87 + 145 + 5). **@Pratheek:** diagnostic methods added to `docs/HANDOFF-adaptive-path.md`. Open question: the quest targets grades 3 to 5, the lessons grades 9 to 12.
7. **[Task 015] Student UI on the Adaptive Path (Course, Quizzes, Next Step)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 11:35 PST
   - **Summary:** `webapi/service.py` now goes through `engine.course.Course` as in `docs/HANDOFF-adaptive-path.md`; new routes `POST /answer`, `GET/POST /next`. The UI shows quiz steps (predict choices, explain text, explanations after wrong answers), a "what's next" screen with the recommended option first and a theme box for `new_theme`, and all six concepts (ones outside the project dimmed). Layout: a compact level path (practice problems show as a badge on their level) with a sideways-scrolling "What you're learning" row beside it, and the editor fills the right side. Engine untouched. 95 Python tests, 7 vitest tests, typecheck and build pass; clicked through Weather Station, the next-step screen and a review quiz in a browser. Not done: rubric score doesn't affect stages (engine side), no demo mode without the API.
8. **[Task 016] Evaluation of the Proto Engine & Evaluation Console**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Eval`
   - **Timestamp:** 2026-11-04 10:45 PST
   - **Summary:** Merged `proto-branch` and `evaluation-plan` into `main` (engine code unchanged). Added read-only evaluation of the proto engine in `evaluation/harness/proto_*.py`: E01 grader vs. a draft human key (26 submissions: agreement 0.92, kappa 0.84, 2 false passes), E07 fallback under 12 injected faults (9/12 finish; unexpected grader / AI-hint exceptions escape `Engine.submit`, a persistently unavailable grader has no fallback), E08 input/output filtering (48 theme requests, 16 hint texts: input catch 1.0 but 29% false blocks; output check misses answers given in prose), E12 hint quality (36 AI + 36 teacher hints; judge says 75% of AI and 53% of teacher hints give the answer), scored with an LLM judge and AgentCore Evaluations (custom evaluator on spans built by the harness, no Runtime). Added the Evaluation Console (`evaluation/console/`, React 18 / MUI 7, served by `python -m evaluation.harness.console_server`): requirement-by-requirement evidence, live grading / filtering / hint scoring, and blind human rating. Judge not yet validated against teachers; E01 key is a draft.
9. **[Task 013] Adaptive Path Across Projects (Profile, Next Step, Revision Quizzes)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Demo`
   - **Timestamp:** 2026-11-04 10:40 PST
   - **Summary:** After each project, `engine/course.py` judges every concept as strong, steady, or struggled from attempts, hints, and practice problems. The thresholds are in `projects/catalog.yaml`. Struggled sends the student to a revision project for the weakest concept: a quiz with predict-the-output questions checked automatically, an explain answer scored by the Bedrock rubric, then a scaffolded coding task. All strong sends them to the topic with the lowest mastery. Steady offers a new theme or the next topic. A per-student profile carries concept stages across projects. New content: topic 2 `projects/weather-collections` (Lists & Dictionaries) and six `projects/revision-*`. The content check also runs every quiz snippet. CLI: `next`, `answer`. Demo: `python3 -m engine.path_demo [--offline]`. 87 tests pass. **@Pratheek:** UI handoff in `docs/HANDOFF-adaptive-path.md`. The current `webapi/service.py` still works unchanged (verified). Route it through `Course` for the new screens.
10. **[Task 014] Student UI on the Weather Station Engine (CodeAI styling)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 10:20 PST
   - **Summary:** Added `webapi/` (stdlib JSON server over `engine.session`: new student, state, submit, theme, theme reset; serves `frontend/dist`) and replaced the earlier mock-data scaffold in `frontend/` with screens for the real engine: level path with assigned practice problems, Python editor, instructions renderer, grader messages and hints (AI vs teacher-written), Missing/Beginning/Meeting/Exceeding meters, "quick practice" pop-up, theme dialog, completion screen. Styled after Code.org's CodeAI (design reference only, see `frontend/NOTICE-codeorg.md`). Engine code untouched. Run: `python -m webapi.server --ai off`, then `cd frontend && npm run build`. 75 Python tests, 5 vitest tests, typecheck and build pass; clicked through all 4 levels in a browser against the real engine. Not done: demo mode without the API, CodeMirror, telemetry endpoint.
