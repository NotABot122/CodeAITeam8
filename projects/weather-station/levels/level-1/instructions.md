# Level 1: Retrieve Data from the Database

The weather station saves one reading per day in a SQLite table called `daily_readings`:

| Column | Meaning |
|---|---|
| `station_id` | Station code, such as `ST-A` |
| `date` | Date as text, `YYYY-MM-DD` |
| `temp_high_c` | Highest temperature that day, in °C |
| `temp_low_c` | Lowest temperature that day, in °C |
| `rain_mm` | Rainfall, in millimeters |

## Your task

Write a function:

```python
def get_readings(conn, station_id, start_date, end_date):
```

- `conn` is an open `sqlite3` connection.
- Return a **list of dictionaries**, one per day, with the five column names as keys.
- Include only rows for `station_id`.
- Include days from `start_date` to `end_date`, **including both ends**.
- Sort the rows by date, oldest first.
- If no days match, return an empty list.

Put the values into the query with `?` placeholders. Don't build the SQL text with string formatting.
