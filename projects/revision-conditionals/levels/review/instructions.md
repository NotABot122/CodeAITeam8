# Review: Conditionals

`if`, `elif`, and `else` let your code choose:

```python
if temp >= 35.0:        # checked first
    band = "hot"
elif temp >= 20.0:      # only checked if the first was False
    band = "warm"
else:                   # used when nothing above was True
    band = "cool"
```

- Python runs the **first** branch whose condition is True, then skips the rest. So check the strictest condition first.
- `>=` includes the edge value; `>` doesn't. `35.0 >= 35.0` is True, but `35.0 > 35.0` is False.
- Two separate `if` statements (not `elif`) can both run. That's how a day gets two labels.

Answer the questions below. Wrong answers show an explanation, and you can try again.
