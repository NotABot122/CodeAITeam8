# Requirements Document

## Introduction

This feature is a Python prototype of the CodeAI Adaptive Engine, delivered with its first lesson: the Weather Station Project. Grade 9-12 students write four Python functions against a synthetic SQLite weather dataset. Each function is one level: Level 1 retrieves data with a parameterized query (`get_readings`), Level 2 applies conditionals (`classify_day`), Level 3 uses loops (`summarize`), and Level 4 combines the earlier functions (`build_report`).

The Engine grades code submissions with automated tests and grades open-ended written responses with an AI rubric grader on Amazon Bedrock. The model sits behind a swappable abstraction. The Engine tracks a stage per concept (Stage 0 Missing to Stage 3 Exceeding), saves that progress across sessions, and routes the student to the next level or practice problem. If validation or routing fails, the student continues on a fixed, non-adaptive level order.

Projects are content folders with a fixed layout: manifest, dataset generator, levels, and reference solution. Later projects can then reuse the Engine without code changes. Only Project 1 is built now.

Primary source: `lessons/weather-station-project/SPEC.md`. Background: the vision, technical, and concepts documents in `rubric/`.

Decisions applied from the lesson spec's open questions:
1. Level 3 checks both the output values and that the student used a loop.
2. Attempts are unlimited.
3. Expected values come from automated cross-checks for now. A teacher will review them later.
4. Target Python 3.11 and pytest.
5. CSTA standards codes are skipped for the prototype.

Assumptions made for this draft (please confirm or correct):
- A concept stage only moves up during the prototype. A student never loses a stage they earned.
- The default streak length for moving up a stage is 3 consecutive qualifying problems. Each project manifest can override it.
- Open-ended responses are short written prompts that a level can include, for example "Explain why the heat-wave check uses `>=`". They are graded by the Rubric_Grader, and Project 1 includes at least one per level.
- "First-attempt" and "second-attempt" mastery from the draft spec is replaced by the stage streak model, because attempts are unlimited.
- Streak_Length must be a whole number from 1 to 10.
- A streak counts only distinct Problems; resubmitting an already-counted Problem does not extend a streak.
- A Concept's streak resets to 0 after its Stage rises, so each Stage needs fresh evidence.
- The default agreement threshold for the validator benchmark is 80% exact agreement.
- Content filter categories: profanity, sexual content, violence, self-harm, hate or harassment, and personal contact information. If the filter errors, the item is treated as blocked.

## Glossary

- **Engine**: The Python prototype that loads projects, presents levels, grades submissions, tracks stages, and routes students.
- **Project**: A folder under `projects/<project-name>/` containing a Manifest, a dataset folder, a levels folder, and a reference folder.
- **Manifest**: The `manifest.yaml` file in a Project. It declares the title, levels, concept mapping, stage criteria, streak length, and practice problems.
- **Project_Loader**: The Engine component that reads a Project folder and builds an in-memory Project definition.
- **Manifest_Parser**: The Project_Loader component that parses `manifest.yaml` text into a Manifest object.
- **Manifest_Printer**: The component that formats a Manifest object back into `manifest.yaml` text.
- **Level**: One step in a Project with one objective, instructions, ordered hints, automated tests, and optional open-ended prompts.
- **Practice_Problem**: A pre-authored, pre-approved extra problem tied to one concept and one target stage. The Router can assign it instead of advancing to the next Level.
- **Problem**: A Level or a Practice_Problem.
- **Concept**: A skill the Engine tracks. For Project 1 the Concepts are Database_Retrieval, Conditionals, Loops, and Functions.
- **Stage**: A student's level on one Concept: 0 (Missing), 1 (Beginning), 2 (Meeting), or 3 (Exceeding).
- **Stage_Criteria**: The Manifest-defined conditions a graded Problem result must meet to count as evidence for a given Stage of a Concept.
- **Streak_Length**: The number of consecutive qualifying Problem results needed to move a Concept up one Stage.
- **Stage_Tracker**: The Engine component that updates Stages from graded results.
- **Router**: The Engine component that selects the next Problem for a student from Stages and the Manifest.
- **Fallback_Path**: The fixed Level order 1, 2, 3, 4 declared in the Manifest, used when validation or routing fails.
- **Dataset_Generator**: The script in a Project's dataset folder that builds the SQLite database from a fixed random seed.
- **Weather_Database**: The SQLite file `weather.db` produced by the Project 1 Dataset_Generator, with table `daily_readings` (station_id TEXT, date TEXT, temp_high_c REAL, temp_low_c REAL, rain_mm REAL).
- **Submission**: The code or written response a student submits for one Problem.
- **Test_Grader**: The Engine component that runs a Level's pytest tests against a code Submission in an isolated process.
- **Loop_Checker**: The Engine component that inspects a Level 3 code Submission's syntax tree for a loop and for banned aggregate shortcuts.
- **Rubric_Grader**: The Engine component that scores a written Submission against a rubric using a Model_Provider.
- **Model_Provider**: The abstraction through which the Engine calls a language model. The prototype implementation calls Amazon Bedrock.
- **Content_Filter**: The Engine component that screens student input and model output before the Engine uses or shows that text.
- **Feedback_Service**: The Engine component that turns grading results into plain-language messages and hints.
- **Progress_Store**: The abstraction that saves and loads student progress. The prototype implementation uses local files or SQLite.
- **File_Store**: The abstraction that saves and loads files such as rubrics and submissions. The prototype implementation uses the local filesystem.
- **Reference_Solution**: The Project's correct implementation of every Level, used only to check tests and expected values.
- **Independent_Checker**: A computation of expected report values that is written separately from the Reference_Solution, for example direct SQL aggregation over the Weather_Database.
- **Benchmark_Set**: A small set of written Submissions with human-assigned rubric scores, used to measure Rubric_Grader agreement.
- **Student_Id**: An opaque, generated identifier for a test student. It contains no personal information.

## Requirements

### Requirement 1: Project folder structure and loading

**User Story:** As a curriculum author, I want each project to be a self-contained folder with a fixed layout, so that I can add later projects without changing Engine code.

#### Acceptance Criteria

