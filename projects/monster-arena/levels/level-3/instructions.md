# Level 3: Count Them All Up

Add this function:

```python
def summarize_monsters(entries):
```

`entries` is a list of pairs `(entry, labels)`: a row from `get_monsters` and the list `classify_monster` gave it.

```python
for entry, labels in entries:
    ...
```

Return a dictionary with exactly these keys:

| Key | Value |
|---|---|
| `strong_count` | how many are labeled `"strong"` |
| `fast_count` | how many are labeled `"fast"` |
| `balanced_count` | how many are labeled `"balanced"` |
| `total_speed` | every `speed` added up, rounded to 1 decimal place |
| `max_power` | the highest `power`, or `None` if the list is empty |
| `flagged_monster_numbers` | the `monster_number` of every entry that isn't balanced, smallest first |

## Rules for this level

- Use a `for` or `while` loop.
- Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()` inside `summarize_monsters`. `my_list.sort()` is allowed.
- The entries might not be in order. An empty list gives zeros, `None`, and an empty list.
