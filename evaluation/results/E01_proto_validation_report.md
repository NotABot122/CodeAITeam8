# E01 on proto-branch: validation (auto-checks) vs. a draft human key

Proto's validation service is the automated checks in `projects/weather-station/levels/*/checks.py` plus the Level 3 loop rule (commit 745b446, unchanged). Each submission below replaces one function in an otherwise correct file. The key is a **draft** from the evaluation team, based only on the level instructions; it needs teacher review.

- Scored submissions: 25 (plus 2 marked `review` for a teacher).
- Agreement with the key: **0.92**, Cohen's kappa **0.841**.
- False fail (valid code rejected): **0** 
- False pass (broken requirement accepted): **2** V-L2-05, V-L4-04

| ID | Key | Grader | Why (key) | First message the student sees |
|---|---|---|---|---|
| V-L1-01 | pass | pass | BETWEEN is inclusive on both ends. | Level 1: passed. Every check works. |
| V-L1-02 | pass | pass | Builds each dictionary by hand with a loop. | Level 1: passed. Every check works. |
| V-L1-03 | pass | pass | SELECT * (the table has exactly the five columns). | Level 1: passed. Every check works. |
| V-L1-04 | pass | pass | Uses sqlite3.Row on a new cursor-level row factory. | Level 1: passed. Every check works. |
| V-L1-05 | pass | pass | Named placeholders (:station) are still placeholders. | Level 1: passed. Every check works. |
| V-L1-06 | fail | fail | f-string with quotes: works on normal ids but breaks the placeholder rule (SQL injection). | Level 1: the station ID ' OR '1'='1 should match no rows, but 1095 came back. Use ? placeholders instead of putting values into the SQL text. |
| V-L1-07 | fail | fail | No station filter. | Level 1: asking for station ST-A returned rows that aren't for ST-A. |
| V-L1-08 | fail | fail | Sorted newest first. | Level 1: rows should be sorted by date, oldest first. Try ORDER BY date. |
| V-L1-09 | review | pass | Reads all rows and filters in Python; no values in the SQL, so no placeholders needed. Meets the outputs, not the spirit of 'database retrieval'. | Level 1: passed. Every check works. |
| V-L2-01 | pass | pass | Literal thresholds instead of constants. | Level 2: passed. Every check works. |
| V-L2-02 | pass | pass | if/elif chain that covers all four cases explicitly. | Level 2: passed. Every check works. |
| V-L2-03 | fail | fail | Labels in the wrong order for a hot and wet day. | Level 2: 35.0 °C with 20.0 mm should return ["heat_wave", "heavy_rain"] (got ['heavy_rain', 'heat_wave']). |
| V-L2-04 | fail | fail | Changes the row dictionary (instructions: don't change row). | Level 2: classify_day should not change the row dictionary it is given. |
| V-L2-05 | fail | pass **(disagree)** | Threshold 34.95: wrong rule (35.0 or more), only visible for 34.95-34.99 values. | Level 2: passed. Every check works. |
| V-L2-06 | fail | fail | Returns a string, not a list. | Level 2: classify_day should return a list, but it returned 'normal'. |
| V-L2-07 | fail | fail | Rounds the temperature first, so 34.5-34.9 count as a heat wave. | Level 2: a temperature of 34.9 is not a heat wave, so it should be normal (got ['heat_wave']). |
| V-L3-01 | pass | pass | while loop with an index. | Level 3: passed. Every check works. |
| V-L3-02 | pass | pass | Counts with a dictionary of counters. | Level 3: passed. Every check works. |
| V-L3-03 | pass | pass | Uses 'if not readings' for the empty case (no banned call). | Level 3: passed. Every check works. |
| V-L3-04 | fail | fail | Calls len() for the empty check (banned by the instructions). | Level 3: summarize must not call len() (line 35). Work it out with a loop instead. |
| V-L3-05 | fail | fail | Uses sorted() (banned by the instructions). | Level 3: summarize must not call sorted() (line 45). Work it out with a loop instead. |
| V-L3-06 | review | pass | Avoids the ban with readings.__len__() and builtins.max via getattr: follows the letter, not the intent. | Level 3: passed. Every check works. |
| V-L3-07 | fail | fail | Counts heavy rain from rain_mm > 20 instead of the labels (wrong at exactly 20.0). | Level 3: for 7 test days, heavy_rain_days should be 2, but was 1. |
| V-L4-01 | pass | pass | List comprehension for the pairs. | Level 4: passed. Every check works. |
| V-L4-02 | pass | pass | Keyword arguments and a separate pairs variable. | Level 4: passed. Every check works. |
| V-L4-03 | fail | fail | Calls get_readings twice (instructions: once). | Level 4: build_report should call get_readings exactly once. |
| V-L4-04 | fail | pass **(disagree)** | Hard-codes the stored January answer for ST-A (the real stored values) and computes the rest. | Level 4: passed. Every check works. |

Pass/fail agreement is only half of the customer requirement. Proto's mastery signal (Stage 0-3) comes from attempt and hint counts on a pass, not from the quality of the code, so two passing submissions get the same stage whatever their quality. A rubric-based score (requirements 10-11 in proto's own spec) is still missing.