1. WHEN the Engine requests a Project load for a folder under `projects/<project-name>/`, THE Project_Loader SHALL accept the folder as a valid Project layout if the folder contains a `manifest.yaml` file, a `dataset/` folder, a `levels/` folder with one subfolder for each Level listed in the Manifest, and a `reference/` folder.
2. WHEN a Project folder with a valid layout is loaded, THE Project_Loader SHALL build one Project definition. That definition SHALL contain, for every Level listed in the Manifest, the Level's instructions, its hints in the order defined in the Level folder, its tests, its open-ended prompts (zero or more), and its Concept mapping. It SHALL also contain every Practice_Problem listed in the Manifest.
3. IF a Project folder is missing one or more of `manifest.yaml`, `dataset/`, `levels/`, or `reference/`, THEN THE Project_Loader SHALL report a single error that names every missing item, not only the first one found.
4. IF the Manifest references a Level folder or a Practice_Problem that does not exist in the Project folder, THEN THE Project_Loader SHALL report an error naming each missing Level folder or Practice_Problem identifier.
5. WHEN a second Project is placed under `projects/<project-name>/` with the same folder layout and different content (a different title, Levels, Concepts, and dataset), THE Engine SHALL load that Project, present its Level 1, and grade a Submission for it, with no changes to Engine source code.
6. IF a Level folder listed in the Manifest is missing its instructions, its hints, or its tests, THEN THE Project_Loader SHALL report an error naming the Level and each missing item.
7. IF the Project_Loader reports any error while loading a Project, THEN THE Project_Loader SHALL return no Project definition, not even a partial one, and THE Engine SHALL present no Problem from that Project to students.

### Requirement 2: Manifest parsing and printing

**User Story:** As a curriculum author, I want the manifest to be parsed and validated reliably, so that mistakes in project configuration are caught before students see them.

#### Acceptance Criteria

1. WHEN a valid `manifest.yaml` is provided, THE Manifest_Parser SHALL parse the file into a Manifest object containing the title, Levels, Concept mapping, Stage_Criteria, Streak_Length, Practice_Problems, and Fallback_Path, where a valid `manifest.yaml` is one that passes every check in criteria 2, 3, 4, 6, and 7.
2. IF `manifest.yaml` contains a YAML syntax error, THEN THE Manifest_Parser SHALL return an error that states the line number of the first syntax error, and THE Manifest_Parser SHALL return no Manifest object.
3. IF `manifest.yaml` is missing one or more required fields (title, Levels, Concept mapping, Stage_Criteria, or Fallback_Path), or the title is empty, THEN THE Manifest_Parser SHALL return one error that names every missing or empty field, and THE Manifest_Parser SHALL return no Manifest object.
4. IF the Manifest omits Streak_Length, THEN THE Manifest_Parser SHALL set Streak_Length to 3; IF the Manifest gives a Streak_Length that is not a whole number from 1 to 10 inclusive, THEN THE Manifest_Parser SHALL return an error naming the Streak_Length field and the invalid value, and THE Manifest_Parser SHALL return no Manifest object.
5. WHEN the Manifest_Printer formats a Manifest object, THE Manifest_Printer SHALL produce `manifest.yaml` text that the Manifest_Parser accepts without error and that states Streak_Length explicitly, including when Streak_Length came from the default of 3.
6. IF a Level or Practice_Problem in the Manifest maps to a Concept that the Concept mapping does not declare, or a Practice_Problem's target Stage is outside 1 to 3 inclusive, THEN THE Manifest_Parser SHALL return an error naming the Level or Practice_Problem identifier, the field, and the invalid value, and THE Manifest_Parser SHALL return no Manifest object.
7. IF the Fallback_Path lists a Level that the Manifest's Levels do not declare, or leaves out a declared Level, THEN THE Manifest_Parser SHALL return an error naming each undeclared or missing Level, and THE Manifest_Parser SHALL return no Manifest object.
8. FOR ALL valid Manifest objects, printing with the Manifest_Printer and then parsing with the Manifest_Parser SHALL produce a Manifest object equal to the original in every field (round-trip property).

### Requirement 3: Synthetic weather dataset

**User Story:** As a curriculum author, I want a reproducible synthetic dataset, so that every run produces the same data and tests have stable expected answers.

#### Acceptance Criteria

1. WHEN the Dataset_Generator runs, THE Dataset_Generator SHALL create a Weather_Database with a `daily_readings` table containing exactly one row per station per calendar day for stations `ST-A`, `ST-B`, and `ST-C` over the 365 consecutive days from 2026-01-01 to 2026-12-31 inclusive, for a total of exactly 1,095 rows, with no duplicate (`station_id`, `date`) pairs and no NULL value in any of the five columns.
2. WHEN the Dataset_Generator runs twice with the same seed, THE Dataset_Generator SHALL produce Weather_Databases whose `daily_readings` tables contain identical rows, with every column value equal, when both tables are read ordered by `station_id` then `date`. If no seed is supplied, the Dataset_Generator SHALL use the fixed default seed stored in the Project's `dataset/` folder.
3. THE Dataset_Generator SHALL store each `date` value as a 10-character string in `YYYY-MM-DD` format that represents a valid calendar date, with zero-padded month and day.
4. THE Dataset_Generator SHALL produce, for each of the three stations, at least one day with `temp_high_c` exactly 35.0, at least one day with `temp_high_c` exactly 34.9, at least one day with `rain_mm` exactly 20.0, at least one day with `rain_mm` exactly 19.9, and at least one day with both `temp_high_c` >= 35.0 and `rain_mm` >= 20.0, so that boundary, near-boundary, and overlap cases appear in the data.
5. THE Dataset_Generator SHALL produce exactly 31 rows for station `ST-A` with dates from 2026-01-01 to 2026-01-31 inclusive, so that the Level 4 known-good report can be computed.
6. THE Dataset_Generator SHALL generate only synthetic values. The only `station_id` values SHALL be `ST-A`, `ST-B`, and `ST-C`, and the Weather_Database SHALL contain no columns or tables holding names, locations, or other personal or real-station information.
7. FOR ALL rows in the Weather_Database, THE Dataset_Generator SHALL produce `temp_low_c` less than or equal to `temp_high_c` and `rain_mm` greater than or equal to 0.0 (invariant).
8. FOR ALL rows in the Weather_Database, THE Dataset_Generator SHALL produce `temp_high_c` and `temp_low_c` values from -30.0 to 50.0 inclusive and `rain_mm` values from 0.0 to 200.0 inclusive, each rounded to exactly 1 decimal place.
9. IF the Dataset_Generator cannot write the Weather_Database (for example, the target folder is not writable), THEN THE Dataset_Generator SHALL report an error naming the target path, exit with a non-zero status, and leave no partially written `weather.db` file.
10. WHEN the Dataset_Generator runs and a `weather.db` file already exists at the target path, THE Dataset_Generator SHALL replace it, so that the resulting Weather_Database contains only the 1,095 newly generated rows.

### Requirement 4: Level 1, retrieve data from the database

**User Story:** As a student, I want to write a function that queries the weather database for one station and date range, so that I learn to retrieve data with parameterized SQL.

#### Acceptance Criteria

