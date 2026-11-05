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
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Theme designer on GPT-5.6 Terra (Task 031), Bedrock Guardrail (Task 030), AI inspector (Task 029), fading help off (Task 028), on branch `feat/guardrail-inspector-terra`, committed; PR into `main` | 2026-11-05 11:20 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Merged `diagnosis` into `proto-branch` and connected the readiness quest to `Course` (confident stages seed the profile; placement sets the first problem) | 2026-11-04 12:05 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Kiro-AgentCore` | Claude Opus 5.5 (Kiro) | `idle` | Hosted the diagnostic on AgentCore Runtime behind inbound OAuth (`deploy/agentcore/`, branch `diagnosis`) | 2026-11-04 12:30 PST |
| `Kiro-Eval` | Claude Opus 5.5 (Kiro) | `idle` | Evaluated the proto engine against the customer requirements (E01/E07/E08/E12, AgentCore Evaluations) and built the Evaluation Console (`evaluation/`) | 2026-11-04 10:45 PST |
| `Kiro-Diagnostic` | Claude Opus 5.5 (Kiro) | `idle` | Merged `origin/main` into `diagnosis`; readiness questions show code as blocks and tables; interests + skills project matching; import results from an earlier lesson | 2026-11-05 |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 032] Readiness Check: Code Blocks, Project Matching by Interests and Skills, Import Earlier Results**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Diagnostic`
   - **Timestamp:** 2026-11-05 PST
   - **Summary:** On `diagnosis`, merged into `main`: merged `origin/main` (local `main` was 74 commits behind). Conflicts in `diagnostic/safety.py`, `evaluation/harness/mcp_server.py` and both v0.2 schemas take main's reconciled versions. **Layout:** questions get `code` (Python/SQL block), `table` and `option_format`. All 24 items rewritten so code is never inside the prompt sentence (answers unchanged). `check-content` enforces it and runs the content filter on every student-facing string, code and table cells included. Web UI: `ui/CodeBlock.tsx` (highlighted, line-numbered) and inline code. Spot questions show the program's lines in order. **Matching:** `engine/matching.py`. Interests (goal + optional "What are you into?", screened) pick the story via catalog `interests`; the trusted seeding results pick the start. A "Why this project fits you" card is shown, with no stages. **Import:** `diagnostic/importer.py` (`codeai-lesson-export` v1) builds a finished readiness record. Files with personal-detail keys are rejected; ids and unknown fields aren't stored. Four synthetic samples, one per pathway. `GET/POST /api/import`, `engine.cli import`, "Import my results" on the landing page. Theme placeholders no longer name a franchise. 294 Python tests, 22 vitest, typecheck, build, harness 10/10. Not done: no browser check (none on this machine); lists and dictionaries are never assessed or imported. **Heads-up:** `test_course_diagnostic.test_lucky_guesses_are_not_seeded` flakes about 20-30% of runs, before these changes too.
2. **[Task 031] "Make it yours" Project Generation on OpenAI GPT-5.6 Terra (Bedrock)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 11:20 PST
   - **Summary:** The user asked for "GPT-Tera"; Bedrock has OpenAI GPT-5.6 Terra and GPT-6.1 Terra. Both answer forced tool calls through `us.` profiles; only 5.6 Terra also works through `global.` (6.1: AccessDenied), so the theme designer now uses `us.openai.gpt-5.6-terra` (`DEFAULT_THEME_MODEL_ID` in `engine/ai.py`, override with `CODEAI_THEME_MODEL_ID`). `Course(theme_provider=...)`; `build_theme` designs with it and keeps request moderation on the team model (Claude Haiku 4.5). `FallbackProvider`: if Terra fails, Haiku designs. All other features unchanged. The AI inspector shows the theme designer's model. Live: "soccer", "space exploration", "basketball" all built and passed the content check in about 8-10 s (the earlier Haiku build took 36 s).
