# Level 3: Count Them All Up

Add this function:

```python
def summarize_books(entries):
```

`entries` is a list of pairs `(entry, labels)`: a row from `get_books` and the list `classify_book` gave it.

```python
for entry, labels in entries:
    ...
```

Return a dictionary with exactly these keys:

| Key | Value |
|---|---|
| `long_count` | how many are labeled `"long"` |
| `popular_count` | how many are labeled `"popular"` |
| `regular_count` | how many are labeled `"regular"` |
| `total_checkouts` | every `checkouts` added up, rounded to 1 decimal place |
| `max_pages` | the highest `pages`, or `None` if the list is empty |
| `flagged_shelf_numbers` | the `shelf_number` of every entry that isn't regular, smallest first |

## Rules for this level

- Use a `for` or `while` loop.
- Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()` inside `summarize_books`. `my_list.sort()` is allowed.
- The entries might not be in order. An empty list gives zeros, `None`, and an empty list.
