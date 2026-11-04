# Level 4: Solve the Full Problem

Put it all together. Add this function to your file:

```python
def build_report(conn, station_id, start_date, end_date):
```

It should:

1. Call **your** `get_readings` once to get the rows for the station and dates.
2. Call **your** `classify_day` on each row, and pair each row with its labels: `(row, labels)`.
3. Call **your** `summarize` once with the list of pairs, and return its result.

Don't change the database. Calling `build_report` twice with the same arguments should give the same report.

The meteorologist will check your report for station `ST-A` in January 2026 against the stored answer.
