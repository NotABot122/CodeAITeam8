# E12 on proto-branch: AI tutor hints vs. teacher-written hints

Run `run-20261104T180914Z-proto-hints-33b1`. Code under test: proto-branch `engine/hints.py` (`AIHinter`, unchanged), hint model `us.anthropic.claude-haiku-4-5-20251001-v1:0`. 12 seeded bugs (`harness/proto_bugs.py`) x attempts 1-3, graded by proto's own grader so the hint sees the real check messages. Judge: `us.anthropic.claude-sonnet-4-6` on the E12 sheet (`protocols/E12_E13_E15_instruments.md`), temperature 0, with the ground-truth bug description. **The judge is not yet validated against human raters**; the rating sheet for that is `annotation/E12_proto_hint_rating_sheet.csv`.

## Summary

| | AI hint (raw) | Teacher-written | What the student saw (AI, or teacher hint after a rejection) |
|---|---|---|---|
| Hints | 36 | 36 | 36 |
| H1 accurate (0-1) | 0.97 | 0.47 | 0.97 |
| H2 Socratic (0-2) | 0.36 | 0.47 | 0.33 |
| H3 strength fits attempt (0-2) | 0.94 | 0.56 | 0.92 |
| H4 grade-appropriate (0-1) | 1.0 | 1.0 | 1.0 |
| H5 safe and kind (0-1) | 1.0 | 1.0 | 1.0 |
| Gives the answer (H2 = 0) | 0.75 | 0.528 | 0.778 |
| Fix can be followed literally | 0.75 | 0.444 | 0.778 |
| AgentCore custom H2 evaluator (0-2) | 0.22 | 0.22 | 0.19 |
| AgentCore: gives the answer | 0.778 | 0.778 | 0.806 |
| AgentCore Builtin.Harmfulness (1 = not harmful) | 1.0 | 1.0 | 1.0 |
| AgentCore Builtin.Helpfulness (0-1) | 0.62 | 0.53 | 0.63 |

## By attempt (judge H2, H3, share that gives the fix)

| Attempt | AI H2 | AI H3 | AI gives fix | Teacher H2 | Teacher H3 | Teacher gives fix |
|---|---|---|---|---|---|---|
| 1 | 0.42 | 0.42 | 0.75 | 0.83 | 0.58 | 0.17 |
| 2 | 0.42 | 1.17 | 0.75 | 0.25 | 0.67 | 0.58 |
| 3 | 0.25 | 1.25 | 0.75 | 0.33 | 0.42 | 0.58 |

Escalation (help gets the same or stronger from attempt 1 to 3, judge H2): AI 10/12 bugs; non-monotonic: L2-elif, L3-builtins. Teacher hints: 8/12.

## Proto's output guard and cost

- AI hints rejected by proto (fell back to the teacher hint): 1/36 (copies the reference solution).
- Latency P50 984 ms, P95 2978 ms. Tokens per hint: 1110 in / 64 out; about $0.001574 per hint (prices in `bedrock_client.py`, verify before quoting).
- Proto logs `latency_ms` and `model_id` for hints but not tokens or cost; this harness adds them in `results/event_log_run-20261104T180914Z-proto-hints-33b1.jsonl`.

Our judge vs. the AgentCore custom H2 evaluator on AI hints: exact agreement 0.694, Cohen's kappa 0.208. Both are LLM judges on the same model; agreement between them is not evidence of agreement with teachers.

## AI hints rated 'gives the answer' (H2 = 0)

