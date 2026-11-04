"""Themed Level 1: retrieve rows with a parameterized query."""
from .common import INJECTION, db_rows, describe, expect, name_of, row_count, spec_of, student


def _call(ctx, *args):
    conn = ctx.connect()
    try:
        return student(ctx, "get")(conn, *args)
    finally:
        conn.close()


def check_only_requested_group(ctx):
    """The function should return only rows for the requested group."""
    s = spec_of(ctx)
    group = s.groups[0]
    rows = _call(ctx, group, 1, 10)
    expect(isinstance(rows, list), f"{name_of(ctx, 'get')} should return a list, but it returned {describe(rows)}.")
    others = [r for r in rows if not isinstance(r, dict) or r.get(s.group_column) != group]
    expect(not others, f"asking for {s.group_column} {group!r} returned rows from another {s.group_column}.")


def check_exact_number_range(ctx):
    """Return each number in the range exactly once, including both ends."""
    s = spec_of(ctx)
    for group, start, end in ((s.groups[0], 1, 10), (s.groups[1], 3, 9)):
        rows = _call(ctx, group, start, end)
        expect(isinstance(rows, list), f"{name_of(ctx, 'get')} should return a list, but it returned {describe(rows)}.")
        numbers = [r.get(s.number_column) if isinstance(r, dict) else None for r in rows]
        wanted = list(range(start, end + 1))
        expect(start in numbers and end in numbers,
               f"{group} from {s.number_column} {start} to {end} should include both {start} and {end}.")
        expect(sorted(x for x in numbers if x is not None) == wanted and len(numbers) == len(wanted),
               f"{group} from {start} to {end} should return {len(wanted)} rows, one per number, "
               f"but returned {len(numbers)}.")


def check_rows_are_dictionaries(ctx):
    """Each row should be a dictionary with the five column names and the database values."""
    s = spec_of(ctx)
    group = s.groups[2]
    rows = _call(ctx, group, 2, 8)
    truth = {r[s.number_column]: r for r in db_rows(ctx, group, 2, 8)}
    for row in rows:
        expect(isinstance(row, dict), f"each row should be a dictionary, but one was {describe(row)}.")
        expect(set(row) == set(s.columns),
               f"each row should have exactly the keys {', '.join(s.columns)}, "
               f"but one had {', '.join(sorted(map(str, row)))}.")
        expect(row == truth.get(row[s.number_column]),
               f"the row for number {row[s.number_column]} should have the values stored in the database.")


def check_sorted_by_number(ctx):
    """Rows should be sorted by number, smallest first."""
    s = spec_of(ctx)
    rows = _call(ctx, s.groups[1], 1, len(s.names[s.groups[1]]))
    numbers = [r.get(s.number_column) for r in rows if isinstance(r, dict)]
    expect(all(a < b for a, b in zip(numbers, numbers[1:])),
           f"rows should be sorted by {s.number_column}, smallest first. Try ORDER BY {s.number_column}.")


def check_empty_ranges(ctx):
    """A range with no matching rows should return an empty list without an error."""
    s = spec_of(ctx)
    rows = _call(ctx, s.groups[0], 500, 600)
    expect(rows == [], f"numbers 500 to 600 don't exist, so the result should be [], but was {describe(rows)}.")
    rows = _call(ctx, s.groups[0], 9, 2)
    expect(rows == [], f"a start number bigger than the end number should return [], but returned {describe(rows)}.")


def check_uses_placeholders(ctx):
    """A group name containing a quote should return no rows."""
    before = row_count(ctx)
    try:
        rows = _call(ctx, INJECTION, 1, 100)
    except Exception as exc:
        raise AssertionError(f"a group name containing a quote (') caused {type(exc).__name__}. "
                             "Use ? placeholders instead of putting values into the SQL text.") from None
    expect(rows == [], f"the group name {INJECTION} should match no rows, but some came back. "
                       "Use ? placeholders instead of putting values into the SQL text.")
    expect(row_count(ctx) == before, f"{name_of(ctx, 'get')} should not change the database.")