1. WHEN a student submits `get_readings(conn, station_id, start_date, end_date)`, THE Test_Grader SHALL call the function with `station_id` `ST-A`, `start_date` `2026-01-01`, and `end_date` `2026-01-31`, and SHALL verify that every returned row has `station_id` equal to `ST-A`.
2. WHEN a student submits `get_readings`, THE Test_Grader SHALL verify, for at least two station and date-range combinations in the Weather_Database, that the returned rows contain exactly one row for each date from `start_date` to `end_date`, inclusive on both ends, with no dates outside that range and no duplicate dates (31 rows for `ST-A` from `2026-01-01` to `2026-01-31`).
3. WHEN a student submits `get_readings`, THE Test_Grader SHALL verify that the function returns a Python list in which each element is a dictionary with exactly the keys `station_id`, `date`, `temp_high_c`, `temp_low_c`, and `rain_mm`, and each value equals the matching Weather_Database column value for that row.
4. WHEN a student submits `get_readings`, THE Test_Grader SHALL verify that the returned rows are in strictly ascending `date` order.
5. WHEN a student submits `get_readings`, THE Test_Grader SHALL call the function with a date range containing no Weather_Database rows for the requested station, and with a `start_date` later than `end_date`, and SHALL verify that each call returns an empty list and raises no exception.
6. WHEN a student submits `get_readings`, THE Test_Grader SHALL call the function with a `station_id` containing a single-quote character and SQL text that would match every row if inserted into the query by string formatting, and SHALL verify that the call returns an empty list, raises no exception, and leaves the `daily_readings` table with all 1,095 rows unchanged, which confirms the query uses parameter placeholders.
7. WHEN every check in criteria 1 through 6 passes, THE Test_Grader SHALL record the Level 1 Submission as passed.
8. IF any check in criteria 1 through 6 fails, or the `get_readings` call raises an exception, or the Submission does not define a function named `get_readings` that accepts four arguments, THEN THE Test_Grader SHALL record the Level 1 Submission as failed and return to the Feedback_Service each failing check, plus the exception type and message when an exception was raised.

### Requirement 5: Level 2, make decisions with conditionals

**User Story:** As a student, I want to write a function that labels one day's reading, so that I learn to use conditionals and boundary values.

#### Acceptance Criteria

1. WHEN a student submits `classify_day(row)`, THE Test_Grader SHALL call the function with a dictionary containing the keys `station_id`, `date`, `temp_high_c`, `temp_low_c`, and `rain_mm`, matching the `daily_readings` columns of the Weather_Database, and SHALL verify that the function returns a Python list of strings, each one of `"heat_wave"`, `"heavy_rain"`, or `"normal"`, with no repeated label.
2. WHEN a student submits `classify_day`, THE Test_Grader SHALL verify that a row with `temp_high_c` of 35.0 and `rain_mm` of 0.0 returns exactly `["heat_wave"]`, and that a row with `temp_high_c` of 34.9 and `rain_mm` of 0.0 returns exactly `["normal"]`.
3. WHEN a student submits `classify_day`, THE Test_Grader SHALL verify that a row with `rain_mm` of 20.0 and `temp_high_c` of 20.0 returns exactly `["heavy_rain"]`, and that a row with `rain_mm` of 19.9 and `temp_high_c` of 20.0 returns exactly `["normal"]`.
4. WHEN a student submits `classify_day`, THE Test_Grader SHALL verify that a row with `temp_high_c` greater than or equal to 35.0 and `rain_mm` greater than or equal to 20.0 returns exactly `["heat_wave", "heavy_rain"]`, in that order.
5. WHEN a student submits `classify_day`, THE Test_Grader SHALL verify that a row with `temp_high_c` less than 35.0 and `rain_mm` less than 20.0 returns exactly `["normal"]`, and that `"normal"` never appears in the same list as `"heat_wave"` or `"heavy_rain"`.
6. FOR ALL rows in the Weather_Database (1,095 rows) and at least 100 additional generated rows with `temp_high_c` from -30.0 to 50.0 and `rain_mm` from 0.0 to 100.0 at 0.1 resolution, THE Test_Grader SHALL verify that the student's `classify_day` output equals the Reference_Solution output, including label order (model-based property).
7. WHEN a student submits `classify_day`, THE Test_Grader SHALL verify that the input row dictionary has the same keys and values before and after the call.
8. IF the student's `classify_day` raises an exception or returns a value that is not a list for any test row, THEN THE Test_Grader SHALL mark the Level 2 Submission as failed and return a result naming the `temp_high_c` and `rain_mm` values of the first row that failed and whether the failure was an exception or a wrong return type.

### Requirement 6: Level 3, process every record with loops

**User Story:** As a student, I want to write a function that summarizes a list of classified readings with a loop, so that I learn accumulators and tracking a maximum.

#### Acceptance Criteria

1. WHEN a student submits `summarize(readings)`, where `readings` is a list of 0 to 365 classified readings and each classified reading is one Level 1 row dictionary paired with its Level 2 label list in the form given in the Level 3 instructions, THE Test_Grader SHALL verify that the returned value is a dictionary containing exactly the keys `heat_wave_days`, `heavy_rain_days`, `normal_days`, `total_rain_mm`, `max_temp_c`, and `flagged_dates`, with no missing and no extra keys.
2. WHEN a student submits `summarize`, THE Test_Grader SHALL verify that `heat_wave_days`, `heavy_rain_days`, and `normal_days` are integers equal to the number of readings whose label list contains `"heat_wave"`, `"heavy_rain"`, and `"normal"` respectively, using a hand-checked input of 5 to 10 readings that includes at least one reading at `temp_high_c` 35.0, at least one at `rain_mm` 20.0, at least one with both labels, and at least one labeled `"normal"`.
3. WHEN a student submits `summarize`, THE Test_Grader SHALL verify that `total_rain_mm` is a float equal to the sum of all `rain_mm` values in the input rounded to 1 decimal place, compared against the expected value also rounded to 1 decimal place.
4. WHEN a student submits `summarize` with a non-empty input, THE Test_Grader SHALL verify that `max_temp_c` is a float exactly equal to the highest `temp_high_c` value in the input, using an input where the highest value is neither the first nor the last reading.
5. WHEN a student submits `summarize`, THE Test_Grader SHALL verify that `flagged_dates` contains, in ascending date order and exactly once each, the date of every reading whose label list contains a label other than `"normal"`, using an input whose readings are not in ascending date order.
6. WHEN a student submits `summarize` with an empty input list, THE Test_Grader SHALL verify that `heat_wave_days`, `heavy_rain_days`, and `normal_days` are each 0, `total_rain_mm` is 0.0, `flagged_dates` is an empty list, and the function raises no exception.
7. THE Manifest SHALL define the value of `max_temp_c` for an empty input, and WHEN a student submits `summarize` with an empty input list, THE Test_Grader SHALL verify that `max_temp_c` equals that Manifest-defined value.
8. WHEN a student submits `summarize`, THE Loop_Checker SHALL verify that the `summarize` function body contains at least one `for` statement or `while` statement, where list, set, dictionary, and generator comprehensions do not count as a loop.
9. IF the `summarize` function body, including any function defined inside it, calls any of the built-in functions `sum`, `max`, `min`, `len`, or `sorted`, THEN THE Loop_Checker SHALL mark the Level 3 Submission as failed and return a message naming each banned call and its line number.
10. FOR ALL generated reading lists, using at least 100 lists of 0 to 365 readings each drawn from the Weather_Database and classified by the Reference_Solution `classify_day`, THE Test_Grader SHALL verify that `heat_wave_days + heavy_rain_days - both_days + normal_days` equals the number of readings, where `both_days` counts readings with both labels, and that every returned value equals the Reference_Solution `summarize` output (invariant and model-based property).
11. IF the `summarize` function body contains no `for` statement and no `while` statement, THEN THE Loop_Checker SHALL mark the Level 3 Submission as failed and return a message stating that `summarize` must use a `for` or `while` loop.
12. WHEN a Level 3 Submission is graded, THE Engine SHALL mark the Submission as passed only if every Test_Grader check in criteria 1 to 7 and 10 passes and the Loop_Checker finds at least one loop and no banned call, and otherwise THE Engine SHALL mark the Submission as failed and return the message for every failed output check and every failed Loop_Checker check from the same attempt.

