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
| `zane-claude` | Claude Opus 5.5 (Kiro) | `idle` | Readiness-check slow-down: quick clicks after feedback no longer count (Task 036); committed on `feat/prod-deploy`, not released or pushed | 2026-11-05 07:55 PST |
| `Kiro-Demo` | Claude Opus 5.5 (Kiro) | `idle` | Merged `diagnosis` into `proto-branch` and connected the readiness quest to `Course` (confident stages seed the profile; placement sets the first problem) | 2026-11-04 12:05 PST |
| `Agent-2` | Unassigned | `idle` | None | - |
| `Kiro-AgentCore` | Claude Opus 5.5 (Kiro) | `idle` | Hosted the diagnostic on AgentCore Runtime behind inbound OAuth (`deploy/agentcore/`, branch `diagnosis`) | 2026-11-04 12:30 PST |
| `Kiro-Eval` | Claude Opus 5.5 (Kiro) | `idle` | Evaluated the proto engine against the customer requirements (E01/E07/E08/E12, AgentCore Evaluations) and built the Evaluation Console (`evaluation/`) | 2026-11-04 10:45 PST |
| `Kiro-Diagnostic` | Claude Opus 5.5 (Kiro) | `idle` | Merged `origin/main` into `diagnosis`; readiness questions show code as blocks and tables; interests + skills project matching; import results from an earlier lesson | 2026-11-05 |

---

## 🔄 LRU Task History (Last 10 Completed Tasks)

> *Most recent on top. Maximum 10 items.*

1. **[Task 036] Readiness Check Slow-Down Ignores Clicks Carried Over from Feedback**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 07:55 PST
   - **Summary:** Order questions and row-sort questions start ready to check, so a quick click carried over from the feedback screen's Next could answer the next question in under a second. It counted as rushed, and two of those turned on the slow-down (Task 024). `frontend/src/quest/QuestApp.tsx`: clicks on a question are ignored for its first 0.8 s (`SETTLE_MS`), with no visual change; `send` refuses before then. Feedback time and the Next click were already never timed (timer runs from the question appearing to Check). Throwaway jsdom test: the old code triggered the slow-down from three Next-then-Check bursts; the new code submits only the real answers and doesn't. Genuinely rushed answers (0.9 s after the pause) still trigger it. 22 vitest, typecheck, build.
2. **[Task 035] Production on AWS: Private EC2 behind CloudFront, Sandboxed Student Code**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 03:28 PST
   - **Summary:** Live at https://dag0zjv2d0yq1.cloudfront.net (us-west-2), from `main` plus `feat/prod-deploy`. Stacks: `codeai-storage-prod` (storage template with `Suffix=-prod`: its own buckets, KMS key and app role, which only the server role can assume) and `codeai-prod` (`infrastructure/production.yaml`: VPC, private t3.small with no public IP, NAT, S3 gateway endpoint, CloudFront VPC origin with HTTPS redirect and security headers, release bucket, teacher token in Secrets Manager `codeai-team8/prod/teacher-token`, recover and reboot alarms). Port 8080 is open only to `CloudFront-VPCOrigins-Service-SG`; the VPC-range rule never matched (504s). `python -m deploy.production infra | release | status`: a release is a commit, shipped through SSM Run Command to `deploy/production/install.sh`, then smoke-tested. Student code runs as `codeai-sandbox` through sudo and `run-student-code`: copies only, cleared environment, nftables drops all its packets, CPU, memory and process limits. `engine/grader.py` copies the files into the temp folder and validates the runner's result. Live checks: AI hint on a failing run, reference solution passes, infinite loop times out; a probe submission found metadata, server, internet, data dir and settings all blocked and a clean env (uid 992); teacher pages 403 without the token; inspector 404; admin role denied on the prod bucket and on assuming the prod app role. Fixed on the way: install race (lock), datasets built before the release is made read-only. About $50/month, mostly NAT. See `documentation/PRODUCTION.md`. Later at the user's request: the AI inspector is on in production (`--dev`), and with a teacher token set `/api/dev/*` needs `X-Teacher-Token` (403 otherwise); the panel asks for the token, and `health.devLocked` tells it. Live: no or wrong token 403, the right token shows the calls. Then: a "Standards retrieval (RAG)" inspector entry before each pathway decision (source and S3 version, query, retrieved standards, which ones the decider cited; `retrieve_standards` in `engine/decider.py`, exact lookup by code). Checked on a local server with the S3 curriculum. The "Strands Decider 2B" name is removed from the app: `PathwayDecider` class, inspector label "Pathway decider", system prompt, stored `decider` field and event category `pathway_decider`; the spec documents in `documentation/` still use the old name.
