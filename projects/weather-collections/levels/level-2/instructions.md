# Level 2: Total by Station

Now add up the rain for each station. Add this function:

```python
def rain_by_station(rows):
```

- Return a **dictionary**: each key is a `station_id`, and its value is that station's total `rain_mm`, rounded to 1 decimal place.
- Include only stations that appear in `rows`. No rows gives an empty dictionary `{}`.

Example: two ST-A rows with 2.5 and 1.0 mm, and one ST-B row with 4.0 mm, give `{"ST-A": 3.5, "ST-B": 4.0}`.
