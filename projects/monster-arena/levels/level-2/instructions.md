# Level 2: Label Each Entry

Add this function:

```python
def classify_monster(entry):
```

`entry` is one dictionary from `get_monsters`. Return a **list of labels**:

- **strong**: `power` is 70 or more
- **fast**: `speed` is 60 or more
- **balanced**: neither of the above

- An entry that is both returns `["strong", "fast"]`, in that order.
- `"balanced"` never appears with another label. Don't change `entry`.

Watch the edges: exactly 70 **counts** as strong.