3. **[Task 034] Student Data and Curriculum on S3, Privacy Pass on Stored Student Data**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 02:05 PST
   - **Summary:** On `feat/s3-storage` (includes `claude/eloquent-clarke-uik76u`). `infrastructure/curriculum-and-progress.yaml` now makes the curriculum bucket, a student-data bucket (versioned, SSE-KMS with its own key, public access and ACLs off, TLS only, old versions expire after 30 days) and the app role `CodeAITeam8App-<region>`. The unused DynamoDB table is gone. A bucket-policy deny and the key policy let only the app role read or write student data; the IAM policy simulator shows the workshop admin role gets an explicit deny. New `engine/s3_storage.py`: `.codeai-data/` stays the working copy; changed files under progress/, workspace/, themes/ and logs/ go to S3 in a background thread (0.5 s debounce, retries, flush on stop); the server restores from S3 on start (manifest `.s3-sync.json`); `/api/health` shows `storage`. Hooks in `engine/progress.py`, `diagnostic/store.py`, `engine/events.py`, `diagnostic/eval_log.py`, `engine/cli.py`, `webapi/service.py`, `engine/themes/builder.py`. The curriculum loader uses the app role. CLI: `python -m engine.s3_storage configure | publish-curriculum | status`. AgentCore code bucket: TLS-only policy, ACLs off. Privacy: data dir 0700/0600 with umask 077; emails and phone numbers in student code become `[removed]` and the student is told. Inventory in `documentation/AWS_STORAGE_SETUP.md`. 303 tests; fake-S3 end-to-end check (save, wipe and restore, offline changes, outage retry). Deployed: stack `codeai-storage` (us-west-2); `config/aws_storage.json` written; standards published (version pinned). Live: admin role gets an explicit deny on list/get/put and the KMS key refuses it; the app role reads and writes (SSE-KMS, bucket key); plain HTTP refused; 74 students (469 files) uploaded on first start; restoring the bucket into an empty folder gave 473/473 files identical to the live copy. AgentCore: `python3 -m deploy.agentcore deploy` run in this account (runtime `codeai_team8_diagnostic`, code bucket TLS-only, ACLs off, SSE-S3); `demo` passed 4/4 (401 no token, 403 forged, SigV4 refused, 200 with a Cognito token).
