# Level 1: Find the Animals

Park rangers put tracking tags on animals in three parks. They need help finding patterns in the tag data: which animals are heavy, which roam far each day, and what each park looks like in a report they can share with the wildlife team.

The data is in a SQLite table called `tagged_animals`:

| Column | Meaning |
|---|---|
| `park` | The park where the animal was tagged (`Pine Ridge`, `Cedar Lake`, `Red Canyon`) |
| `tag_number` | Entry number within its park, starting at 1 |
| `species` | Name, such as Black Bear |
| `weight_kg` | Body weight (kg) |
| `daily_km` | Distance moved in a day (km) |

The names are real, but the numbers are made up for practice.

## Your task

```python
def get_animals(conn, park, start_number, end_number):
```

- Return a **list of dictionaries**, one per row, with the five column names as keys.
- Include only rows where `park` matches.
- Include `tag_number` values from `start_number` to `end_number`, **including both ends**.
- Sort by `tag_number`, smallest first. If nothing matches, return an empty list.

Put the values into the query with `?` placeholders. Don't build the SQL text with string formatting.