3. **[Task 030] Local Safety Rules Converted into an Amazon Bedrock Guardrail**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 10:45 PST
   - **Summary:** New `engine/guardrail.py`: builds the guardrail policy from `engine/safety.py` / `diagnostic/safety.py` (word lists → word filter minus ambiguous words + managed profanity; categories → 7 denied topics incl. gambling and private details about real people; email/phone/address → PII block; injection phrases → prompt-attack filter; content filters), `sync` creates/updates `codeai-team8-student-safety` (id `byycv2r16d2i`, v2) and writes `config/bedrock_guardrail.json`. `engine.safety.screen_text(text, source, local_only, code)` asks the guardrail (INPUT for student text and code, OUTPUT for model text) and falls back to the local rules; content checks use `local_only`; prompt-attack is ignored for student code (starter files read like instructions); theme specs are screened in one batched call. `webapi.server` turns it on when AI is on and the config exists (`--no-guardrail` to skip); health/inspector show it; each check appears in the AI inspector. Eval on 44 labelled theme requests: local 8/23 caught, 5/21 false blocks → guardrail v2 21/23, 1/21 (Moby Dick, managed profanity); hint outputs: 3 bad blocked, 0 good; 0/22 code files; ~270 ms. Policy needs T&L review (borderline cases).
4. **[Task 029] Dev-Only AI Inspector Panel for Demos**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 09:40 PST
   - **Summary:** `webapi.server --dev` wraps the model provider in `engine/ai_trace.TracingProvider`, which records every call (feature, model, system prompt, input, tools and schemas, output text or tool answer, latency, tokens, student id, errors) in an in-memory ring buffer of 300 (nothing on disk). The feature is recognised from the system prompt (9 features: pathway decider, AI tutor hint, error explainer, mistake labeler, quiz scorer, readiness reader and advisor, theme moderation and designer). The web server tags each request's calls with its student (`current_student` context var). Routes `GET /api/dev/ai`, `GET /api/dev/ai/calls/after/<n>`, `POST /api/dev/ai/clear`, 404 without `--dev`; `health.dev` tells the UI. UI: `frontend/src/dev/AiInspector.tsx`, mounted in `main.tsx`: a corner button with a new-call badge opens a side panel (live, 1.5 s polling): colour per feature, description, stats, output open, input/system prompt/tools expandable, "This student only", clear. Browser with live Bedrock: two failed runs showed Error explainer, Mistake labeler and AI tutor hint with their prompts, outputs and token counts. The "AI features" list shows each feature's model (last seen in a call, else the configured one; all share `CODEAI_MODEL_ID`, default Claude Haiku 4.5).
5. **[Task 028] Full Support for Every Student (Fading Help Off)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 16:25 PST
   - **Summary:** At the user's request, help no longer tapers. New `fade` switch on `SupportPolicy` (`engine/support.py`); `projects/catalog.yaml` sets `support.fade: false`, so every student gets the `full` level on every problem whatever their stage, streak or stuck state: a hint after each failed run, the whole function bank with examples, the outline, AI error explanations, "Where to look" tips and the Blocks suggestion. The level table stays in the catalog; `fade: true` brings tapering back. Stuck detection still counts toward in-lesson practice. Checked: a stage-3 student now gets level full, the outline and a hint plus tip on the first failed run.
6. **[Task 027] "Make it yours" Back in the Header and in the Project Picker**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 16:05 PST
   - **Summary:** The header button only showed on first-topic projects, so it vanished on review steps (e.g. "Build the basics first"). Now the state has `themeable` (`now` / `later` / null, `Course.theme_target`) and the button shows at the top right whenever the first topic is current or still ahead on the pathway. `Course.build_theme`: on the first topic the theme opens now and becomes the student's `core_project`; on a review step it replaces the upcoming pathway step and starts when they get there (message says so). `reset_theme` goes back to the student's ready-made choice. `project_choices` lists a built theme as the current choice (`project: "custom"`). `ProjectPicker` has a "Make it yours" card on the pathway screen and the Skip-to-coding screen (same `ThemeDialog`, which now says "Back to the ready-made projects"). Live Bedrock: "soccer" built "Soccer Stars" from the picker in 36 s and opened it; on a review step the header button shows and the dialog says it starts after the current project.
