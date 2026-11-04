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
| `Pratheek-Claude` | Claude Sonnet 5.5 | `idle` | Built the student UI in `frontend/` against the `proto-branch` engine (Weather Station) plus `webapi/` JSON server | 2026-11-04 10:20 PST |
| `Agent-3` | Unassigned | `idle` | None | - |
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Renamed "Stance Decider 2B" to "Strands Decider 2B" in documentation/ | 2026-11-03 15:30 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Added student-chosen themes and Bedrock AI tutor hints to the demo (`engine/themes/`, `engine/ai.py`, `engine/hints.py`, `engine/safety.py`) on `proto-branch` | 2026-11-04 09:39 PST |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 014] Student UI on the Weather Station Engine (CodeAI styling)**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Pratheek-Claude`
   - **Timestamp:** 2026-11-04 10:20 PST
   - **Summary:** Added `webapi/` (stdlib JSON server over `engine.session`: new student, state, submit, theme, theme reset; serves `frontend/dist`) and replaced the earlier mock-data scaffold in `frontend/` with screens for the real engine: level path with assigned practice problems, Python editor, instructions renderer, grader messages and hints (AI vs teacher-written), Missing/Beginning/Meeting/Exceeding meters, "quick practice" pop-up, theme dialog, completion screen. Styled after Code.org's CodeAI (design reference only, see `frontend/NOTICE-codeorg.md`). Engine code untouched. Run: `python -m webapi.server --ai off`, then `cd frontend && npm run build`. 75 Python tests, 5 vitest tests, typecheck and build pass; clicked through all 4 levels in a browser against the real engine. Not done: demo mode without the API, CodeMirror, telemetry endpoint.
2. **[Task 012] Student-Chosen Themes & Bedrock AI Tutor Hints**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Demo`
   - **Timestamp:** 2026-11-04 09:39 PST
   - **Summary:** Students can ask for the project in a theme they like (`python3 -m engine.cli theme --student ID "pokemon"`). The request is screened locally and by a separate Bedrock moderation call. Bedrock then designs the theme through a forced tool call, choosing only names, words, and number ranges. The engine validates it, generates data, checks, and a reference solution from templates, and uses the project only if the content check passes. Concepts and levels stay the same. AI hints: when a check fails, Bedrock writes one hint from the instructions, the failing checks, and the student's code. It never sees the reference solution or student ID. Unsafe or code-containing hints fall back to the teacher-written hint. Model: Claude Haiku 4.5 via `us.` inference profile in us-west-2, changeable with `CODEAI_MODEL_ID`, off with `--ai off`. Live: 17/18 themes built (one scale issue, since fixed). 69 tests pass, using a scripted model. Demo: `python3 -m engine.theme_demo` (or `--offline`). Needs `boto3`. Spec Requirements 20 and 21 added.
2. **[Task 011] Weather Station Adaptive Lesson Demo (Python Prototype)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Demo`
   - **Timestamp:** 2026-11-04 08:56 PST
   - **Summary:** Added a local Python prototype of the adaptive engine on `proto-branch` (commit `4f7669a`), with no cloud calls. One project, `projects/weather-station/`: a seeded synthetic SQLite dataset and four levels (SQL retrieval, conditionals, loops, functions) with three practice problems. The engine grades each submission in a separate process with a 10 s limit, enforces a loop rule on Level 3, gives ordered hand-written hints, tracks a Stage 0–3 per concept, routes struggling students to practice problems, and falls back to fixed level order if routing fails. Progress is saved per student. Run `python3 -m engine.demo` or see `README.md`. 51 tests pass. Spec is in `.kiro/specs/weather-station-adaptive-lesson/`. Not built yet: Bedrock rubric grading, content filter, grader benchmark. Numbered 011 because `main` already uses 009 and 010.
2. **[Task 008] Vision Document Ingestion & Intra-Lesson Adaptivity Invariant**
   - **Model:** Gemini 3.8 Flash (Authoritative)
   - **Agent:** Lead-Antigravity
   - **Timestamp:** 2026-11-03 15:33 PST
   - **Summary:** Integrated the official CodeAI AWS Imagine Grant Vision Document into documentation/VISION.md, aligning the architecture with intra-lesson adaptivity, consistent objectives with variable depth, static fallbacks, and bidirectional content filtering.
3. **[Task 007] Authoritative Lead Designation & Version Control Protocols**
   - **Model:** Gemini 3.8 Flash (Authoritative)
   - **Agent:** Lead-Antigravity
   - **Timestamp:** 2026-11-03 15:32 PST
   - **Summary:** Established authoritative implementation mandate directly to main with atomic, tested commits and branch-off protocols for high-risk modules.
4. **[Task 006] CSTA Verification, Learning Trajectories Reference & Diff-Check Rule**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** Agent-Bootstrap
   - **Timestamp:** 2026-11-03 15:31 PST
   - **Summary:** Scraped and verified Google Doc reference into documentation/resources/concept_learning_trajectories_draft.md (Units 1-4, Stage 0-3 progressions), verified CSTA PK-12 standard mappings from csteachers.org, and added mandatory documentation diff-check requirement for collaborating agents.
2. **[Task 005] Course Flow Graph, Curriculum DB Integration & Post-Project Reteach Loop**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 15:21 PST
   - **Summary:** Added `documentation/COURSE_FLOW_GRAPH.md` showing end-to-end adaptive flow. Updated `documentation/PROJECT_SPEC.md` with the teammate's Curriculum Database in Aurora/SimpleDB, dual evaluation modalities (eval checks answers, lesson checks live telemetry feed), post-project AI reteach option, and committed all files to the local Git repository pointing to `https://github.com/NotABot122/CodeAITeam8`.
2. **[Task 004] Backend-First Skill Tree & Point Classification + Stance Decider 2B Pipeline**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 15:11 PST
   - **Summary:** Updated `documentation/PROJECT_SPEC.md` to specify that the skill tree is strictly maintained on the backend (Ruby/Rails + Aurora/SimpleDB), defined the point-classification scoring model ($P_{\text{node}}$), and formalized the course flow with Stance Decider 2B determining next questions/skills.
3. **[Task 003] Official CodeAI AWS Architecture & Tech Stack Alignment**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 15:06 PST
   - **Summary:** Extracted official CodeAI technical requirements (Ruby 3.2 on Rails 7.1, React 18 / MUI 7, Aurora SQL, Amazon SimpleDB / ElastiCache, Amazon Bedrock model abstraction, Langfuse) into `documentation/TECHNICAL_ENVIRONMENT.md` and updated `documentation/PROJECT_SPEC.md` and teammate prompt accordingly.
2. **[Task 002] Multi-Parent Skill Tree Refinement & Teammate Kickoff Prompt**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 14:58 PST
   - **Summary:** Updated `documentation/PROJECT_SPEC.md` to classify nodes like While Loops under both Conditionals and Loops (poly-hierarchy), removed the `documentation/prompts/` folder, and prepared the teammate handoff prompt targeting `https://github.com/NotABot122/CodeAITeam8`.
3. **[Task 001] Documentation Foundation & Architecture Spec**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 14:52 PST
   - **Summary:** Initialized `/documentation` directory structure (`must familiarise/`, `roadmaps/`), created `collab.md`, and drafted the complete system spec in `documentation/PROJECT_SPEC.md`.