### Requirement 7: Level 4, solve the full problem with functions

**User Story:** As a student, I want to combine my earlier functions into one report function, so that I learn to build a larger solution from small functions.

#### Acceptance Criteria

1. WHEN a student submits `build_report(conn, station_id, start_date, end_date)`, THE Test_Grader SHALL verify that the output for station `ST-A` from 2026-01-01 to 2026-01-31 is a dictionary with exactly the six keys defined for `summarize` in Requirement 6 and that every key's value equals the stored expected report for that station and range.
2. WHEN a student submits `build_report`, THE Test_Grader SHALL verify that the output for one station other than `ST-A`, over a date range of at least 7 consecutive days declared in the Level's tests, equals that range's stored expected report on every key.
3. WHEN a student submits `build_report` and the test passes a date range that matches no rows in the Weather_Database, THE Test_Grader SHALL verify that `build_report` raises no exception and returns the empty-input summary defined in Requirement 6, criteria 6 and 7.
4. WHEN a student submits `build_report`, THE Test_Grader SHALL verify that the Weather_Database has the same row count and identical row contents in `daily_readings` before and after each call.
5. WHEN a student submits `build_report`, THE Test_Grader SHALL call `build_report` twice in the same test with identical arguments and verify that both calls return equal dictionaries (idempotence).
6. WHEN a student submits `build_report`, THE Test_Grader SHALL verify, for one call over a non-empty date range, that `build_report` calls the student's `get_readings` exactly once with the given `conn`, `station_id`, `start_date`, and `end_date`, calls the student's `classify_day` once per returned row, and calls the student's `summarize` exactly once, with the calls in that order.
7. IF `build_report` does not call one or more of `get_readings`, `classify_day`, or `summarize`, THEN THE Test_Grader SHALL mark the Level 4 Submission as failed and return a message naming each function that was not called.
8. IF a `build_report` output differs from the stored expected report, THEN THE Test_Grader SHALL mark the Level 4 Submission as failed and return a result naming each key whose value differs, together with the station and date range tested.

### Requirement 8: Reference solution and expected values

**User Story:** As a curriculum author, I want expected values checked automatically against an independent computation, so that tests are trustworthy before a teacher reviews them.

#### Acceptance Criteria

1. WHEN the content check runs, THE Engine SHALL run every automated test for Levels 1, 2, 3, and 4 against the Reference_Solution, including the Loop_Checker checks for Level 3, and SHALL report the content check as passed only if every test passes.
2. FOR ALL `station_id` values in {`ST-A`, `ST-B`, `ST-C`} and all date ranges where `start_date` and `end_date` both fall within the 365 days in the Weather_Database and `start_date` is less than or equal to `end_date`, THE Reference_Solution `build_report` output SHALL equal the Independent_Checker output in every report field, with `total_rain_mm` compared after both values are rounded to 1 decimal place (model-based property).
3. WHEN expected report values are generated, THE Engine SHALL store each expected report together with its `station_id`, `start_date`, `end_date`, and the dataset seed used to produce it. The stored set SHALL include at least the two reports used by the Level 4 tests in Requirement 7.
4. IF a stored expected report differs from the Independent_Checker output for the same seed, station, and date range, THEN THE Engine SHALL fail the content check and report the station, the date range, and each differing field with its stored value and its computed value.
5. WHEN expected values for a Project are generated or regenerated, THE Engine SHALL set that Project's `teacher_reviewed` flag to false. The flag SHALL stay false until a teacher marks the values as reviewed.
6. IF any automated test fails against the Reference_Solution, THEN THE Engine SHALL fail the content check and report the Level number and the name of each failing test.
7. IF the seed stored with an expected report differs from the seed configured for the Project's Dataset_Generator, THEN THE Engine SHALL fail the content check and report both seed values and the affected expected reports.
8. WHILE a Project's `teacher_reviewed` flag is false, THE Engine SHALL state in the content check result that the expected values are unreviewed. The unreviewed status alone SHALL NOT fail the content check.

### Requirement 9: Running student code safely

**User Story:** As a student, I want my code to be graded without affecting the lesson or the database, so that a mistake in my code does not break my session.

#### Acceptance Criteria

1. WHEN the Test_Grader grades a code Submission, THE Test_Grader SHALL run the Submission in an operating-system process separate from the Engine process, against a new copy of the Weather_Database created for that Submission and not reused by any other Submission.
2. WHEN the Test_Grader finishes grading a code Submission with any result, THE Engine SHALL leave the original Weather_Database file with contents identical to its contents before grading started.
3. IF a code Submission process runs longer than 10 seconds of wall-clock time measured from process start, THEN THE Test_Grader SHALL stop the Submission process within 1 second, record the attempt as failed, and return a result to the student indicating that the Submission exceeded the 10-second time limit.
4. IF a code Submission has a syntax error or raises an exception during import, THEN THE Test_Grader SHALL record the attempt as failed without running the Level's tests, and SHALL return to the student the error message, the line number in the Submission where the error occurred, and the first hint for the Level.
5. IF a code Submission raises an exception or its process exits abnormally while the Level's tests run, THEN THE Test_Grader SHALL record the attempt as failed and return to the student the name of each test that did not pass and the exception message for each test that raised one.
6. IF the Test_Grader cannot start the Submission process or cannot create the Weather_Database copy, THEN THE Engine SHALL record the result as ungraded, leave the student's Stages and streak counts unchanged, show the student a plain-language message indicating that grading is unavailable, and keep the next Level's instructions on the Fallback_Path available to the student.
7. WHEN a code Submission process ends for any reason, including timeout, crash, or forced stop, THE Engine SHALL keep the student's session open and accept another Submission for the same Problem without the student restarting the Engine.

