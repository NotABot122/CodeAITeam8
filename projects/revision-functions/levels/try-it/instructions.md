# Try It: Station Average

Your file already has a working `get_readings`. Write two small functions that work together:

```python
def average_high(rows):
```
Return the average `temp_high_c` of the rows, rounded to 1 decimal place. No rows gives `None`.

```python
def station_average(conn, station_id, start_date, end_date):
```
Call `get_readings` to get the rows, then call **your** `average_high` on them and return the result.
