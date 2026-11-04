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
| `Pratheek-Claude` | Claude Sonnet 5.5 | `idle` | Hexagon skill tree on My course (`frontend/src/ui/SkillTree.tsx`) | 2026-11-04 14:50 PST |
| `Agent-3` | Unassigned | `idle` | None | - |
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Text/Blocks editor toggle (Python ↔ Blockly, `webapi/blocks.py` + `frontend/src/blocks/`) and per-problem function bank (`functions.yaml`, `ui/FunctionBank.tsx`); on local branch `feat/blocks-function-bank`, not pushed | 2026-11-04 12:15 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Merged `diagnosis` into `proto-branch` and connected the readiness quest to `Course` (confident stages seed the profile; placement sets the first problem) | 2026-11-04 12:05 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Kiro-Eval` | Claude Opus 5.5 (Kiro) | `idle` | Evaluated the proto engine against the customer requirements (E01/E07/E08/E12, AgentCore Evaluations) and built the Evaluation Console (`evaluation/`) | 2026-11-04 10:45 PST |
| `Kiro-Diagnostic` | Claude Sonnet 5.5 (Kiro) | `idle` | Built the gamified grade 3-5 Weather Station readiness diagnostic (`diagnostic/`, `projects/weather-station/diagnostic/`, additive `evaluation/` files) on the `diagnosis` branch | 2026-11-04 |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 023] Hexagon Skill Tree on the My Course Page**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 14:50 PST
   - **Summary:** The six ideas are now a honeycomb skill tree (`frontend/src/ui/SkillTree.tsx`), a mix of CodeAI's honeycomb progression map and a game skill tree: hex per idea coloured by stage, glowing paths between ideas the student has reached, an orange pulsing hex with Ducky on the idea they are working on, "Learned!" ribbons, locked hexes, and a panel with a one-line description when a hex is clicked. It replaces the idea meters on My course. The unlock order (database retrieval, then conditionals and loops, then functions, lists, dictionaries) is a layout constant in the component, not engine data; change it there. `GET /api/students/<id>/course` concepts now include `inProject`. 11 API tests and 9 frontend tests pass.
2. **[Task 022] Ducky the Rubber Duck Replaces the Hint Lightbulb**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 14:30 PST
   - **Summary:** Team name is Rubber Ducky, so the AI helper now has a mascot. New `frontend/src/ui/RubberDuck.tsx` (inline SVG, fixed colours) replaces the lightbulb in the hint box in `ui/Results.tsx`, and the hint label reads "Hint from Ducky" (or "Hint from Ducky, your AI tutor" when the hint is AI-written). No API or engine changes.
3. **[Task 021] Teacher View Works Behind a Proxy Prefix**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 13:50 PST
   - **Summary:** The teacher page called `/api/teacher/...` at the site root and ignored `VITE_API_BASE_URL`, so it failed when the app was served under a prefix such as `/proxy/8090/`. It now uses the same base as the student client. One line in `frontend/src/teacher/TeacherApp.tsx`. Thanks to whoever found it. Build with `VITE_API_BASE_URL=/proxy/8090` when serving under a prefix.
4. **[Task 020] Student "My Course" Page**
   - **Agent:** `Pratheek-Claude`
   - **Date:** 2026-11-04 13:30 PST
   - **Summary:** Added the whole-course view for students. New `Service.course_view` and `GET /api/students/<id>/course` (topics done / current / upcoming, six ideas with stage, finished reviews, what the quest seeded, next-step reason). Frontend: `ui/CoursePage.tsx`, a "My course" button in the lesson header, `getCourse` in the client. Tests: `test_course_view_tracks_topics_and_reviews`, a render test; tsc, vitest and build pass. No engine changes.
5. **[Task 019] Text/Blocks Editor Toggle & Per-Problem Function Bank**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 12:15 PST
   - **Summary:** A Text | Blocks toggle above the student editor. Blocks mode uses Blockly 13 (lazy-loaded chunk). `POST /api/blocks` (`webapi/blocks.py`) parses and compiles the student's Python (never runs it) into blocks; a syntax error or anything blocks can't show yet (class, lambda, f-string, try, with, default args, chained comparisons) gives an empty workspace plus the line and reason. Blocks → Python runs in the browser (`frontend/src/blocks/python.ts`); text stays untouched until a block is edited, and comments survive. Round trip gives the same Python AST for every starter and reference solution. Text mode gets a function bank on the toolbox side (`ui/FunctionBank.tsx`), with a popup per function, from new per-problem `functions.yaml` files (all 19 code problems); `check-content` fails if a bank lists something the reference solution doesn't use. Themed (AI-built) projects have no bank yet.
6. **[Task 018] Teacher View: Class Overview, Student Detail, Content Check**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 13:10 PST
   - **Summary:** New `webapi/teacher.py` and screens at `/#/teacher`. Class overview (in the quest, coding, finished, needs help), a stacked bar per idea showing where the class stands, a student list that flags 4+ tries, 2+ hints or the fixed-order fallback, a student detail (stages, per-project tries and hints, routing path, and the readiness quest's teacher report with the child's own words and any content-filter holds), and a button that runs the lesson and quest content checks. Read-only. Needs `CODEAI_TEACHER_TOKEN` on the server; unset means the routes return 403. Routes: `GET /api/teacher/overview`, `/api/teacher/students/<id>`, `/api/teacher/content-check`. Engine and `diagnostic/` untouched. Not done: classes or rosters (students are listed together), the evaluation console stays its own app, demo scripts stay in the terminal.