### Requirement 10: Open-ended responses graded by rubric

**User Story:** As a student, I want my written explanations scored against a clear rubric, so that I get credit for reasoning as well as working code.

#### Acceptance Criteria

1. WHEN a student submits a written response of 1 to 2,000 characters to a Level's open-ended prompt, THE Rubric_Grader SHALL return a Stage score that is an integer from 0 to 3 inclusive and a plain-language justification of 1 to 600 characters that names the rubric descriptor for the awarded Stage.
2. THE Rubric_Grader SHALL send all model requests through the Model_Provider.
3. WHERE a different model or provider is configured, THE Engine SHALL use the configured Model_Provider implementation without changes to Rubric_Grader source code.
4. IF the Model_Provider returns an error, does not respond within 30 seconds, or returns output that lacks an integer Stage score from 0 to 3 or a non-empty justification, THEN THE Rubric_Grader SHALL record the response as ungraded, keep the student's written response text saved, show the student a plain-language message that the response could not be graded, and THE Engine SHALL continue the student on the Fallback_Path.
5. THE Rubric_Grader SHALL load each rubric through the File_Store, and each rubric SHALL define one descriptor for each Stage from 0 to 3.
6. IF a submitted written response is empty, contains only whitespace, or exceeds 2,000 characters, THEN THE Rubric_Grader SHALL reject the response without sending it to the Model_Provider, show the student a message stating the allowed length of 1 to 2,000 characters, and keep the submitted text available for editing.
7. IF the File_Store cannot load the rubric for an open-ended prompt, THEN THE Rubric_Grader SHALL record the response as ungraded without sending a request to the Model_Provider, and THE Engine SHALL continue the student on the Fallback_Path.
8. WHEN the Rubric_Grader returns a Stage score for a written response, THE Engine SHALL pass the score, the Problem identifier, and the Concept mapped to the open-ended prompt to the Stage_Tracker as a graded result.

### Requirement 11: Validator agreement benchmark

**User Story:** As a product owner, I want to measure how often the AI rubric grader agrees with human raters, so that I can decide whether the mastery signal is trustworthy.

#### Acceptance Criteria

1. THE Engine SHALL include a Benchmark_Set of at least 20 written Submissions for Project 1, with at least 1 Submission for the open-ended prompt of each of Levels 1, 2, 3, and 4, where each Submission has a unique identifier, names the open-ended prompt it answers, and has exactly one human-assigned Stage score that is an integer from 0 to 3.
2. WHEN the benchmark runs, THE Engine SHALL grade every Benchmark_Set item with the Rubric_Grader and report the exact-agreement rate, calculated as the number of graded items whose Rubric_Grader score equals the human score divided by the number of graded items, as a percentage rounded to 1 decimal place.
3. WHEN the benchmark runs, THE Engine SHALL list, in ascending identifier order, each graded Benchmark_Set item where the Rubric_Grader score differs from the human score, showing the item identifier, the human score, and the Rubric_Grader score.
4. WHEN the benchmark finishes, THE Engine SHALL report pass if the exact-agreement rate is greater than or equal to the configured agreement threshold and report fail otherwise, where the agreement threshold is a percentage from 0 to 100 inclusive that defaults to 80 when not configured.
5. WHEN the benchmark runs, THE Engine SHALL report the within-one-Stage agreement rate, calculated as the number of graded items whose Rubric_Grader score differs from the human score by at most 1 Stage divided by the number of graded items, as a percentage rounded to 1 decimal place.
6. IF the Rubric_Grader records a Benchmark_Set item as ungraded, THEN THE Engine SHALL exclude that item from both agreement rates, report the count and identifiers of ungraded items, and report fail when no Benchmark_Set items were graded.
7. IF the configured agreement threshold is not a number from 0 to 100 inclusive, THEN THE Engine SHALL not run the benchmark and SHALL report an error indicating that the agreement threshold is invalid.

### Requirement 12: Content filtering

**User Story:** As a student, I want unsafe content kept out of my lesson, so that the learning experience stays appropriate for my age group.

#### Acceptance Criteria

1. WHEN a student submits a written response, THE Content_Filter SHALL screen the full response text and return a result of either allowed or blocked before the Rubric_Grader sends any part of the response to the Model_Provider.
2. WHEN the Model_Provider returns output, THE Content_Filter SHALL screen the full output text and return a result of either allowed or blocked before the Engine shows any part of the output to the student.
3. IF the Content_Filter blocks a student response, THEN THE Engine SHALL show the student a plain-language message asking for a revised response, keep the student on the same Problem, and send no part of the blocked response to the Model_Provider.
4. IF the Content_Filter blocks a student response, THEN THE Stage_Tracker SHALL leave every Concept's Stage and streak count unchanged, and THE Engine SHALL not record the blocked response as a graded or ungraded result.
5. IF the Content_Filter blocks model output, THEN THE Engine SHALL show the student the Level's pre-authored feedback message from the Level folder in place of the entire model output, and THE Rubric_Grader SHALL record the response as ungraded.
6. WHEN the Content_Filter blocks an item, THE Engine SHALL write one log entry that contains the Student_Id, Problem identifier, direction (input or output), blocked category, and timestamp, and that excludes the blocked text.
7. THE Content_Filter SHALL block any text that falls in at least one of these categories: profanity, sexual content, violence, self-harm, hate or harassment, and personal contact information such as email addresses or phone numbers.
8. IF the Content_Filter raises an error or cannot return a result, THEN THE Engine SHALL treat the screened item as blocked and apply the same behavior as for a blocked student response or blocked model output, depending on the item's direction.

### Requirement 13: Feedback and hints

**User Story:** As a student, I want clear feedback and step-by-step hints after a failed attempt, so that I can fix my work without being given the answer.

#### Acceptance Criteria

