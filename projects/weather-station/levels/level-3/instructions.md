# Level 3: Process Every Record

Now count up a whole date range. Add this function to your file:

```python
def summarize(readings):
```

`readings` is a list of **pairs** `(row, labels)`: a row from `get_readings` and the list `classify_day` returned for it. For example:

```python
readings = [
    (row_for_jan_1, ["heat_wave"]),
    (row_for_jan_2, ["normal"]),
]
for row, labels in readings:
    ...
```

Return a dictionary with exactly these keys:

| Key | Value |
|---|---|
| `heat_wave_days` | number of days labeled `"heat_wave"` |
| `heavy_rain_days` | number of days labeled `"heavy_rain"` |
| `normal_days` | number of days labeled `"normal"` |
| `total_rain_mm` | all rainfall added up, rounded to 1 decimal place |
| `max_temp_c` | the highest `temp_high_c`, or `None` if there are no readings |
| `flagged_dates` | dates that aren't normal, oldest first |

## Rules for this level

- Use a `for` or `while` loop to go through the readings.
- Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()` inside `summarize`. Keep running totals yourself. To put dates in order, `my_list.sort()` is allowed.
- The readings might not be in date order.
- An empty list should give zeros, `None` for `max_temp_c`, and an empty `flagged_dates` list.