| Bug | Attempt | Rejected by proto | Hint |
|---|---|---|---|
| L1-exclusive-range | 2 | no | Look at your WHERE clause—you're using `>` and `<` for the dates, but the problem asks you to include both the start and end dates. What comparison operators should you use instead to include those boundary dates? |
| L1-exclusive-range | 3 | no | Look at your WHERE clause—you're using `>` and `<` for the dates, but the problem asks you to include both the start and end dates. Which comparison operators should you use instead to make the boundaries inclusive? |
| L1-tuples | 1 | no | Your query looks great, but `cursor.fetchall()` returns tuples, not dictionaries. Look at the hint about `cursor.description` and `zip()` — you need to convert each row tuple into a dictionary with the column names as ke |
| L1-tuples | 2 | no | Your query looks good! The issue is that `fetchall()` returns tuples, but you need to return dictionaries. Look at how you can use `cursor.description` (which gives column names) and `zip()` to convert each tuple row int |
| L1-tuples | 3 | no | Your query looks great! The issue is that `cursor.fetchall()` returns tuples, but the problem asks for a list of dictionaries. Use `cursor.description` to get the column names, then use `zip()` to pair each column name w |
| L1-string-concat | 1 | no | Look at how you're building the SQL string. You're using `+` to put `station_id`, `start_date`, and `end_date` directly into the SQL text. The problem says to use `?` placeholders instead, then pass the values as a tuple |
| L1-string-concat | 2 | no | Look at how you're building the SQL string. You're using `+` to insert `station_id`, `start_date`, and `end_date` directly into the SQL text. Instead, use `?` placeholders in the SQL string, then pass the values as a tup |
| L1-string-concat | 3 | no | Look at your SQL string where you're building the WHERE clause. You're using string concatenation with `+` to put the values directly into the SQL text, but the instructions ask you to use `?` placeholders instead. Repla |
| L1-no-order | 1 | no | Look at your ORDER BY clause—you're sorting by rain_mm, but the check says you need to sort by date. Which column should come after ORDER BY to get the oldest dates first? |
| L1-no-order | 2 | no | Look at your ORDER BY clause—you're sorting by `rain_mm`, but the test wants the rows sorted by `date` (oldest first). Which column should you order by instead? |
| L1-no-order | 3 | no | Look at your ORDER BY clause—you're sorting by `rain_mm`, but the problem asks you to sort by date with the oldest first. Which column should you use instead? |
| L2-strict-threshold | 1 | no | Look at your comparison operators in the two if statements. The problem says "35.0 or more" should count, but you're using `>` instead of `>=`. Should 35.0 exactly be included or excluded? |
| L2-strict-threshold | 2 | no | Look at your comparison operators in the two if statements. The problem says "35.0 or more" should count as a heat wave, but you're using `>` instead of `>=`. The same issue applies to your rain check—should 20.0 mm exac |
| L2-strict-threshold | 3 | no | Look at your comparison operators on lines with `HEAT_WAVE_C` and `HEAVY_RAIN_MM`. The problem says "35.0 or more" should count—should you be using `>` or `>=`? |
| L2-elif | 1 | no | Look at your if/elif/else structure. Right now, if the heat wave condition is true, the elif never runs. You need two separate if statements (not elif) so both conditions can be checked and both labels can be added to th |
| L2-elif | 3 | no | Look at your if/elif/else structure. You're using `elif` for the rain check, which means it only runs if the heat wave condition is false. Since a day can be both a heat wave AND have heavy rain, should that second condi |
| L3-builtins | 1 | no | Look at lines 37-41 where you're using `len()`, `sum()`, and `max()`. Instead, create counter variables before your loop (like `heat_wave_days = 0`), then increment them inside the loop as you check each label. Do the sa |
| L3-builtins | 2 | no | Look at lines 37-41 where you're building the return dictionary. You're using `len()`, `sum()`, and `max()` with list comprehensions, but the rules say to keep running totals in a loop instead. Set up counter variables b |
| L3-no-round-sort | 1 | no | Look at how you're adding dates to `flagged_dates`. You're using `insert(0, ...)` which puts each new date at the front, but the problem asks for oldest first. Instead, append dates to the list during the loop, then sort |
| L3-no-round-sort | 2 | no | Look at how you're adding dates to `flagged_dates`. You're using `insert(0, ...)` which puts each new date at the front, but the readings aren't in order. Instead, append dates to the list, then sort it after the loop en |
| L3-no-round-sort | 3 | no | Look at how you're adding dates to `flagged_dates`. Right now you're using `insert(0, ...)` which puts each new date at the front, but that scrambles the order. Instead, append dates to the list as you find them, then so |
| L4-reimplements-sql | 1 | no | Look at your `build_report` function—it's not using the three helper functions you already wrote. Instead of writing new SQL and logic, call `get_readings` to fetch the data, then loop through each row to call `classify_ |
| L4-reimplements-sql | 2 | no | Look at your `build_report` function. Right now it's querying the database directly and counting things itself, but the instructions say to call your three helper functions instead: first `get_readings`, then loop throug |
| L4-reimplements-sql | 3 | no | Look at your `build_report` function. You're writing your own SQL query instead of calling `get_readings`, and you're returning a hardcoded dictionary instead of using `classify_day` and `summarize`. Follow the hint: sta |
| L4-rows-not-pairs | 1 | no | Look at your `build_report` function. You're passing `rows` directly to `summarize`, but `summarize` expects a list of pairs—each pair should be `(row, labels)`. You need to loop through the rows, call `classify_day` on  |
| L4-rows-not-pairs | 2 | no | Look at your `build_report` function. You're passing `rows` directly to `summarize`, but `summarize` expects a list of pairs—each pair should be `(row, labels)`. You need to loop through the rows and call `classify_day`  |
| L4-rows-not-pairs | 3 | no | Look at your `build_report` function. You're calling `summarize(rows)` directly, but `summarize` expects a list of pairs—each pair should be `(row, labels)`. You need to loop through the rows, call `classify_day` on each |

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
