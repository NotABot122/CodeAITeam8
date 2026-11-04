# Level 3: Group by Month

Now combine both ideas: a dictionary whose values are lists. Add this function:

```python
def days_by_month(rows):
```

- Return a **dictionary**: each key is a month as text, `"YYYY-MM"` (the first 7 characters of the date), and its value is a **list of the dates** in that month.
- Sort each list, oldest first. No rows gives `{}`.

Example: dates `2026-02-03`, `2026-01-31`, and `2026-02-01` give
`{"2026-01": ["2026-01-31"], "2026-02": ["2026-02-01", "2026-02-03"]}`.

Tip: `"2026-02-03"[:7]` is `"2026-02"`.
