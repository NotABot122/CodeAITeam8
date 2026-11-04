# Level 4: Station Summary

Put your three functions to work. Add this function:

```python
def station_summary(rows):
```

Return a dictionary with one key per station in `rows`. Each value is another dictionary:

| Key | Value | Use |
|---|---|---|
| `hot_days` | number of that station's days at 35.0 or more | your `hot_dates` |
| `total_rain` | that station's total rain | your `rain_by_station` |
| `months` | number of months with data for that station | your `days_by_month` |

Example: `{"ST-A": {"hot_days": 13, "total_rain": 82.2, "months": 1}}`

Call **your** functions: `rain_by_station` once on all rows, and `hot_dates` and `days_by_month` once per station, on that station's rows. `len()` is fine here.