1. WHEN the Test_Grader reports one or more failing tests for a code Submission, THE Feedback_Service SHALL return one message per failing test, in the test order defined in the Problem's folder. Each message SHALL start with the Level number for a Level, or the Practice_Problem title for a Practice_Problem, followed by a colon. Each message SHALL name the input and the expected behavior that failed, in at most 200 characters, for example "Level 2: a temperature of 35.0 should count as a heat wave."
2. WHEN a student fails an attempt on a Problem, THE Feedback_Service SHALL offer exactly one hint: the first hint, in the order defined in the Problem's folder, that the student has not yet seen. THE Feedback_Service SHALL then mark that hint as seen for that student. A failed attempt is a code Submission with at least one failing test, a timeout, a syntax or import error, or a Loop_Checker failure.
3. WHILE a student has already seen every hint for a Problem, WHEN the student fails another attempt on that Problem, THE Feedback_Service SHALL offer the last hint in the defined order again.
4. THE Feedback_Service SHALL show only pre-authored hint text from the Problem's folder. THE Feedback_Service SHALL NOT include any Reference_Solution source code in a hint or feedback message.
5. THE Engine SHALL accept every Submission on every Problem regardless of how many earlier attempts failed, with no lockout and no waiting period between attempts. THE Engine SHALL increase that Problem's attempt count by 1 for each graded Submission.
6. IF a Problem defines zero hints, THEN THE Feedback_Service SHALL return the failure messages from criterion 1 with no hint, and THE Engine SHALL continue to accept Submissions on that Problem.
7. WHEN every test for a code Submission passes, THE Feedback_Service SHALL return a message stating that the Problem is passed, SHALL offer no hint, and SHALL leave the student's seen-hint record for that Problem unchanged.

### Requirement 14: Stage tracking per concept

**User Story:** As a student, I want my stage on each concept to rise when I show I can do the next stage's work, so that my progress reflects evidence and not luck.

#### Acceptance Criteria

1. WHEN a student starts a Project for the first time, THE Stage_Tracker SHALL set the student's Stage to 0 and the streak count to 0 for every Concept listed in the Manifest.
2. WHEN a Problem is graded, THE Stage_Tracker SHALL record, for each Concept the Manifest maps that Problem to, whether the graded result meets the Stage_Criteria for that Concept's current Stage plus one, and THE Stage_Tracker SHALL leave the Stage and streak count of every Concept the Problem does not map to unchanged.
3. WHEN a graded result meets the Stage_Criteria for the next Stage of a Concept, THE Stage_Tracker SHALL increase that Concept's streak count by 1.
4. WHEN a Concept's streak count reaches the Manifest's Streak_Length (3 if the Manifest omits it), THE Stage_Tracker SHALL raise that Concept's Stage by exactly one and reset that Concept's streak count to 0 within the same update.
5. IF a graded result for a Concept does not meet the next Stage's Stage_Criteria, THEN THE Stage_Tracker SHALL reset that Concept's streak count to 0 and leave that Concept's Stage unchanged.
6. THE Stage_Tracker SHALL keep each Concept's Stage between 0 and 3 inclusive, SHALL raise a Stage by at most one per graded result, and SHALL keep a Stage unchanged or raised after every update (invariant).
7. IF a Concept is already at Stage 3, THEN THE Stage_Tracker SHALL keep that Concept's Stage at 3 and its streak count at 0 for every later graded result.
8. IF a qualifying graded result is for a Problem that already added to the Concept's current streak, THEN THE Stage_Tracker SHALL leave that Concept's streak count unchanged, so that a streak counts only distinct Problems.
9. FOR ALL sequences of graded results, THE Stage_Tracker SHALL produce the same Stages and streak counts when the same sequence is replayed from Stage 0 with the same Manifest (determinism).
10. IF a result is recorded as ungraded, THEN THE Stage_Tracker SHALL leave the Stage and streak count of every Concept mapped to that Problem unchanged, and SHALL count the result as neither qualifying nor non-qualifying.

### Requirement 15: Cross-session progress

**User Story:** As a student, I want my stages and position in the lesson saved, so that I can continue where I stopped in a later session.

#### Acceptance Criteria

1. WHEN a Problem is graded, THE Engine SHALL save one progress record for the Student_Id and Project through the Progress_Store, containing each Concept's Stage, each Concept's streak count, the current Problem identifier, the attempt count for each Problem attempted, the hints seen for each Problem, the Levels passed, and whether the student is on the Fallback_Path. The Engine SHALL finish the save before it presents the next Problem.
2. WHEN a student opens a Project for which the Progress_Store holds a saved progress record for that Student_Id and Project, THE Engine SHALL restore every field listed in criterion 1 to its saved value and present the saved current Problem.
3. FOR ALL student progress records, saving then loading through the Progress_Store SHALL produce a record equal to the original in every field listed in criterion 1 (round-trip property).
4. THE Progress_Store SHALL key each progress record only by Student_Id and Project identifier, and SHALL store no name, email, or other personal information.
5. WHERE a different storage backend is configured, THE Engine SHALL use the configured Progress_Store and File_Store implementations without changes to Stage_Tracker or Router source code.
6. IF a saved progress record for the Student_Id and Project exists but the Progress_Store cannot read it or the record is missing a field listed in criterion 1, THEN THE Engine SHALL show the student a plain-language message saying that saved progress could not be loaded, set every Concept's Stage and streak count to 0, start the student on the Fallback_Path at Level 1, and leave the unreadable record unchanged in the Progress_Store.
7. IF the Progress_Store fails to save a progress record, THEN THE Engine SHALL show the student a plain-language message saying that progress was not saved, keep the unsaved progress in the current session so the student can continue, and save the full current progress record again when the next Problem is graded.

### Requirement 16: Adaptive routing

**User Story:** As a student, I want the lesson to pick my next problem from what I have shown, so that I practice what I need and move on when I am ready.

#### Acceptance Criteria

