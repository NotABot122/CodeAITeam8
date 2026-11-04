"""Write a themed project folder from a validated ThemeSpec.

The folder has the same layout as projects/weather-station, so the existing
loader, grader, router, and content check run it without changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..manifest import ConceptDef, LevelDef, Manifest, PracticeDef, StageCriterion, print_manifest
from .spec import ThemeSpec

SEED = 2026
STRUCTURE_ARGS = lambda spec: [  # noqa: E731  (ranges the Level 4 checks use)
    {"group": spec.groups[0], "start": 1, "end": 10},
    {"group": spec.groups[1], "start": 3, "end": 9},
    {"group": spec.groups[2], "start": 1, "end": len(spec.names[spec.groups[2]])},
]

CHECK_STUBS = {
    "level-1": ("level1", "*", "get"),
    "level-2": ("level2", "*", "classify"),
    "level-3": ("level3", "*", "summarize"),
    "level-4": ("level4", "*", None),
    "practice-count": ("practice", "check_count_each_group", "count"),
    "practice-band": ("practice", "check_bands", "band"),
    "practice-loop": ("practice", "check_count_label", "count_label"),
}
ARITY = {"get": 4, "classify": 1, "summarize": 1, "report": 4, "count": 2, "band": 1, "count_label": 1}


def manifest_for(spec: ThemeSpec) -> Manifest:
    f = spec.functions
    concepts = [ConceptDef("database_retrieval", "Database Retrieval"), ConceptDef("conditionals", "Conditionals"),
                ConceptDef("loops", "Loops"), ConceptDef("functions", "Functions")]
    levels = [
        LevelDef("level-1", 1, f"Find the {spec.entity_plural.replace('_', ' ')}", "levels/level-1",
                 ["database_retrieval"], 1, None),
        LevelDef("level-2", 2, "Label Each Entry", "levels/level-2", ["conditionals"], 1, None),
        LevelDef("level-3", 3, "Count Them All Up", "levels/level-3", ["loops"], 1, f["summarize"]),
        LevelDef("level-4", 4, "Build the Report", "levels/level-4", ["functions"], None, None),
    ]
    practice = [
        PracticeDef("practice-count", f"Practice: Count Each {spec.group_column.replace('_', ' ').title()}",
                    "practice/count", "database_retrieval", 1, None),
        PracticeDef("practice-band", f"Practice: {spec.metric_a.column.replace('_', ' ').title()} Bands",
                    "practice/band", "conditionals", 1, None),
        PracticeDef("practice-loop", f"Practice: Count the {spec.metric_b.label.replace('_', ' ').title()} Ones",
                    "practice/loop", "loops", 1, f["count_label"]),
    ]
    return Manifest(
        title=spec.title,
        concepts=concepts,
        stage_criteria={1: StageCriterion(3, None), 2: StageCriterion(2, None), 3: StageCriterion(1, 0)},
        levels=levels,
        fallback_path=["level-1", "level-2", "level-3", "level-4"],
        streak_length=1,
        practice_problems=practice,
        dataset={"generator": "dataset/generate.py", "database": "dataset/data.db"},
        parameters={"theme": spec.to_dict(), "expected_report_args": STRUCTURE_ARGS(spec), "empty_max": None},
    )


# Source templates ----------------------------------------------------------------------------

def reference_source(spec: ThemeSpec) -> str:
    f, k = spec.functions, spec.summary_keys
    g, n = spec.group_column, spec.number_column
    a, b = spec.metric_a, spec.metric_b
    cols = ", ".join(spec.columns)
    return f'''"""Reference solution for {spec.title}. Used only to check the tests. Never shown to students."""


def {f["get"]}(conn, {g}, start_number, end_number):
    cursor = conn.execute(
        "SELECT {cols} FROM {spec.table} "
        "WHERE {g} = ? AND {n} >= ? AND {n} <= ? ORDER BY {n}",
        ({g}, start_number, end_number),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def {f["classify"]}(entry):
    labels = []
    if entry["{a.column}"] >= {a.threshold!r}:
        labels.append("{a.label}")
    if entry["{b.column}"] >= {b.threshold!r}:
        labels.append("{b.label}")
    if not labels:
        labels.append("{spec.normal_label}")
    return labels


def {f["summarize"]}(entries):
    count_a = 0
    count_b = 0
    count_normal = 0
    total = 0.0
    highest = None
    flagged = []
    for entry, labels in entries:
        if "{a.label}" in labels:
            count_a += 1
        if "{b.label}" in labels:
            count_b += 1
        if "{spec.normal_label}" in labels:
            count_normal += 1
        else:
            flagged.append(entry["{n}"])
        total += entry["{b.column}"]
        if highest is None or entry["{a.column}"] > highest:
            highest = entry["{a.column}"]
    flagged.sort()
    return {{
        "{k["count_a"]}": count_a,
        "{k["count_b"]}": count_b,
        "{k["count_normal"]}": count_normal,
        "{k["total_b"]}": round(total, 1),
        "{k["max_a"]}": highest,
        "{k["flagged"]}": flagged,
    }}


def {f["report"]}(conn, {g}, start_number, end_number):
    rows = {f["get"]}(conn, {g}, start_number, end_number)
    entries = []
    for row in rows:
        entries.append((row, {f["classify"]}(row)))
    return {f["summarize"]}(entries)


def {f["count"]}(conn, {g}):
    return conn.execute("SELECT COUNT(*) FROM {spec.table} WHERE {g} = ?", ({g},)).fetchone()[0]


def {f["band"]}(value):
    if value >= {a.threshold!r}:
        return "high"
    elif value >= {spec.band_cutoff!r}:
        return "medium"
    else:
        return "low"


def {f["count_label"]}(rows):
    count = 0
    for row in rows:
        if row["{b.column}"] >= {b.threshold!r}:
            count += 1
    return count
'''


def checker_source(spec: ThemeSpec) -> str:
    k = spec.summary_keys
    g, n = spec.group_column, spec.number_column
    a, b = spec.metric_a, spec.metric_b
    return f'''"""Independent computation of the Level 4 report, using SQL instead of Python loops."""

WHERE = "WHERE {g} = ? AND {n} BETWEEN ? AND ?"


def compute(conn, group, start, end):
    params = (group, start, end)
    count_a, count_b, count_normal, total, highest = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN {a.column} >= {a.threshold!r} THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN {b.column} >= {b.threshold!r} THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN {a.column} < {a.threshold!r} AND {b.column} < {b.threshold!r} THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM({b.column}), 0.0), MAX({a.column}) FROM {spec.table} " + WHERE, params).fetchone()
    flagged = [row[0] for row in conn.execute(
        "SELECT {n} FROM {spec.table} " + WHERE +
        " AND ({a.column} >= {a.threshold!r} OR {b.column} >= {b.threshold!r}) ORDER BY {n}", params)]
    return {{
        "{k["count_a"]}": int(count_a),
        "{k["count_b"]}": int(count_b),
        "{k["count_normal"]}": int(count_normal),
        "{k["total_b"]}": round(float(total), 1),
        "{k["max_a"]}": highest,
        "{k["flagged"]}": flagged,
    }}
'''


GENERATOR_STUB = '''"""Builds data.db for this themed project from theme.json and seed.txt."""
import json
from pathlib import Path

from engine.themes.dataset import build

HERE = Path(__file__).resolve().parent


def read_default_seed():
    return int((HERE / "seed.txt").read_text().strip())


def generate(out_path=HERE / "data.db", seed=None):
    theme = json.loads((HERE.parent / "theme.json").read_text())
    return build(out_path, theme, read_default_seed() if seed is None else seed)
'''


def checks_stub(problem_id: str, spec: ThemeSpec) -> str:
    module, names, role = CHECK_STUBS[problem_id]
    roles = [role] if role else ["get", "classify", "summarize", "report"]
    required = {spec.functions[r]: ARITY[r] for r in roles}
    return (f'"""Generated checks: shared themed checks, configured by the theme in manifest parameters."""\n'
            f"from engine.themes.checks.{module} import {names}  # noqa: F401,F403\n\n"
            f"REQUIRED = {required!r}\n")


# Student-facing text --------------------------------------------------------------------------

def _pairs_example(spec: ThemeSpec) -> str:
    return f"(entry, labels)"


def instructions(spec: ThemeSpec) -> dict:
    f, k = spec.functions, spec.summary_keys
    g, n, nm = spec.group_column, spec.number_column, spec.name_column
    a, b = spec.metric_a, spec.metric_b
    group_list = ", ".join(f"`{x}`" for x in spec.groups)
    example_name = spec.names[spec.groups[0]][0]
    table = "\n".join([
        "| Column | Meaning |", "|---|---|",
        f"| `{g}` | {spec.group_description} ({group_list}) |",
        f"| `{n}` | Entry number within its {g.replace('_', ' ')}, starting at 1 |",
        f"| `{nm}` | Name, such as {example_name} |",
        f"| `{a.column}` | {a.description} ({a.unit}) |",
        f"| `{b.column}` | {b.description} ({b.unit}) |",
    ])
    rules = (f"- **{a.label}**: `{a.column}` is {a.threshold:g} or more\n"
             f"- **{b.label}**: `{b.column}` is {b.threshold:g} or more\n"
             f"- **{spec.normal_label}**: neither of the above")
    return {
        "level-1": f"""# Level 1: Find the {spec.entity_plural.replace('_', ' ').title()}

