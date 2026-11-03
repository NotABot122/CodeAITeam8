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
| `Agent-2` | Claude Sonnet 5.5 | `idle` | Scaffolded `frontend/` (React 18 / TS / MUI 7) from Code.org adaptive patterns; on branch `frontend-scaffold`, pending review | 2026-11-03 15:47 PST |
| `Agent-3` | Unassigned | `idle` | None | - |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 009] Front-End Scaffold Adapted from Code.org Adaptive Pathway UI**
   - **Model:** Claude Sonnet 5.5
   - **Agent:** `Agent-2`
   - **Timestamp:** 2026-11-03 15:47 PST
   - **Summary:** Added `frontend/` (Vite, React 18, TS, MUI 7, zod 4): typed API contract and mock backend, poly-hierarchy skill tree view, diagnostic player with AI follow-up probes, stance router, lesson view with batched telemetry. Layout and answer-flow logic adapted from `code-dot-org/code-dot-org` `apps/src/adaptive` (Apache-2.0, see `frontend/NOTICE-codeorg.md`; no Code.org assets used). 27 tests, typecheck and build pass. Only `GET /api/v1/student/skill_tree` is in the spec; other endpoints in `frontend/src/api/client.ts` are proposals for backend.
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
