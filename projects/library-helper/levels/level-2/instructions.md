# Level 2: Label Each Entry

Add this function:

```python
def classify_book(entry):
```

`entry` is one dictionary from `get_books`. Return a **list of labels**:

- **long**: `pages` is 400 or more
- **popular**: `checkouts` is 30 or more
- **regular**: neither of the above

- An entry that is both returns `["long", "popular"]`, in that order.
- `"regular"` never appears with another label. Don't change `entry`.

Watch the edges: exactly 400 **counts** as long.
