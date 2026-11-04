# Level 4: Build the Report

Add this function:

```python
def build_monster_report(conn, zone, start_number, end_number):
```

1. Call **your** `get_monsters` once.
2. Call **your** `classify_monster` on each row and pair them up: `(row, labels)`.
3. Call **your** `summarize_monsters` once with the list of pairs, and return its result.

Don't change the database. Calling it twice with the same arguments should give the same report.