4. **[Task 033] Cheaper Team Model Tried and Reverted: Staying on Claude Haiku 4.5**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 01:32 PST
   - **Summary:** No code change. Tried `us.anthropic.claude-haiku-5-5` as `DEFAULT_MODEL_ID` ($0.11 / $0.55 per million tokens on Bedrock us-west-2 against Haiku 4.5's $1.10 / $5.50). In a 28-case hint test (Claude Sonnet 4.5 judging) it gave the fix away less often (4.3/5 against 1.7/5) at $0.36 against $1.91 per 1,000 hints. Reverted at the user's request because the agent evaluations (`evaluation/harness/bedrock_client.py`) pin Haiku 4.5 and send `temperature`, which Haiku 5.5 rejects, so the app would no longer match what was evaluated. Notes if someone switches later: Haiku 5.5 thinks before plain-text answers and that counts toward `max_tokens` (hints at 200 came back empty; 1,500 works), and it counts the same text as about 30% more tokens, so the decider, placement advisor and mistake labeler need more room. Move the evaluation harness first.
5. **[Task 032] Readiness Check: Code Blocks, Project Matching by Interests and Skills, Import Earlier Results**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `Kiro-Diagnostic`
   - **Timestamp:** 2026-11-05 PST
   - **Summary:** On `diagnosis`, merged into `main`: merged `origin/main` (local `main` was 74 commits behind). Conflicts in `diagnostic/safety.py`, `evaluation/harness/mcp_server.py` and both v0.2 schemas take main's reconciled versions. **Layout:** questions get `code` (Python/SQL block), `table` and `option_format`. All 24 items rewritten so code is never inside the prompt sentence (answers unchanged). `check-content` enforces it and runs the content filter on every student-facing string, code and table cells included. Web UI: `ui/CodeBlock.tsx` (highlighted, line-numbered) and inline code. Spot questions show the program's lines in order. **Matching:** `engine/matching.py`. Interests (goal + optional "What are you into?", screened) pick the story via catalog `interests`; the trusted seeding results pick the start. A "Why this project fits you" card is shown, with no stages. **Import:** `diagnostic/importer.py` (`codeai-lesson-export` v1) builds a finished readiness record. Files with personal-detail keys are rejected; ids and unknown fields aren't stored. Four synthetic samples, one per pathway. `GET/POST /api/import`, `engine.cli import`, "Import my results" on the landing page. Theme placeholders no longer name a franchise. 294 Python tests, 22 vitest, typecheck, build, harness 10/10. Not done: no browser check (none on this machine); lists and dictionaries are never assessed or imported. **Fixed flake:** `test_course_diagnostic.test_lucky_guesses_are_not_seeded` failed about 20-30% of runs because the simulator's "wrong" sort answer moved one card of five, which still passes the 80% bar; it now misplaces enough cards (0/40 failures; regression test in `test_diag_content.py`).
6. **[Task 031] "Make it yours" Project Generation on OpenAI GPT-5.6 Terra (Bedrock)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 11:20 PST
   - **Summary:** The user asked for "GPT-Tera"; Bedrock has OpenAI GPT-5.6 Terra and GPT-6.1 Terra. Both answer forced tool calls through `us.` profiles; only 5.6 Terra also works through `global.` (6.1: AccessDenied), so the theme designer now uses `us.openai.gpt-5.6-terra` (`DEFAULT_THEME_MODEL_ID` in `engine/ai.py`, override with `CODEAI_THEME_MODEL_ID`). `Course(theme_provider=...)`; `build_theme` designs with it and keeps request moderation on the team model (Claude Haiku 4.5). `FallbackProvider`: if Terra fails, Haiku designs. All other features unchanged. The AI inspector shows the theme designer's model. Live: "soccer", "space exploration", "basketball" all built and passed the content check in about 8-10 s (the earlier Haiku build took 36 s).
7. **[Task 030] Local Safety Rules Converted into an Amazon Bedrock Guardrail**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 10:45 PST
   - **Summary:** New `engine/guardrail.py`: builds the guardrail policy from `engine/safety.py` / `diagnostic/safety.py` (word lists → word filter minus ambiguous words + managed profanity; categories → 7 denied topics incl. gambling and private details about real people; email/phone/address → PII block; injection phrases → prompt-attack filter; content filters), `sync` creates/updates `codeai-team8-student-safety` (id `byycv2r16d2i`, v2) and writes `config/bedrock_guardrail.json`. `engine.safety.screen_text(text, source, local_only, code)` asks the guardrail (INPUT for student text and code, OUTPUT for model text) and falls back to the local rules; content checks use `local_only`; prompt-attack is ignored for student code (starter files read like instructions); theme specs are screened in one batched call. `webapi.server` turns it on when AI is on and the config exists (`--no-guardrail` to skip); health/inspector show it; each check appears in the AI inspector. Eval on 44 labelled theme requests: local 8/23 caught, 5/21 false blocks → guardrail v2 21/23, 1/21 (Moby Dick, managed profanity); hint outputs: 3 bad blocked, 0 good; 0/22 code files; ~270 ms. Policy needs T&L review (borderline cases).
8. **[Task 029] Dev-Only AI Inspector Panel for Demos**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-05 09:40 PST
   - **Summary:** `webapi.server --dev` wraps the model provider in `engine/ai_trace.TracingProvider`, which records every call (feature, model, system prompt, input, tools and schemas, output text or tool answer, latency, tokens, student id, errors) in an in-memory ring buffer of 300 (nothing on disk). The feature is recognised from the system prompt (9 features: pathway decider, AI tutor hint, error explainer, mistake labeler, quiz scorer, readiness reader and advisor, theme moderation and designer). The web server tags each request's calls with its student (`current_student` context var). Routes `GET /api/dev/ai`, `GET /api/dev/ai/calls/after/<n>`, `POST /api/dev/ai/clear`, 404 without `--dev`; `health.dev` tells the UI. UI: `frontend/src/dev/AiInspector.tsx`, mounted in `main.tsx`: a corner button with a new-call badge opens a side panel (live, 1.5 s polling): colour per feature, description, stats, output open, input/system prompt/tools expandable, "This student only", clear. Browser with live Bedrock: two failed runs showed Error explainer, Mistake labeler and AI tutor hint with their prompts, outputs and token counts. The "AI features" list shows each feature's model (last seen in a call, else the configured one; all share `CODEAI_MODEL_ID`, default Claude Haiku 4.5).
9. **[Task 028] Full Support for Every Student (Fading Help Off)**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 16:25 PST
   - **Summary:** At the user's request, help no longer tapers. New `fade` switch on `SupportPolicy` (`engine/support.py`); `projects/catalog.yaml` sets `support.fade: false`, so every student gets the `full` level on every problem whatever their stage, streak or stuck state: a hint after each failed run, the whole function bank with examples, the outline, AI error explanations, "Where to look" tips and the Blocks suggestion. The level table stays in the catalog; `fade: true` brings tapering back. Stuck detection still counts toward in-lesson practice. Checked: a stage-3 student now gets level full, the outline and a hint plus tip on the first failed run.
10. **[Task 027] "Make it yours" Back in the Header and in the Project Picker**
   - **Model:** Claude Opus 5.5 (Kiro)
   - **Agent:** `zane-claude`
   - **Timestamp:** 2026-11-04 16:05 PST
   - **Summary:** The header button only showed on first-topic projects, so it vanished on review steps (e.g. "Build the basics first"). Now the state has `themeable` (`now` / `later` / null, `Course.theme_target`) and the button shows at the top right whenever the first topic is current or still ahead on the pathway. `Course.build_theme`: on the first topic the theme opens now and becomes the student's `core_project`; on a review step it replaces the upcoming pathway step and starts when they get there (message says so). `reset_theme` goes back to the student's ready-made choice. `project_choices` lists a built theme as the current choice (`project: "custom"`). `ProjectPicker` has a "Make it yours" card on the pathway screen and the Skip-to-coding screen (same `ThemeDialog`, which now says "Back to the ready-made projects"). Live Bedrock: "soccer" built "Soccer Stars" from the picker in 36 s and opened it; on a review step the header button shows and the dialog says it starts after the current project.