7. **[Task 026] Game-Style Inputs for the Readiness Quest (tap the rows, sorting belt, word chips)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 15:45 PST
   - **Summary:** Sort questions can now carry an optional `display` (`rows`, `belt`, `chips`) that only changes how they are drawn; the answer is still {card: box}, so scoring, guess-and-slip and answer keys are unchanged (`diagnostic/models.py`, `content.py`; the public payload adds `display`). Skinned three existing Weather Station items (log-2a rows, dec-2a belt, fun-2a chips). Frontend: `frontend/src/quest/SortGames.tsx` with tap and keyboard paths, no timers or lives. Readiness quest only; lessons untouched. Tests: `SortGames.test.tsx`; payload allow-list updated in `tests/test_diag_content.py`. Heads-up `Kiro-Diagnostic`: additive change in your `diagnostic/` files.
8. **[Task 025] Merged `main` into `frontend`: My Course, Hex Skill Tree, Ducky, Yellow Theme**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 15:20 PST
   - **Summary:** Brought the student UI work (earlier Tasks 020-024) together with `main`'s landing page, pathway screen and on-request hints. New on `frontend`: a My course page with a hexagon skill tree (`ui/SkillTree.tsx`, `GET /api/students/<id>/course`), Ducky the rubber-duck helper on hints, a Rubber Ducky yellow theme (`ui/theme.ts`), and the teacher page honouring `VITE_API_BASE_URL`. Conflicts were small (App.tsx, client.ts, StepView, PathStrip, Results, service.py); `main`'s `HintCard` now shows Ducky.
9. **[Task 024] Slow Down Rushed Answers (Readiness Check and Lesson Quizzes)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 15:15 PST
   - **Summary:** New `frontend/src/ui/pace.ts`: expected seconds per question from its text (4 words/s, +0.75 s per choice or card, +1.5 s per code line, +2 s to decide; 3-40 s), rushed = under 20% of that (lowered from 40%: it triggered too often). Readiness check (`quest/QuestApp.tsx`): 2 rushed of the last 3 → "Whoa, that was fast!" message and a countdown on Check ("Check (11)") for each question; 3 calm answers in a row turn it off; explain answers aren't timed. Lesson quizzes (`App.tsx`, `ui/QuizPanel.tsx`): whole page (up to 120 s), 1 rushed submit turns it on, retries wait half, 2 calm pages turn it off. Client side only, no backend change. Browser: two rushed quest answers → message + 11 s countdown → unlocked after 10.6 s → off after 3 calm answers; rushed 3-question revision quiz → message + 21 s countdown.
10. **[Task 023] Pick a Project: Three New Pre-Built Projects with Weather Station's Skills**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 15:00 PST
   - **Summary:** One project per readiness-check goal: `projects/monster-arena` (Make a game), `projects/wildlife-watch` (Find patterns in data), `projects/library-helper` (Build tools people can use); Weather Station keeps weather_report and not_sure. Rendered offline from hand-written specs with the theme templates (same 4 levels, checks, practice and skills; spec in each `theme.json`), plus authored `functions.yaml`, `mistakes.yaml` and outlines; all pass `check_content` (11/11 projects). DRAFT for teacher review: expected values, names, tips. `projects/catalog.yaml` `topics[0].choices` lists them with goals and a one-line pitch. `Course`: `core_project_for` (chosen, else the goal's suggestion), `choose_project` (allowed until the project is started), `translate_problem` (placement and planned practice move to the same concept's practice in the chosen project), the pathway's core step and message follow the choice, the quest result names the real first problem and project. API `GET /api/students/<id>/projects`, `POST /api/students/<id>/project`. UI: `landing/ProjectPicker.tsx` on the pathway screen and a new `ChooseScreen` after "Skip to coding". `engine/support.py` content check now follows `from engine... import` to find themed check names. Browser: skip → pick Monster Arena → lesson; game goal → Monster Arena suggested → switch to Wildlife Watch on the pathway screen → steps update → lesson. Not done: the readiness check's questions and guide still talk about the weather station; the second topic (Lists and Dictionaries) is still weather-themed for everyone.
