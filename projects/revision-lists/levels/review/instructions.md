# Review: Lists

A list holds many values in order, under one name:

```python
temps = []                # an empty list
temps.append(36.2)        # add to the end: [36.2]
temps.append(30.1)        # [36.2, 30.1]
print(temps[0])           # first item: 36.2
print(temps[-1])          # last item: 30.1
print(len(temps))         # how many: 2
temps.sort()              # sort in place: [30.1, 36.2]
```

- Build a list in a loop: start empty before the loop, `.append()` inside it.
- Positions start at 0. `-1` means the last item.

Answer the questions below. Wrong answers show an explanation, and you can try again.
