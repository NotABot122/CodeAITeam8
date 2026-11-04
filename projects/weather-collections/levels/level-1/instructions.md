# Level 1: Build a List

The meteorologist wants every hot day in one list. Add this function:

```python
def hot_dates(rows, threshold):
```

- `rows` is a list of row dictionaries (keys `station_id`, `date`, `temp_high_c`, `temp_low_c`, `rain_mm`).
- Return a **list of dates** (strings) where `temp_high_c` is `threshold` or more.
- Sort the dates, oldest first. The rows might not be in order.
- No matching days gives an empty list `[]`.

Start with an empty list and `.append()` to it inside a loop.
