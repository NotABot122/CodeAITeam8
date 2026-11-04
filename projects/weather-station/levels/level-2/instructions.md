# Level 2: Make Decisions

Now label each day. Add this function to your file:

```python
def classify_day(row):
```

`row` is one dictionary from `get_readings`. Return a **list of labels**:

| Condition | Label |
|---|---|
| `temp_high_c` is 35.0 or more | `"heat_wave"` |
| `rain_mm` is 20.0 or more | `"heavy_rain"` |
| neither | `"normal"` |

- A day that is both returns `["heat_wave", "heavy_rain"]`, in that order.
- `"normal"` never appears together with another label.
- Don't change the `row` dictionary.

Watch the edges: exactly 35.0 **is** a heat wave, and 34.9 is not.
