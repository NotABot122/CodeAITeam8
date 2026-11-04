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
| `Pratheek-Claude` | Claude Sonnet 5.5 | `idle` | Game-style readiness-quest inputs (tap the rows, sorting belt, word chips) via a `display` option on sort items | 2026-11-04 15:20 PST |
| `Agent-3` | Unassigned | `idle` | None | - |
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Slow-down timer for rushed answers (Task 024), project choice (Task 023), adaptive support (Task 022) on branch `feat/adaptive-help`, committed; PR into `main` | 2026-11-04 15:15 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Merged `diagnosis` into `proto-branch` and connected the readiness quest to `Course` (confident stages seed the profile; placement sets the first problem) | 2026-11-04 12:05 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Kiro-Eval` | Claude Opus 5.5 (Kiro) | `idle` | Evaluated the proto engine against the customer requirements (E01/E07/E08/E12, AgentCore Evaluations) and built the Evaluation Console (`evaluation/`) | 2026-11-04 10:45 PST |
| `Kiro-Diagnostic` | Claude Sonnet 5.5 (Kiro) | `idle` | Built the gamified grade 3-5 Weather Station readiness diagnostic (`diagnostic/`, `projects/weather-station/diagnostic/`, additive `evaluation/` files) on the `diagnosis` branch | 2026-11-04 |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 026] Game-Style Inputs for the Readiness Quest (tap the rows, sorting belt, word chips)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 15:45 PST
   - **Summary:** Sort questions can now carry an optional `display` (`rows`, `belt`, `chips`) that only changes how they are drawn; the answer is still {card: box}, so scoring, guess-and-slip and answer keys are unchanged (`diagnostic/models.py`, `content.py`; the public payload adds `display`). Skinned three existing Weather Station items (log-2a rows, dec-2a belt, fun-2a chips). Frontend: `frontend/src/quest/SortGames.tsx` with tap and keyboard paths, no timers or lives. Readiness quest only; lessons untouched. Tests: `SortGames.test.tsx`; payload allow-list updated in `tests/test_diag_content.py`. Heads-up `Kiro-Diagnostic`: additive change in your `diagnostic/` files.
2. **[Task 025] Merged `main` into `frontend`: My Course, Hex Skill Tree, Ducky, Yellow Theme**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 15:20 PST
   - **Summary:** Brought the student UI work (earlier Tasks 020-024) together with `main`'s landing page, pathway screen and on-request hints. New on `frontend`: a My course page with a hexagon skill tree (`ui/SkillTree.tsx`, `GET /api/students/<id>/course`), Ducky the rubber-duck helper on hints, a Rubber Ducky yellow theme (`ui/theme.ts`), and the teacher page honouring `VITE_API_BASE_URL`. Conflicts were small (App.tsx, client.ts, StepView, PathStrip, Results, service.py); `main`'s `HintCard` now shows Ducky.
3. **[Task 024] Slow Down Rushed Answers (Readiness Check and Lesson Quizzes)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 15:15 PST
   - **Summary:** New `frontend/src/ui/pace.ts`: expected seconds per question from its text (4 words/s, +0.75 s per choice or card, +1.5 s per code line, +2 s to decide; 3-40 s), rushed = under 20% of that (lowered from 40%: it triggered too often). Readiness check (`quest/QuestApp.tsx`): 2 rushed of the last 3 → "Whoa, that was fast!" message and a countdown on Check ("Check (11)") for each question; 3 calm answers in a row turn it off; explain answers aren't timed. Lesson quizzes (`App.tsx`, `ui/QuizPanel.tsx`): whole page (up to 120 s), 1 rushed submit turns it on, retries wait half, 2 calm pages turn it off. Client side only, no backend change. Browser: two rushed quest answers → message + 11 s countdown → unlocked after 10.6 s → off after 3 calm answers; rushed 3-question revision quiz → message + 21 s countdown.
4. **[Task 023] Pick a Project: Three New Pre-Built Projects with Weather Station's Skills**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 15:00 PST
   - **Summary:** One project per readiness-check goal: `projects/monster-arena` (Make a game), `projects/wildlife-watch` (Find patterns in data), `projects/library-helper` (Build tools people can use); Weather Station keeps weather_report and not_sure. Rendered offline from hand-written specs with the theme templates (same 4 levels, checks, practice and skills; spec in each `theme.json`), plus authored `functions.yaml`, `mistakes.yaml` and outlines; all pass `check_content` (11/11 projects). DRAFT for teacher review: expected values, names, tips. `projects/catalog.yaml` `topics[0].choices` lists them with goals and a one-line pitch. `Course`: `core_project_for` (chosen, else the goal's suggestion), `choose_project` (allowed until the project is started), `translate_problem` (placement and planned practice move to the same concept's practice in the chosen project), the pathway's core step and message follow the choice, the quest result names the real first problem and project. API `GET /api/students/<id>/projects`, `POST /api/students/<id>/project`. UI: `landing/ProjectPicker.tsx` on the pathway screen and a new `ChooseScreen` after "Skip to coding". `engine/support.py` content check now follows `from engine... import` to find themed check names. Browser: skip → pick Monster Arena → lesson; game goal → Monster Arena suggested → switch to Wildlife Watch on the pathway screen → steps update → lesson. Not done: the readiness check's questions and guide still talk about the weather station; the second topic (Lists and Dictionaries) is still weather-themed for everyone.
5. **[Task 022] Adaptive Support: Help That Fades as Students Improve**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 14:25 PST
   - **Summary:** New `engine/support.py` and `support:` in `projects/catalog.yaml`. Each code problem gets a help level from its weakest concept's stage (full / guided / light / minimal); two quick passes with no hints give one level less, being stuck gives one level more on that problem. Levels decide: hint after 1, 1, 2 failed runs or only on request; function bank with examples / descriptions only / hidden; outline of the steps (`<problem>/outline.py`) or the def line; AI or rules error explanation; "Where to look" mistake tip; Blocks suggestion. **Error explainer:** rules for common Python and SQL errors, AI tutor phrasing at full/guided (no code, filtered, rules fallback); a Python error gets the explanation instead of a hint. **Mistakes:** `projects/weather-station/mistakes.yaml` (21 mistakes, DRAFT for teacher review; ids reuse the readiness check's misconception codes) maps checks to mistakes root cause first; several or unmapped → AI picks from the allowed list; logged (`mistake` events), counted per student (teacher API `mistakes`, `support`), passed to the AI hint, and used to pick the in-lesson practice. **Stuck:** same failing code twice, errors in a row, fail right after a hint; failed-check stuck runs count toward `struggle_after` (syntax errors don't). AI hints now get the help level (full concrete, minimal a nudge). Content check validates `mistakes.yaml` and the 7 outlines. `engine/progress.py` records gain optional `support` and `mistakes`. Three existing tests (`test_course` x2, `test_webapi` x1) submitted identical failing code to simulate tries; they now use different code (identical code is a stuck signal). Live Bedrock: explanations, a mistake label and hints in 1.6-1.9 s. Browser: full help (outline, AI explanation, Blocks nudge, tip + hint) vs a stage-3 student (no outline, bank hidden, no auto hint or tip, Hint button still there).
6. **[Task 021] Landing Page, Grade, and Lesson Pathway from the Strands Decider 2B (Amazon Bedrock)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 13:40 PST
   - **Summary:** The site now opens on a landing page (`frontend/src/landing/Landing.tsx`): what happens, a grade picker (9-12), then the readiness check. When the check ends, "Find my pathway" runs the **Strands Decider 2B** (`engine/decider.py`, spec 4.3): rules decide which pathways the student can get (new authored `pathways:` in `projects/catalog.yaml`, one per stance: review-first, step-by-step, connect-ideas, full-project) and the rules' pick; Bedrock (team model, Haiku 4.5) reads the evidence (stage estimates, check certainty, right answers, mistake patterns, time per question), the grade and the CSTA standards the skill tree maps to, from the curriculum workbook (`engine/curriculum.py`, stdlib xlsx reader, all 196 standards), and picks one eligible pathway with a stance, cited standards, a student message and a teacher note through a forced tool call. Disallowed pathway, stance mismatch, model error, or a student message mentioning stages/scores → rules (logged `fallback`). `Course.decide_pathway` (kept once per student) starts the first step (review project, or the Weather Station at the placement / Level 3 / Level 4); when a pathway project is finished, its next project is offered first. `POST /api/students/<id>/pathway {grade}`; state has a student-safe `pathway`; `GET /api/teacher/students/<id>` returns the full decision (teacher screen doesn't show it yet). Live Bedrock: 6 decisions, 2.4-3.6 s, no fallbacks after the prompt fix (it read the check's certainty as skill at first). Browser run: landing → check → pathway (live) → lesson → reload. Needs `boto3` for live AI (not installed system-wide here; ran from a scratch copy). Not done: teacher screen for the pathway, real 2B model (the decider uses `CODEAI_MODEL_ID`), Strands Agents SDK (needs Python 3.10+, this machine has 3.9).
7. **[Task 020] AI Tutor Hints on Request, Readiness-Check Result Card, In-Lesson Help Screens**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 13:15 PST
   - **Summary:** New local branch `feat/ai-agents-diagnostic` off `frontend`, with `main` and `kiro-eval/diagnostic-9-12-and-in-lesson-help` merged in (both fast-forwards; in-lesson help is on, `struggle_after: 3`). FRONTEND_GAPS items 6-9. **Hints:** `POST /api/students/<id>/hint` (`Engine.request_hint`, `Course.request_hint`) reveals the next authored hint and counts it in `hintsSeen` without an attempt; for code problems with the AI on, it grades the current editor text (not counted) and the AI tutor phrases the hint from the failing checks, falling back to the authored hint. A "Hint (N left)" button beside Run (code and quizzes) with the honest cost line. **Readiness check:** the result screen shows "You will start with <activity>" and the goal sentence (matches the lesson's first problem); order cards use the code font and keep indentation (`diagnostic/content.py` no longer strips leading spaces from card text). **In-lesson help:** the level left for an inserted practice is `paused` on the path ("Back after practice"); the problem payload has `inserted` (`after_level`/`struggle`/`planned`) and `returnTo`; one dialog names the level the student returns to; each problem's code is kept as a draft in `localStorage` and restored on return. Typecheck, vitest (8), content checks pass; 256 Python tests with 1 error that also fails without these changes (old `jsonschema`). Browser run: full quest to the card, hint button, 3 failed runs → dialog and paused level, practice passed → back on Level 1 with the draft. Not done: live Bedrock (no `boto3` here), teacher-view gaps 1-5.
8. **[Task 019] Text/Blocks Editor Toggle & Per-Problem Function Bank**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 12:15 PST
   - **Summary:** A Text | Blocks toggle above the student editor. Blocks mode uses Blockly 13 (lazy-loaded chunk). `POST /api/blocks` (`webapi/blocks.py`) parses and compiles the student's Python (never runs it) into blocks; a syntax error or anything blocks can't show yet (class, lambda, f-string, try, with, default args, chained comparisons) gives an empty workspace plus the line and reason. Blocks → Python runs in the browser (`frontend/src/blocks/python.ts`); text stays untouched until a block is edited, and comments survive. Round trip gives the same Python AST for every starter and reference solution. Text mode gets a function bank on the toolbox side (`ui/FunctionBank.tsx`), with a popup per function, from new per-problem `functions.yaml` files (all 19 code problems); `check-content` fails if a bank lists something the reference solution doesn't use. Themed (AI-built) projects have no bank yet.
9. **[Task 018] Teacher View: Class Overview, Student Detail, Content Check**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 13:10 PST
   - **Summary:** New `webapi/teacher.py` and screens at `/#/teacher`. Class overview (in the quest, coding, finished, needs help), a stacked bar per idea showing where the class stands, a student list that flags 4+ tries, 2+ hints or the fixed-order fallback, a student detail (stages, per-project tries and hints, routing path, and the readiness quest's teacher report with the child's own words and any content-filter holds), and a button that runs the lesson and quest content checks. Read-only. Needs `CODEAI_TEACHER_TOKEN` on the server; unset means the routes return 403. Routes: `GET /api/teacher/overview`, `/api/teacher/students/<id>`, `/api/teacher/content-check`. Engine and `diagnostic/` untouched. Not done: classes or rosters (students are listed together), the evaluation console stays its own app, demo scripts stay in the terminal.
10. **[Task 017] Readiness Quest as the Front Page of the Student UI**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 12:40 PST
   - **Summary:** Merged `main` into `frontend`. The site now opens on the readiness quest (buddy and goal picks, zone bar, XP/rank/badges, tap, order and sort questions, optional typed "explain" step, feedback with tips, skill map at the end). A "Skip to coding" link starts a lesson-only student. When the quest ends, its result is applied through `Course` and the student lands in the lesson at the placement. A refresh resumes a half-finished quest. New `webapi/` routes: `GET /api/quest/options`, `POST /api/quest`, `GET /api/quest/<id>/next`, `POST /api/quest/<id>/answer`, `POST /api/quest/<id>/finish`. Ordering and sorting use buttons, not drag. The free-text goal is not offered. Seeded stages show in the concept meters, still an open design question (see the handoff doc). Engine and `diagnostic/` untouched. Browser run: full quest, hand-off, reload.
