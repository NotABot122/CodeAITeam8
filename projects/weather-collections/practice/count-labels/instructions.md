# Practice: Count the Labels

Extra practice with dictionaries. Add this function:

```python
def count_labels(label_lists):
```

`label_lists` is a list of label lists, like the ones `classify_day` returned:
`[["heat_wave"], ["normal"], ["heat_wave", "heavy_rain"]]`.

Return a dictionary counting each label: `{"heat_wave": 2, "normal": 1, "heavy_rain": 1}`.
Only labels that appear are keys. No lists gives `{}`.