1. WHEN a student passes Level 1, 2, or 3 and the Concept mapped to that Level is at or above the required Stage for advancing that the Manifest declares for that Level (an integer from 1 to 3), THE Router SHALL select the next Level in the Manifest's Level order.
2. WHEN a student passes Level 1, 2, or 3 and the Concept mapped to that Level is below the Manifest's required Stage for advancing, THE Router SHALL select the first Practice_Problem, in Manifest order, that is mapped to that Concept, has a target Stage equal to the Concept's current Stage plus one, and has not yet been passed by the student.
3. IF the Router would assign a Practice_Problem under criterion 2 or criterion 8 and no Practice_Problem meets all of that criterion's conditions, THEN THE Router SHALL select the next Level in the Manifest's Level order.
4. THE Router SHALL select only Problems whose identifiers are listed in the Project Manifest.
5. FOR ALL combinations of Stages, streak counts, passed Problems, current Problem, and Manifest, THE Router SHALL return the same Problem each time it receives the same inputs (determinism).
6. WHEN the Router selects a Problem, THE Engine SHALL record, through the Progress_Store, the Student_Id, the selected Problem identifier, the Stage of every Concept used for the selection, the reason for the selection (next Level, Practice_Problem assigned, or no Practice_Problem remaining), and a timestamp.
7. WHEN a student passes Level 3 and any Practice_Problems the Router assigns after Level 3, THE Router SHALL select Level 4 for every student, whatever that student's Stages are.
8. WHEN a student passes a Practice_Problem, THE Router SHALL select the Level after the Level that led to the Practice_Problem if the Practice_Problem's Concept is now at or above that Level's required Stage for advancing, and SHALL otherwise select the next Practice_Problem using the rule in criterion 2.
9. IF a student's Submission for a Problem does not pass, THEN THE Router SHALL keep that same Problem as the student's current Problem.
10. WHEN a student passes Level 4, THE Router SHALL mark the Project as complete for that student and SHALL select no further Problem.

### Requirement 17: Non-adaptive fallback path

**User Story:** As a student, I want the lesson to keep working when grading or routing breaks, so that I am never stuck on a broken screen.

#### Acceptance Criteria

1. IF the Router raises an error or returns a Problem identifier not listed in the Manifest, THEN THE Engine SHALL discard the Router's result, switch the student to the Fallback_Path, and select the Level that follows, in Fallback_Path order, the highest-numbered Level the student has passed.
2. IF the Rubric_Grader records a response to a Level's open-ended prompt as ungraded, THEN THE Engine SHALL switch the student to the Fallback_Path and select the Level that follows, in Fallback_Path order, the Level that contains that prompt.
3. WHILE a student is on the Fallback_Path, THE Engine SHALL present only Levels, in the order 1, 2, 3, 4, SHALL present no Practice_Problems, and SHALL present the next Level only after the student passes the current Level.
4. WHILE a student is on the Fallback_Path, THE Engine SHALL skip every Level the student has already passed and SHALL keep the student on the Fallback_Path until the student passes Level 4 or the Project is restarted.
5. IF the Engine must select the next Level on the Fallback_Path and the student has already passed Level 4, THEN THE Engine SHALL mark the Project as complete for the student and SHALL show a plain-language message saying the Project is complete.
6. WHEN the Engine switches a student to the Fallback_Path, THE Engine SHALL leave the student's Stages, streak counts, attempt counts, and hints seen unchanged, and SHALL save the student's Fallback_Path status through the Progress_Store so the status is restored in a later session.
7. WHEN the Engine switches a student to the Fallback_Path, THE Engine SHALL show the student the selected Level's instructions together with a plain-language message saying the lesson will continue in fixed order, and SHALL show no error trace, exception text, or internal identifier.
8. WHERE adaptive routing is disabled in configuration, THE Engine SHALL place every student on the Fallback_Path starting at the lowest-numbered Level the student has not passed, and SHALL not call the Router.
9. WHEN the Engine switches a student to the Fallback_Path, THE Engine SHALL write one log entry containing the Student_Id, the identifier of the Problem the student was on, the failure reason (router error, Problem not in Manifest, ungraded response, Progress_Store load failure, or adaptive routing disabled), and a timestamp.

### Requirement 18: Student view of progress

**User Story:** As a student, I want to see my stage on each concept and my current problem, so that I understand where I am in the lesson.

#### Acceptance Criteria

1. WHEN a student requests progress, THE Engine SHALL show, for every Concept listed in the Project Manifest and in Manifest order, the student's Stage number (0 to 3) and the matching Stage name (0 Missing, 1 Beginning, 2 Meeting, 3 Exceeding). The values shown SHALL equal the values saved through the Progress_Store after the student's most recently graded Problem.
2. WHEN a student requests progress, THE Engine SHALL show the title of the student's current Problem, whether it is a Level or a Practice_Problem, and the numbers of all Levels the student has passed in ascending order. If the student has passed no Levels, THE Engine SHALL show an indication that no Levels are passed. If the student has passed Level 4, THE Engine SHALL show an indication that the Project is complete in place of a current Problem title.
3. WHEN a student requests progress, THE Engine SHALL show, for each Concept below Stage 3, the student's current streak count (an integer from 0 to Streak_Length minus 1) together with the Manifest's Streak_Length. For each Concept at Stage 3, THE Engine SHALL show an indication that the Concept is at the highest Stage and SHALL show no streak count.
4. IF a student requests progress for a Project the student has not started, THEN THE Engine SHALL show Stage 0 (Missing) for every Concept in the Manifest, a streak count of 0 for every Concept, Level 1 as the current Problem, and no passed Levels.
5. IF the Progress_Store cannot load the student's saved record when the student requests progress, THEN THE Engine SHALL show a plain-language message saying that progress could not be loaded, SHALL show no Stage or streak values, and SHALL leave the saved record unchanged.
6. WHEN a student requests progress, THE Engine SHALL leave the student's Stages, streak counts, current Problem, attempt counts, and hints seen unchanged.

### Requirement 19: Data privacy in the prototype

**User Story:** As a product owner, I want the prototype to use no real student data, so that we meet CodeAI's privacy rules from the start.

#### Acceptance Criteria

1. WHEN the Engine creates a new student record, THE Engine SHALL generate the Student_Id only from a random source, independent of any user-supplied input, so that creating two students with identical inputs produces two different Student_Id values.
2. WHEN the Engine creates a new student record, THE Engine SHALL assign a Student_Id that differs from every Student_Id already saved in the Progress_Store, so that 10,000 consecutively generated Student_Id values contain no duplicates.
3. THE Engine SHALL accept no student name, email address, birth date, school name, or other personal information as input when creating a student record or starting a Project.
4. WHEN the Rubric_Grader sends a request to the Model_Provider, THE Engine SHALL include only the written response text that passed the Content_Filter, the rubric text, and the open-ended prompt text, and SHALL exclude the Student_Id, Stages, streak counts, attempt counts, and every other student's responses.
5. WHEN the benchmark sends a Benchmark_Set item to the Model_Provider, THE Engine SHALL include only that item's written response text, the rubric text, and the open-ended prompt text.
6. WHEN the Engine writes a log entry that refers to a student, including blocked-content entries, Fallback_Path switch entries, and routing decision records, THE Engine SHALL identify the student only by Student_Id and SHALL include no name, email address, or other personal information.
7. IF a log entry, Progress_Store record, or Model_Provider request is about to be written or sent with a field that holds personal information or, for a Model_Provider request, a Student_Id, THEN THE Engine SHALL not write or send that item and SHALL report an error naming the field that was rejected.

