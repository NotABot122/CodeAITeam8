# Review: Dictionaries

A dictionary stores values under **keys**, like a label on each box:

```python
rain = {}                         # an empty dictionary
rain["ST-A"] = 2.5                # put 2.5 under the key "ST-A"
rain["ST-A"] = rain["ST-A"] + 1.0 # update it: 3.5
print(rain.get("ST-B", 0.0))      # a missing key gives the default: 0.0
for station in rain:              # loop over the keys
    print(station, rain[station])
```

- To count or total things by category, use the category as the key: `counts[label] = counts.get(label, 0) + 1`.
- `.get(key, default)` avoids an error the first time you see a key.

Answer the questions below. Wrong answers show an explanation, and you can try again.
