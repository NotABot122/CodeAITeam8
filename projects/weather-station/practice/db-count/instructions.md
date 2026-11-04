# Practice: Count a Station's Readings

Extra practice with SQL queries before you move on. Add this function to your file:

```python
def count_readings(conn, station_id):
```

Return the number of rows in `daily_readings` for `station_id`, as a whole number. A station with no rows returns `0`.

Use `SELECT COUNT(*) ... WHERE station_id = ?` and pass the station as a parameter, the same way you did in Level 1.
