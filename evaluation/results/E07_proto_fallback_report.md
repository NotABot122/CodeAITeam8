# E07 on proto-branch: fallback under injected failures

Requirement (Vision, MVP success criteria): when validation or routing fails, the student falls back to a working non-adaptive path rather than a broken one. Each scenario injects one fault into proto's `Engine` (commit 745b446, unchanged) and submits a correct file up to 12 times. No model calls.

**9/12 scenarios end with the student finishing the project.**

| Scenario | Failure type | Expected | Finished | Submissions | Path | Fallback logged | Crash |
|---|---|---|---|---|---|---|---|
| baseline adaptive | - | completes, no fallback | yes | 4 | level-1 → level-2 → level-3 → level-4 | - | - |
| router raises on 2nd decision | routing fails | fallback to fixed order, completes | yes | 4 | level-1 → level-2 → level-3 → level-4 | router_error | - |
| router returns a problem not in the manifest | routing fails | fallback to fixed order, completes | yes | 4 | level-1 → level-2 → level-3 → level-4 | problem_not_in_manifest | - |
| saved progress is corrupted | routing state lost | restart on fixed order, completes | yes | 4 | level-1 → level-2 → level-3 → level-4 | progress_load_failure | - |
| progress save fails twice | infrastructure | notice, completes | yes | 4 | level-1 → level-2 → level-3 → level-4 | - | - |
| grader unavailable for 2 submissions | validation fails (transient) | retry, completes | yes | 6 | level-1 → level-1 → level-1 → level-2 → level-3 → level-4 | - | - |
| grader unavailable for every submission | validation fails (persistent) | falls back to a working non-adaptive path | **no** | 12 | level-1 → level-1 → level-1 → level-1 → level-1 → level-1 → level-1 … | - | - |
| grader raises an unexpected exception once | validation fails (bug) | error handled, completes | **no** | 0 | level-1 | - | RuntimeError: grader crashed (escapes Engine: session.py, line 188, in submit) |
| grader times out once | validation fails (timeout) | counted as a failed attempt, completes | yes | 5 | level-1 → level-1 → level-2 → level-3 → level-4 | - | - |
| AI hint model returns ModelError | AI hint fails | teacher hint, completes | yes | 5 | level-1 → level-1 → level-2 → level-3 → level-4 | - | - |
| AI hint model raises an unexpected exception | AI hint fails (bug) | teacher hint, completes | **no** | 0 | level-1 | - | RuntimeError: SDK bug (escapes Engine: session.py, line 254, in _ai_hint) |
| adaptive routing turned off | operator switch | fixed order, completes | yes | 4 | level-1 → level-2 → level-3 → level-4 | adaptive_routing_disabled | - |
