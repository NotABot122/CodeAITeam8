# Level 2: Label Each Entry

Add this function:

```python
def classify_animal(entry):
```

`entry` is one dictionary from `get_animals`. Return a **list of labels**:

- **heavy**: `weight_kg` is 100 or more
- **roamer**: `daily_km` is 15 or more
- **typical**: neither of the above

- An entry that is both returns `["heavy", "roamer"]`, in that order.
- `"typical"` never appears with another label. Don't change `entry`.

Watch the edges: exactly 100 **counts** as heavy.
