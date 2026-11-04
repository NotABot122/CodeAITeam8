# Review: Loops

A `for` loop runs the same steps once for every item in a list:

```python
total = 0                 # 1. set up the answer BEFORE the loop
for row in rows:          # 2. visit every row
    total += row["rain_mm"]   #    and update the answer
print(total)              # 3. use the answer AFTER the loop
```

- A variable that builds up an answer across the loop is called an **accumulator**: a counter, a total, a list, or "the biggest so far".
- Set it up before the loop. If you set it inside, it resets on every pass.
- To track the biggest value, start with `None` and replace it when it's `None` or the new value is bigger.

Answer the questions below. Wrong answers show an explanation, and you can try again.