{spec.story}

The data is in a SQLite table called `{spec.table}`:

{table}

The names are real, but the numbers are made up for practice.

## Your task

```python
def {f["get"]}(conn, {g}, start_number, end_number):
```

- Return a **list of dictionaries**, one per row, with the five column names as keys.
- Include only rows where `{g}` matches.
- Include `{n}` values from `start_number` to `end_number`, **including both ends**.
- Sort by `{n}`, smallest first. If nothing matches, return an empty list.

Put the values into the query with `?` placeholders. Don't build the SQL text with string formatting.
""",
        "level-2": f"""# Level 2: Label Each Entry

Add this function:

```python
def {f["classify"]}(entry):
```

`entry` is one dictionary from `{f["get"]}`. Return a **list of labels**:

{rules}

- An entry that is both returns `["{a.label}", "{b.label}"]`, in that order.
- `"{spec.normal_label}"` never appears with another label. Don't change `entry`.

Watch the edges: exactly {a.threshold:g} **counts** as {a.label}.
""",
        "level-3": f"""# Level 3: Count Them All Up

Add this function:

```python
def {f["summarize"]}(entries):
```

`entries` is a list of pairs `{_pairs_example(spec)}`: a row from `{f["get"]}` and the list `{f["classify"]}` gave it.

```python
for entry, labels in entries:
    ...
```