7. **[Task 017] Readiness Quest as the Front Page of the Student UI**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 12:40 PST
   - **Summary:** Merged `main` into `frontend`. The site now opens on the readiness quest (buddy and goal picks, zone bar, XP/rank/badges, tap, order and sort questions, optional typed "explain" step, feedback with tips, skill map at the end). A "Skip to coding" link starts a lesson-only student. When the quest ends, its result is applied through `Course` and the student lands in the lesson at the placement. A refresh resumes a half-finished quest. New `webapi/` routes: `GET /api/quest/options`, `POST /api/quest`, `GET /api/quest/<id>/next`, `POST /api/quest/<id>/answer`, `POST /api/quest/<id>/finish`. Ordering and sorting use buttons, not drag. The free-text goal is not offered. Seeded stages show in the concept meters, still an open design question (see the handoff doc). Engine and `diagnostic/` untouched. Browser run: full quest, hand-off, reload.
8. **[Task 017] Gamified Grade 3-5 Readiness Diagnostic for the Weather Station Lesson**
   - **Model:** Claude Sonnet 5.5 (Kiro)
   - **Agent:** `Kiro-Diagnostic`
   - **Timestamp:** 2026-11-04
   - **Summary:** Added `diagnostic/` on the `diagnosis` branch (merged `proto-branch` and `evaluation-plan` first). A tap-and-drag quest tests the four prerequisite ideas under the lesson (retrieval, conditionals, loops, functions). Answers are scored by a guess-and-slip model (a stage 0-3 and a real confidence per concept) over a poly-hierarchy skill tree. An optional model, through `engine.ai`, gets the evidence, the goal and the tree and may move a stage by one only with the child's own words as proof; Bedrock is untested live (offline mock model). The quest places the student and can set the lesson's starting problem through the lesson engine's own records (`diagnostic.cli handoff --apply`). Evaluation: implements `validate_submission` and `route_next`, writes the event log, schema v0.2 (additive), `evaluation/harness/run_diag_eval.py` (10 hard requirements pass on the mock), and an MCP hook. Students never see stages or scores. 214 tests pass (69 original plus 145 new). Not done: real-model runs, human-rated E01 benchmark, CSTA codes for grades 3-5, K-2 support. See `diagnostic/README.md`.
9. **[Task 018] Readiness Diagnostic Connected to the Adaptive Path**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Demo`
   - **Timestamp:** 2026-11-04 12:05 PST
   - **Summary:** Merged `diagnosis` (Task 014, Kiro-Diagnostic) into `proto-branch`. The only conflict was `collab.md`, kept from both sides, with the diagnostic entry renumbered 014. `Course` now wraps the quest (`diagnostic_start/answer/next/finish`). When a quest ends, `apply_diagnostic` seeds the profile with every concept the quest is confident about (confidence 0.8 or higher, not borderline; set in `projects/catalog.yaml`) and starts the lesson at the quest's placement. A lesson that has already started keeps its place. **@Kiro-Diagnostic:** this changes your "never seed a stage" rule at the user's request. `diagnostic/` itself is unchanged, and the seeding lives in `engine/course.py`. CLI: `engine.cli placement --student STU-...`. 237 tests pass (87 + 145 + 5). **@Pratheek:** diagnostic methods added to `docs/HANDOFF-adaptive-path.md`. Open question: the quest targets grades 3 to 5, the lessons grades 9 to 12.
10. **[Task 015] Student UI on the Adaptive Path (Course, Quizzes, Next Step)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 11:35 PST
   - **Summary:** `webapi/service.py` now goes through `engine.course.Course` as in `docs/HANDOFF-adaptive-path.md`; new routes `POST /answer`, `GET/POST /next`. The UI shows quiz steps (predict choices, explain text, explanations after wrong answers), a "what's next" screen with the recommended option first and a theme box for `new_theme`, and all six concepts (ones outside the project dimmed). Layout: a compact level path (practice problems show as a badge on their level) with a sideways-scrolling "What you're learning" row beside it, and the editor fills the right side. Engine untouched. 95 Python tests, 7 vitest tests, typecheck and build pass; clicked through Weather Station, the next-step screen and a review quiz in a browser. Not done: rubric score doesn't affect stages (engine side), no demo mode without the API.
