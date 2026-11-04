# Level 1: Find the Monsters

You're on the team building Monster Arena, a creature-battling game. Before the next update, the game designer needs a tool that finds monsters by zone, spots the strong and fast ones, and builds a balance report so no zone is too easy or too hard.

The data is in a SQLite table called `monsters`:

| Column | Meaning |
|---|---|
| `zone` | The game zone where the monster lives (`Forest`, `Desert`, `Volcano`) |
| `monster_number` | Entry number within its zone, starting at 1 |
| `name` | Name, such as Mossling |
| `power` | Attack power (points) |
| `speed` | Movement speed (points) |

The names are real, but the numbers are made up for practice.

## Your task

```python
def get_monsters(conn, zone, start_number, end_number):
```

- Return a **list of dictionaries**, one per row, with the five column names as keys.
- Include only rows where `zone` matches.
- Include `monster_number` values from `start_number` to `end_number`, **including both ends**.
- Sort by `monster_number`, smallest first. If nothing matches, return an empty list.

Put the values into the query with `?` placeholders. Don't build the SQL text with string formatting.
