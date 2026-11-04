# Implementation Plan (Demo Slice)

- [x] 1. Project content: dataset and reference
  - [x] 1.1 Write `projects/weather-station/dataset/generate.py` and `seed.txt`: seeded synthetic data for 3 stations × 365 days, forced boundary rows, atomic write, replace existing file
    - _Requirements: 3.1–3.10_
  - [x] 1.2 Write `reference/solution.py` (all level and practice functions) and `reference/independent_checker.py` (SQL aggregation)
    - _Requirements: 8.1, 8.2_

- [x] 2. Manifest and project loading
  - [x] 2.1 Implement `engine/manifest.py`: dataclasses, `parse_manifest` with full validation, `print_manifest`
    - _Requirements: 2.1–2.8_
  - [x] 2.2 Implement `engine/project.py`: folder layout checks, problem folder checks, all-or-nothing load
    - _Requirements: 1.1–1.7_
  - [x] 2.3 Write `projects/weather-station/manifest.yaml`, `starter.py`, and the four level folders and three practice folders (instructions, hints)
    - _Requirements: 1.2, 13.4_

- [x] 3. Grading
  - [x] 3.1 Implement `engine/checklib.py` and `engine/_runner.py` (compile, import, REQUIRED check, run checks, write result file)
    - _Requirements: 9.4, 9.5_
  - [x] 3.2 Implement `engine/grader.py`: per-submission database copy, subprocess with timeout, ungraded on infrastructure failure
    - _Requirements: 9.1–9.3, 9.6, 9.7_
  - [x] 3.3 Implement `engine/loop_checker.py` and merge its findings into the Level 3 result
    - _Requirements: 6.8, 6.9, 6.11, 6.12_
  - [x] 3.4 Write `checks.py` for Levels 1–4 and the practice problems
    - _Requirements: 4.1–4.8, 5.1–5.8, 6.1–6.7, 6.10, 7.1–7.8_

- [x] 4. Expected values and content check
  - [x] 4.1 Implement `engine/content.py`: generate expected reports from the independent checker with seed and `teacher_reviewed: false`; content check (reference passes all checks, stored vs independent, seed match, unreviewed notice)
    - _Requirements: 8.1, 8.3–8.8_
  - [x] 4.2 Generate `reference/expected_reports.json`
    - _Requirements: 8.3, 8.5_

- [x] 5. Learning loop
  - [x] 5.1 Implement `engine/feedback.py`: per-failure messages with level label, 200-character limit, ordered hints
    - _Requirements: 13.1–13.7_
  - [x] 5.2 Implement `engine/stages.py`
    - _Requirements: 14.1–14.10_
  - [x] 5.3 Implement `engine/router.py`
    - _Requirements: 16.1–16.5, 16.7–16.10_
  - [x] 5.4 Implement `engine/progress.py` and `engine/events.py`
    - _Requirements: 15.1–15.7, 19.1, 19.2, 19.6_
  - [x] 5.5 Implement `engine/session.py`: submit flow, routing log, fallback path, adaptive switch
    - _Requirements: 13.5, 15.1, 15.2, 15.6, 15.7, 16.6, 17.1, 17.3–17.9, 18.1–18.6_

- [x] 6. Interfaces
  - [x] 6.1 Implement `engine/cli.py`: `new`, `show`, `submit`, `progress`, `generate-data`, `generate-expected`, `check-content`, `--no-adaptive`
    - _Requirements: 17.8, 18.1–18.4, 19.3_
  - [x] 6.2 Implement `engine/demo.py`: three scripted students (strong, struggling, router failure)
    - _Requirements: 16, 17_

- [x] 7. Tests and verification
  - [x] 7.1 Unit and property tests for manifest, dataset, loop checker, stages, router, and progress store
  - [x] 7.2 Grader and content tests with reference and known-bad submissions
  - [x] 7.3 Engine flow tests and a full demo run
  - [x] 7.4 README with how to run the demo

- [x] 8. Themes and AI hints
  - [x] 8.1 `engine/ai.py`: ModelProvider, BedrockProvider (Converse, tool use), ScriptedProvider
    - _Requirements: 10.2, 10.3, 21.5_
  - [x] 8.2 `engine/safety.py`: local rules and model moderation, fail closed
    - _Requirements: 12.1, 12.7, 12.8, 20.1, 20.2_
  - [x] 8.3 `engine/hints.py` and Engine integration with fallback and logging
    - _Requirements: 21.1–21.8, 19.4_
  - [x] 8.4 `engine/themes/`: spec validation, renderer, dataset, shared checks, builder with quality gate
    - _Requirements: 20.3–20.10_
  - [x] 8.5 CLI `theme` command, per-student active project, `--ai` switch, `engine.theme_demo`
    - _Requirements: 20.9, 21.8_
  - [x] 8.6 Tests with a scripted model (spec, filter, builder, themed grading, AI hints) and live Bedrock runs
