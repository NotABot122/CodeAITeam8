# Review: Database Retrieval

A query asks the database for exactly the rows you need:

```python
cursor = conn.execute(
    "SELECT date, rain_mm FROM daily_readings WHERE station_id = ? AND rain_mm >= ? ORDER BY date",
    ("ST-A", 20.0),
)
rows = cursor.fetchall()     # a list of tuples, like [("2026-01-14", 20.0), ...]
```

- `WHERE` keeps only the rows that match. `ORDER BY` sorts them.
- Each `?` is a placeholder. The values come in a tuple, in the same order. The database treats them as data, so a name like `O'Brien` can't break the query.

Answer the questions below. Take your time: wrong answers show an explanation, and you can try again.
