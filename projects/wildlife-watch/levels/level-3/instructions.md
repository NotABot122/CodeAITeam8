# Level 3: Count Them All Up

Add this function:

```python
def summarize_animals(entries):
```

`entries` is a list of pairs `(entry, labels)`: a row from `get_animals` and the list `classify_animal` gave it.

```python
for entry, labels in entries:
    ...
```

Return a dictionary with exactly these keys:

| Key | Value |
|---|---|
| `heavy_count` | how many are labeled `"heavy"` |
| `roamer_count` | how many are labeled `"roamer"` |
| `typical_count` | how many are labeled `"typical"` |
| `total_daily_km` | every `daily_km` added up, rounded to 1 decimal place |
| `max_weight_kg` | the highest `weight_kg`, or `None` if the list is empty |
| `flagged_tag_numbers` | the `tag_number` of every entry that isn't typical, smallest first |

## Rules for this level

- Use a `for` or `while` loop.
- Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()` inside `summarize_animals`. `my_list.sort()` is allowed.
- The entries might not be in order. An empty list gives zeros, `None`, and an empty list.
