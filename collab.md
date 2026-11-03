# Collaboration & Agent Tracking (collab.md)

Welcome to the vibe-coding coordination hub! 🚀
Every autonomous agent or developer **MUST read this file before writing code** to understand ongoing work, avoid duplicate efforts, and coordinate state cleanly.

---

## ⚡ Agent Guidelines & Rules of Engagement

1. **Before Starting Any Task:**
   - Review the **Active Agent Status Table** below to ensure no collision on targeted modules/files.
   - Set your Agent status to `working` with your exact task objective and target model.
   - Review recent entries in the **LRU Task History** to maintain continuity.
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
| `Agent-Bootstrap` | Gemini 3.8 Flash | `idle` | Formalized backend-first skill tree, point-classification scoring, and Stance Decider 2B course flow diagram | 2026-11-03 15:11 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Agent-3` | Unassigned | `idle` | None | - |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 004] Backend-First Skill Tree & Point Classification + Stance Decider 2B Pipeline**
   - **Model:** Gemini 3.8 Flash
   - **Agent:** `Agent-Bootstrap`
   - **Timestamp:** 2026-11-03 15:11 PST
   - **Summary:** Updated `documentation/PROJECT_SPEC.md` to specify that the skill tree is strictly maintained on the backend (Ruby/Rails + Aurora/SimpleDB), defined the point-classification scoring model ($P_{\text{node}}$), and formalized the course flow with Stance Decider 2B determining next questions/skills.
2. **[Task 003] Official CodeAI AWS Architecture & Tech Stack Alignment**
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