### Requirement 20: Student-chosen project themes

**User Story:** As a student, I want to ask for the project in a theme I like, such as Pokémon, so that I stay engaged while I practice the same skills as my class.

#### Acceptance Criteria

1. WHEN a student submits a theme request of 1 to 300 characters, THE Engine SHALL screen it with the Content_Filter before any model call that designs the theme.
2. IF the Content_Filter blocks the request or cannot return a result, THEN THE Engine SHALL refuse the request with a plain-language message, make no theme-design model call, and keep the student on their current project.
3. WHEN a request is allowed, THE Engine SHALL obtain a theme spec from the Model_Provider through a forced structured tool call. The spec SHALL contain only titles, story text, names, identifiers, and number ranges.
4. THE Engine SHALL validate every identifier in the spec against a lowercase pattern and against SQL keywords, Python keywords, and Python built-in names before using it in SQL or Python source.
5. IF the spec fails validation, THEN THE Engine SHALL ask the Model_Provider again with the validation errors, up to 3 attempts in total, and SHALL report a failure after the last attempt.
6. WHEN a spec is valid, THE Engine SHALL generate the themed project's dataset, checks, hints, and reference solution from templates, so that a themed project has the same four levels, the same concepts, and the same kinds of checks as Project 1.
7. THE Engine SHALL run the content check (Requirement 8) on the generated project and SHALL make the project available to the student only if the check passes. IF the check fails, THEN THE Engine SHALL delete the generated project and keep the student on their current project.
8. THE Engine SHALL screen every piece of student-visible text in the spec (title, story, descriptions, group names, and item names) with the Content_Filter, and SHALL treat a blocked text as a validation failure.
9. WHEN a themed project is ready, THE Engine SHALL save it as the student's active project, so that later show, submit, and progress commands use it until the student resets to the standard project.
10. THE Engine SHALL state in the themed instructions that the names may be real but the numbers are made up for practice.

### Requirement 21: AI tutor hints

**User Story:** As a student, I want a hint about my actual mistake, so that I can fix my code without being given the answer.

#### Acceptance Criteria

1. WHEN a code Submission fails and a Model_Provider is configured, THE Engine SHALL request one hint that is built from the Problem instructions, the failure messages, the pre-authored hints, and the Submission code.
2. THE Engine SHALL send no Student_Id and no Reference_Solution source to the Model_Provider.
3. IF the Submission code is blocked by the Content_Filter, THEN THE Engine SHALL not send it to the Model_Provider and SHALL use the pre-authored hint.
4. IF the model reply is empty, longer than 400 characters, contains a code block, a statement line, a def statement, a complete SQL query, or any line of the Reference_Solution, or is blocked by the Content_Filter, THEN THE Engine SHALL discard it and use the pre-authored hint.
5. IF the Model_Provider returns an error or times out, THEN THE Engine SHALL use the pre-authored hint.
6. THE Engine SHALL count an AI hint as a hint seen for stage criteria, the same as a pre-authored hint.
7. WHEN a hint is shown, THE Engine SHALL log its source (ai or authored), the Problem identifier, and for AI hints the model identifier and latency, identifying the student only by Student_Id.
8. WHERE AI features are turned off in configuration, THE Engine SHALL use only pre-authored hints and make no model calls.

### Requirement 22: Cross-project student profile

**User Story:** As a student, I want what I've already shown to carry into my next project, so that I don't start from zero every time.

#### Acceptance Criteria

1. THE Engine SHALL keep one profile per Student_Id with a Stage for every Concept in the catalog, the active project, the completed projects with their evidence, and the current next step.
2. WHEN a Problem is graded, THE Engine SHALL set each Concept's profile Stage to the higher of its profile Stage and its Stage in the current project.
3. WHEN a student starts a project, THE Engine SHALL start each of its Concepts at the student's profile Stage.
4. IF a profile can't be read, THEN THE Engine SHALL treat it as empty and continue.

### Requirement 23: Next step after a project

**User Story:** As a student, I want the lesson to pick what I do after a project, so that I'm challenged when I'm ready and supported when I'm not.

#### Acceptance Criteria

1. WHEN a student completes a project, THE Engine SHALL judge each Concept the student worked on as strong, struggled, or steady, using thresholds from the catalog file. The defaults are: strong means every Problem for the Concept passed in 2 attempts or fewer with 1 hint or fewer; struggled means any Problem took 4 or more attempts or 2 or more hints, or the student was assigned a Practice_Problem for that Concept.
2. IF any Concept is struggled, THEN THE Engine SHALL recommend the revision project for the struggled Concept with the most attempts and hints, and SHALL also offer the next topic.
3. IF the struggled Concept's revision project is the one just completed, THEN THE Engine SHALL recommend the next topic and SHALL offer the revision project again.
4. IF every Concept is strong, THEN THE Engine SHALL recommend the uncompleted topic whose Concepts have the lowest average profile Stage, with ties broken by catalog order.
5. IF the result is steady, the topic is themeable, and AI features are on, THEN THE Engine SHALL recommend the same topic in a new theme and SHALL also offer the next topic. Otherwise it SHALL recommend the next topic.
6. IF no uncompleted topic remains, THEN THE Engine SHALL report that every topic is finished.
7. THE Engine SHALL give every recommendation a plain-language reason and the evidence used, and SHALL log it with the Student_Id only.
8. WHEN a student starts a recommended option, THE Engine SHALL make that project active with a fresh progress record.

### Requirement 24: Revision projects and check-for-understanding quizzes

**User Story:** As a student who found a concept hard, I want a short review with questions and a guided task, so that I understand it before moving on.

#### Acceptance Criteria

1. THE catalog SHALL map every Concept to a revision project made of a review quiz followed by a scaffolded coding task on the same Concept.
2. A quiz SHALL contain "predict the output" questions with choices and one correct answer, and "explain" questions with a rubric descriptor for each Stage from 0 to 3.
3. THE Engine SHALL send no answers, explanations, or rubrics to the student before grading.
4. WHEN a student answers a "predict" question wrongly, THE Engine SHALL fail the attempt and show that question's explanation. Attempts are unlimited.
5. WHEN a student answers an "explain" question, THE Engine SHALL screen the text with the Content_Filter, score it with the Rubric_Grader, and show the score and feedback. IF grading fails, THEN THE Engine SHALL save the answer as ungraded and SHALL not block the student.
6. THE explain score SHALL NOT change Stages until the Rubric_Grader meets the agreement benchmark in Requirement 11.
7. THE content check SHALL run every "predict" snippet and fail when its output doesn't match exactly one choice, the one marked correct.
8. A scaffolded starter file SHALL fail its coding task's checks until the student completes it.
