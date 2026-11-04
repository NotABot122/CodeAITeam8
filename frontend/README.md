# CodeAI student UI

React 18 + TypeScript + MUI 7 + Vite. Styled after Code.org's CodeAI (purple brand, orange Run, Geist/Space Grotesk).
It talks to the adaptive engine from `proto-branch` (including `engine.course`) through `webapi/` (a small JSON server in the repo root).

## Run it

```bash
# 1. API (from the repo root; needs PyYAML; --ai off skips Bedrock)
python -m webapi.server --port 8080 --ai off

# 2a. Dev server with hot reload (proxies /api to :8080)
cd frontend && npm install && npm run dev

# 2b. Or build once; the API server then serves frontend/dist itself at http://127.0.0.1:8080
cd frontend && npm run build
```

Teacher view: set `CODEAI_TEACHER_TOKEN=somesecret` before starting the server, then open `/#/teacher`.

Remove `--ai off` (and install `boto3`, set AWS creds) to get AI hints and the "Make it yours" themes.

## What's here

- `src/teacher/` – teacher view at `/#/teacher`: class overview (who is in the quest, coding, finished, needs help), where the class stands on each idea, a student detail with the quest report, and a content check. Needs `CODEAI_TEACHER_TOKEN` on the server (off if unset); the token is kept in session storage only.
- `src/quest/` – the readiness quest, which is the front page (Storm Chaser Academy). Taps for choices, up/down buttons for ordering, a box pick for sorting. "Skip to coding" goes straight to the lesson.

- `src/api/` – typed client and response shapes (mirror `webapi/service.py`)
- `src/ui/PathStrip` – compact level path; an assigned practice problem shows as a badge on its level
- `src/ui/QuizPanel`, `src/ui/NextStepPanel` – review quizzes and the "what's next" screen (from `engine.course`)
- `src/ui/CodeEditor` – textarea with line numbers (Tab = 4 spaces, Esc then Tab leaves the box, Ctrl/Cmd+Enter runs)
- `src/ui/Results` – grader messages, hint (labelled AI or teacher-written), stage changes
- `src/ui/ConceptMeters` – Missing / Beginning / Meeting / Exceeding for all six concepts, in a sideways-scrolling row
- `src/ui/Dialogs` – "A quick practice first" pop-up and the theme dialog
- `src/ui/markdown` – tiny renderer for the instructions (React nodes only, no innerHTML)

The UI never grades or routes; it shows what the engine returns. The student id is kept in `localStorage`.

## Checks

`npm run typecheck`, `npm test`, `npm run build`; API tests: `python -m pytest tests/test_webapi.py`.

Attribution for the Code.org design reference: `NOTICE-codeorg.md`.
