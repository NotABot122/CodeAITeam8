# CodeAI front end

React 18, TypeScript, MUI 7, Vite. Versions match Code.org's `apps/package.json`
(React 18.3, MUI 7.3, zod 4, TS 5.9) so code can move between the two.

```
npm install
npm run dev        # runs against mock data
npm test           # unit + server-render smoke tests
npm run build      # typecheck, then production build
```

Set `VITE_API_BASE_URL` (for example `http://localhost:3000`) to call the Rails
backend instead of the mock.

## Layout

| Path | What |
|---|---|
| `src/api/schema.ts` | zod schemas: the contract with the backend |
| `src/api/client.ts` | `ApiClient` interface and the HTTP client; responses are validated at this boundary |
| `src/api/mock/` | In-memory backend, kept valid against the schemas by a test |
| `src/features/skilltree/` | Skill tree: layout (adapted from Code.org), poly-hierarchy categories, detail panel |
| `src/features/diagnostic/` | One-question-at-a-time diagnostic with AI follow-up probes |
| `src/features/stance/` | Asks for the next step and shows the screen for its stance |
| `src/features/lesson/` | Lesson screen; editor is a textarea until a real one is chosen |
| `src/features/telemetry/` | Batched editor telemetry; sends counts and durations, never typed text |

## Open items for the team

- Only `GET /api/v1/student/skill_tree` is in `PROJECT_SPEC.md`. The other
  paths in `client.ts` are proposals; backend should accept or change them.
- Node states are `LOCKED / AVAILABLE / MASTERED` per the spec. Code.org also
  has `inProgress` and `skipped`; add them to `schema.ts` if we want them.
- Which language do students write? Decides the editor and how code runs.
- The telemetry events carry no code text. Raw code snapshots to S3 need a
  decision on student privacy first.
- Student-facing "Dev" buttons in `LessonView` simulate runs and errors until a
  real runner exists. Remove them then.

## Attribution

Some files are adapted from Code.org (Apache-2.0). See `NOTICE-codeorg.md`.
