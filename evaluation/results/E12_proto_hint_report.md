# E12 on proto-branch: AI tutor hints vs. teacher-written hints

Run `run-20261104T200225Z-proto-hints-4421`. Code under test: proto-branch `engine/hints.py` (`AIHinter`, unchanged), hint model `us.anthropic.claude-haiku-4-5-20251001-v1:0`. 12 seeded bugs (`harness/proto_bugs.py`) x attempts 1-3, graded by proto's own grader so the hint sees the real check messages. Judge: `us.anthropic.claude-sonnet-4-6` on the E12 sheet (`protocols/E12_E13_E15_instruments.md`), temperature 0, with the ground-truth bug description. **The judge is not yet validated against human raters**; the rating sheet for that is `annotation/E12_proto_hint_rating_sheet.csv`.

## Summary

| | AI hint (raw) | Teacher-written | What the student saw (AI, or teacher hint after a rejection) |
|---|---|---|---|
| Hints | 36 | 36 | 36 |
| H1 accurate (0-1) | 0.97 | 0.47 | 0.94 |
| H2 Socratic (0-2) | 0.33 | 0.47 | 0.36 |
| H3 strength fits attempt (0-2) | 1.03 | 0.61 | 1.06 |
| H4 grade-appropriate (0-1) | 1.0 | 1.0 | 1.0 |
| H5 safe and kind (0-1) | 1.0 | 1.0 | 1.0 |
| Gives the answer (H2 = 0) | 0.694 | 0.528 | 0.667 |
| Fix can be followed literally | 0.694 | 0.444 | 0.667 |
| AgentCore custom H2 evaluator (0-2) | 0.31 | 0.28 | 0.33 |
| AgentCore: gives the answer | 0.722 | 0.722 | 0.694 |
| AgentCore Builtin.Harmfulness (1 = not harmful) | 1.0 | 1.0 | 1.0 |
| AgentCore Builtin.Helpfulness (0-1) | 0.61 | 0.53 | 0.61 |

## By attempt (judge H2, H3, share that gives the fix)

| Attempt | AI H2 | AI H3 | AI gives fix | Teacher H2 | Teacher H3 | Teacher gives fix |
|---|---|---|---|---|---|---|
| 1 | 0.33 | 0.5 | 0.67 | 0.83 | 0.67 | 0.17 |
| 2 | 0.33 | 1.25 | 0.75 | 0.25 | 0.67 | 0.58 |
| 3 | 0.33 | 1.33 | 0.67 | 0.33 | 0.5 | 0.58 |

Escalation (help gets the same or stronger from attempt 1 to 3, judge H2): AI 8/12 bugs; non-monotonic: L1-string-concat, L1-tuples, L2-always-normal, L2-strict-threshold. Teacher hints: 8/12.

## Proto's output guard and cost

- AI hints rejected by proto (fell back to the teacher hint): 2/36 (copies the reference solution, too long).
- Latency P50 1010 ms, P95 1247 ms. Tokens per hint: 1110 in / 64 out; about $0.001572 per hint (prices in `bedrock_client.py`, verify before quoting).
- Proto logs `latency_ms` and `model_id` for hints but not tokens or cost; this harness adds them in `results/event_log_run-20261104T200225Z-proto-hints-4421.jsonl`.

Our judge vs. the AgentCore custom H2 evaluator on AI hints: exact agreement 0.806, Cohen's kappa 0.546. Both are LLM judges on the same model; agreement between them is not evidence of agreement with teachers.

## AI hints rated 'gives the answer' (H2 = 0)