Return a dictionary with exactly these keys:

| Key | Value |
|---|---|
| `{k["count_a"]}` | how many are labeled `"{a.label}"` |
| `{k["count_b"]}` | how many are labeled `"{b.label}"` |
| `{k["count_normal"]}` | how many are labeled `"{spec.normal_label}"` |
| `{k["total_b"]}` | every `{b.column}` added up, rounded to 1 decimal place |
| `{k["max_a"]}` | the highest `{a.column}`, or `None` if the list is empty |
| `{k["flagged"]}` | the `{n}` of every entry that isn't {spec.normal_label}, smallest first |

## Rules for this level

- Use a `for` or `while` loop.
- Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()` inside `{f["summarize"]}`. `my_list.sort()` is allowed.
- The entries might not be in order. An empty list gives zeros, `None`, and an empty list.
""",
        "level-4": f"""# Level 4: Build the Report

Add this function:

```python
def {f["report"]}(conn, {g}, start_number, end_number):
```

1. Call **your** `{f["get"]}` once.
2. Call **your** `{f["classify"]}` on each row and pair them up: `(row, labels)`.
3. Call **your** `{f["summarize"]}` once with the list of pairs, and return its result.

Don't change the database. Calling it twice with the same arguments should give the same report.
""",
        "practice-count": f"""# Practice: Count Each {g.replace('_', ' ').title()}

```python
def {f["count"]}(conn, {g}):
```

Return how many rows in `{spec.table}` have that `{g}`, as a whole number (0 if none).
Use `SELECT COUNT(*) ... WHERE {g} = ?` with a parameter, like in Level 1.
""",
        "practice-band": f"""# Practice: {a.column.replace('_', ' ').title()} Bands

```python
def {f["band"]}(value):
```

| `{a.column}` | Return |
|---|---|
| {a.threshold:g} or more | `"high"` |
| {spec.band_cutoff:g} up to {round(a.threshold - 0.1, 1):g} | `"medium"` |
| below {spec.band_cutoff:g} | `"low"` |

Check the order of your conditions: a high value is also above the medium edge.
""",
        "practice-loop": f"""# Practice: Count the {b.label.replace('_', ' ').title()} Ones

```python
def {f["count_label"]}(rows):
```

`rows` is a list of row dictionaries. Return how many have `{b.column}` of {b.threshold:g} or more.
Use a `for` loop and a counter. Don't use `sum()`, `max()`, `min()`, `len()`, or `sorted()`.
""",
    }


def hints(spec: ThemeSpec) -> dict:
    f = spec.functions
    g, n = spec.group_column, spec.number_column
    a, b = spec.metric_a, spec.metric_b
    return {
        "level-1": [
            f"Start with a query that selects the five columns FROM {spec.table}, then add a WHERE clause for "
            f"{g} and the number range.",
            f"Use ? in the SQL for each value and pass them as a tuple: conn.execute(sql, ({g}, start_number, "
            f"end_number)). Use >= and <= so both ends are included.",
            f"ORDER BY {n} sorts the rows. To make dictionaries, cursor.description gives the column names and "
            f"zip(names, values) pairs them up.",
        ],
        "level-2": [
            "Start with an empty list, labels = [], and add a label for each condition that is true.",
            f"\"{a.threshold:g} or more\" means >= {a.threshold:g}. Use two separate if statements so an entry "
            f"can get both labels, {a.label} first.",
            f"After both checks, if the list is still empty, add \"{spec.normal_label}\". Return the list at the end.",
        ],
        "level-3": [
            "Before the loop, set up a variable for each answer: counters at 0, the total at 0.0, the highest at "
            "None, and an empty list for flagged numbers.",
            f"Write for entry, labels in entries: and use if \"{a.label}\" in labels: to add 1 to a counter. Add "
            f"entry[\"{b.column}\"] to the total on every pass.",
            f"Replace the highest {a.column} when it is None or the new value is bigger. After the loop, sort the "
            f"flagged list with .sort() and round the total with round(total, 1).",
        ],
        "level-4": [
            f"{f['report']} doesn't need new logic. Each step is a function you already wrote.",
            f"Start with rows = {f['get']}(conn, {g}, start_number, end_number), then loop and append "
            f"(row, {f['classify']}(row)) to a list.",
            f"The last line should return {f['summarize']}(your_list). Call each function by name.",
        ],
        "practice-count": ["COUNT(*) returns one row with one number in it.",
                           f"Pass ({g},) with the comma, then use .fetchone()[0] to get the number."],
        "practice-band": ["Test the highest band first. Python stops at the first if or elif that is true.",
                          f"Use >= for both edges: >= {a.threshold:g}, then >= {spec.band_cutoff:g}, then else."],
        "practice-loop": ["Start with count = 0 before the loop.",
                          f"Inside the loop, add 1 when row[\"{b.column}\"] >= {b.threshold:g}. Return count after."],
    }


def starter_source(spec: ThemeSpec) -> str:
    story = "\n".join("    " + line if line else "" for line in spec.story.splitlines())
    return (f'"""{spec.title}\n\n{story}\n\nBuild it one function at a time. Each level adds one function to this\n'
            f'file, and later levels use the functions you wrote earlier.\n"""\n\n\n'
            f"# Level 1: write {spec.functions['get']}(conn, {spec.group_column}, start_number, end_number) here.\n")


def render_project(spec: ThemeSpec, folder: Path, request_text: str = "") -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True)
    manifest = manifest_for(spec)
    (folder / "manifest.yaml").write_text(print_manifest(manifest))
    (folder / "theme.json").write_text(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False) + "\n")
    (folder / "request.txt").write_text(request_text.strip() + "\n")
    (folder / "starter.py").write_text(starter_source(spec))

    dataset = folder / "dataset"
    dataset.mkdir()
    (dataset / "generate.py").write_text(GENERATOR_STUB)
    (dataset / "seed.txt").write_text(f"{SEED}\n")

    texts, hint_lists = instructions(spec), hints(spec)
    folders = {lvl.id: lvl.folder for lvl in manifest.levels}
    folders.update({p.id: p.folder for p in manifest.practice_problems})
    for problem_id, rel in folders.items():
        target = folder / rel
        target.mkdir(parents=True)
        (target / "instructions.md").write_text(texts[problem_id])
        (target / "hints.yaml").write_text(yaml.safe_dump(hint_lists[problem_id], allow_unicode=True, width=1000))
        (target / "checks.py").write_text(checks_stub(problem_id, spec))

    reference = folder / "reference"
    reference.mkdir()
    (reference / "solution.py").write_text(reference_source(spec))
    (reference / "independent_checker.py").write_text(checker_source(spec))
    return folder
