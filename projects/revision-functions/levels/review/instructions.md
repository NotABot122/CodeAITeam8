# Review: Functions

A function is a named set of steps. You give it inputs (parameters), and it can **return** an answer:

```python
def double(n):
    return n * 2          # sends the answer back to whoever called it

answer = double(5)        # answer is 10
print(double(double(3)))  # functions can use each other: 12
```

- `return` hands a value back. `print` only shows it on screen. A function with no `return` gives back `None`.
- Big programs are built from small functions that call each other, like your `build_report` calling `get_readings`, `classify_day`, and `summarize`.

Answer the questions below. Wrong answers show an explanation, and you can try again.
