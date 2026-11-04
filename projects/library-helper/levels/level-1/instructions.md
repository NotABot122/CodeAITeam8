# Level 1: Find the Books

The school library wants a helper tool for its student volunteers. It should find the books on a range of shelves, flag the long ones and the popular ones, and build a report the librarian can use to plan displays and reading lists.

The data is in a SQLite table called `library_books`:

| Column | Meaning |
|---|---|
| `genre` | The section of the library (`Mystery`, `Science`, `Adventure`) |
| `shelf_number` | Entry number within its genre, starting at 1 |
| `title` | Name, such as The Clockwork Key |
| `pages` | Number of pages (pages) |
| `checkouts` | Times checked out this year (checkouts) |

The names and the numbers are made up for practice.

## Your task

```python
def get_books(conn, genre, start_number, end_number):
```

- Return a **list of dictionaries**, one per row, with the five column names as keys.
- Include only rows where `genre` matches.
- Include `shelf_number` values from `start_number` to `end_number`, **including both ends**.
- Sort by `shelf_number`, smallest first. If nothing matches, return an empty list.

Put the values into the query with `?` placeholders. Don't build the SQL text with string formatting.
