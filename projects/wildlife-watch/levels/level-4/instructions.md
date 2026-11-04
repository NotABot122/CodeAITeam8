# Level 4: Build the Report

Add this function:

```python
def build_animal_report(conn, park, start_number, end_number):
```

1. Call **your** `get_animals` once.
2. Call **your** `classify_animal` on each row and pair them up: `(row, labels)`.
3. Call **your** `summarize_animals` once with the list of pairs, and return its result.

Don't change the database. Calling it twice with the same arguments should give the same report.