| Bug | Attempt | Rejected by proto | Hint |
|---|---|---|---|
| L1-exclusive-range | 2 | no | Look at your WHERE clause for the dates. You're using `>` and `<`, but the problem asks you to include both the start and end dates. What comparison operators should you use to include the boundary dates? |
| L1-exclusive-range | 3 | no | Look at your WHERE clause conditions for the dates. You're using `>` and `<`, but the problem asks you to include both the start_date and end_date themselves. What comparison operators should you use instead? |
| L1-tuples | 2 | no | Your query and parameters look great! The issue is that `cursor.fetchall()` returns tuples, but the task requires a list of dictionaries. Look at how you can use `cursor.description` to get column names, then zip them wi |
| L1-string-concat | 1 | no | Look at your WHERE clause. You're using string concatenation (`+`) to put the values directly into the SQL, but the error says "no such column: ST" — Python is treating `station_id` as a column name instead of a value. U |
| L1-string-concat | 3 | no | Look at how you're building the SQL string—you're using `+` to concatenate `station_id`, `start_date`, and `end_date` directly into the query. The error "no such column: ST" tells you the database is treating these value |
| L1-no-order | 1 | no | Look at your ORDER BY clause. You're currently sorting by rain_mm, but the test expects the results sorted by date from oldest to first. Which column should you be sorting by instead? |
| L1-no-order | 2 | no | Look at your ORDER BY clause—you're sorting by rain_mm, but the test wants the rows sorted by date with the oldest first. Which column should you order by instead? |
| L1-no-order | 3 | no | Look at your ORDER BY clause. You're sorting by rain_mm, but the test wants the results sorted by date with the oldest first. Which column should you be sorting by instead? |
| L2-strict-threshold | 1 | no | Look at your comparison operators in the two if statements. The problem says "35.0 or more" should count, but you're using `>` instead of `>=`. Should 35.0 exactly be included or excluded? |
| L2-strict-threshold | 2 | no | Look at your comparison operators in the two if statements. The problem says "35.0 or more" should count, but you're using `>` instead of `>=`. Should 35.0 exactly trigger the label, or only values greater than 35.0? |
| L2-elif | 1 | no | Look at your if/elif/else structure. Right now, when the heat wave condition is true, the elif never runs. You need two separate if statements instead so both conditions can be checked independently. Should a day with 35 |
| L2-elif | 2 | no | Look at your if/elif/else structure. Right now, if the heat wave condition is true, the other conditions never get checked. Try using two separate if statements instead of elif, so a day can earn both labels before check |
| L2-elif | 3 | no | Look at your if/elif/else structure. When you use `elif`, the second condition is only checked if the first one is false. Since a day can be both a heat wave AND heavy rain, should you use `elif` for the rain check, or a |
| L2-always-normal | 1 | no | Look at the last line of your function. You're always appending "normal" to the list, even when the day already has heat wave or heavy rain labels. You should only add "normal" if the labels list is still empty—use an if |
| L3-builtins | 2 | no | Look at lines 37-41 where you're using `len()`, `sum()`, and `max()`. Instead, set up counter variables before your loop (like `heat_wave_days = 0`), then increment them inside the loop as you check each label. Do the sa |
| L3-builtins | 3 | no | You're using `len()`, `sum()`, and `max()` in your return dictionary, but the assignment asks you to build these values manually with a loop. Before your loop, create counter variables set to 0, a rain total at 0.0, and  |
| L3-no-round-sort | 1 | no | Look at how you're adding dates to `flagged_dates`. You're using `insert(0, ...)` which puts each new date at the front, but the problem asks for oldest first. Instead, append dates to the list, then sort it after the lo |
| L3-no-round-sort | 2 | no | Look at how you're adding dates to `flagged_dates` — you're using `insert(0, ...)` which puts each new date at the front. Instead, just append dates to the list, then sort it once after the loop finishes. This way the da |
| L3-no-round-sort | 3 | no | Look at how you're adding dates to `flagged_dates`. Right now you're using `insert(0, ...)` which puts each new date at the front, but you need to add all flagged dates to the list first, then sort them at the end using  |
| L4-reimplements-sql | 1 | copies the reference solution | Look at your `build_report` function. You're querying the database directly instead of calling your `get_readings` function. Also, you're only returning two fields instead of using `summarize` to build the complete repor |
| L4-reimplements-sql | 2 | no | Look at your `build_report` function—it's writing its own query instead of calling `get_readings`. Use `get_readings` to fetch the data, then loop through each row calling `classify_day` on it, collect the (row, labels)  |
| L4-reimplements-sql | 3 | too long | Look at your `build_report` function. You're querying the database directly instead of calling `get_readings` like the hint suggests. Also, you're only returning two fields, but `summarize` returns six fields including ` |
| L4-rows-not-pairs | 1 | no | Look at your `build_report` function. You're passing `rows` directly to `summarize`, but `summarize` expects a list of pairs—each pair should be `(row, labels)`. You need to loop through the rows and call `classify_day`  |
| L4-rows-not-pairs | 2 | no | Look at your `build_report` function. You're passing `rows` directly to `summarize`, but `summarize` expects a list of pairs `(row, labels)`. You need to loop through each row, call `classify_day` on it, and build a list |
| L4-rows-not-pairs | 3 | no | Look at your `build_report` function. You're passing `rows` directly to `summarize`, but `summarize` expects a list of pairs like `(row, labels)`. You need to loop through each row, call `classify_day` on it, and build t |

## Teacher-written hints rated 'gives the answer' (H2 = 0)

| Level | Attempt | Hint |
|---|---|---|
| level-1 | 2 | Use ? in the SQL for each value and pass the values as a tuple: conn.execute(sql, (station_id, start_date, end_date)). Dates in YYYY-MM-DD format sort correctly as text, so >= and <= work on them. |
| level-1 | 3 | ORDER BY date sorts the rows. To turn each row into a dictionary, cursor.description gives the column names, and zip(names, values) pairs them up. |
| level-2 | 2 | "35.0 or more" means >= 35.0, not > 35.0. Check the heat wave first and heavy rain second, using two separate if statements so a day can get both labels. |
| level-2 | 1 | Start with an empty list, labels = [], and add a label for each condition that is true. |
| level-2 | 3 | After both checks, if the list is still empty, the day is normal. Return the list at the end. |
| level-3 | 2 | Inside the loop, write for row, labels in readings: and use if "heat_wave" in labels: to add 1 to a counter. Add row["rain_mm"] to the total on every pass. |
| level-3 | 3 | For the highest temperature, replace max_temp when it is None or when the new temperature is bigger. After the loop, call flagged_dates.sort() and round the total with round(total, 1). |
| level-3 | 1 | Before the loop, set up a variable for each answer: counters at 0, total rain at 0.0, max temperature at None, and an empty list for flagged dates. |
| level-4 | 2 | Start with rows = get_readings(conn, station_id, start_date, end_date). Then make an empty list and, in a loop, append (row, classify_day(row)) for each row. |
| level-4 | 3 | The last line should be return summarize(readings). Call each function by name so the checker can see you used it. |

Seeded bugs and synthetic attempts only (the same code is resubmitted on attempts 2 and 3). Real students change their code between attempts.
