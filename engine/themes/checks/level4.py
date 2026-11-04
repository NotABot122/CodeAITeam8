"""Themed Level 4: combine the three functions into a report."""
import inspect

from .common import db_rows, describe, expect, name_of, spec_of, student

ROLES = ("get", "classify", "summarize")


def _expected(ctx, group, start, end):
    for entry in ctx.expected_reports:
        if entry["args"] == {"group": group, "start": start, "end": end}:
            return entry["report"]
    raise AssertionError(f"no stored expected report for {group} {start} to {end} (content problem).")


def _report(ctx, group, start, end):
    conn = ctx.connect()
    try:
        return student(ctx, "report")(conn, group, start, end)
    finally:
        conn.close()


def _compare(ctx, group, start, end):
    result = _report(ctx, group, start, end)
    expect(isinstance(result, dict), f"{name_of(ctx, 'report')} should return a dictionary, "
                                     f"but it returned {describe(result)}.")
    wanted = _expected(ctx, group, start, end)
    wrong = [key for key in wanted if result.get(key) != wanted[key]]
    extra = [str(key) for key in result if key not in wanted]
    expect(not wrong and not extra,
           f"the report for {group} from {start} to {end} has wrong values for {', '.join(wrong + extra)}.")


def check_first_report(ctx):
    """The first stored report should match."""
    s = spec_of(ctx)
    _compare(ctx, s.groups[0], 1, 10)


def check_second_report(ctx):
    """The second stored report should match."""
    s = spec_of(ctx)
    _compare(ctx, s.groups[1], 3, 9)


def check_empty_report(ctx):
    """A range with no rows gives the empty summary without an error."""
    s = spec_of(ctx)
    k = s.summary_keys
    result = _report(ctx, s.groups[0], 500, 600)
    wanted = {k["count_a"]: 0, k["count_b"]: 0, k["count_normal"]: 0, k["total_b"]: 0, k["max_a"]: None,
              k["flagged"]: []}
    expect(isinstance(result, dict) and all(result.get(key) == v for key, v in wanted.items()) and k["max_a"] in result,
           f"numbers 500 to 600 don't exist, so the report should have zero counts and {k['max_a']} None, "
           f"but was {describe(result, 90)}.")


def check_database_unchanged(ctx):
    """The report function should not change the database."""
    s = spec_of(ctx)
    before = db_rows(ctx)
    _report(ctx, s.groups[2], 1, 12)
    expect(db_rows(ctx) == before, f"{name_of(ctx, 'report')} should not change the database.")


def check_same_result_twice(ctx):
    """Two calls with the same arguments return the same report."""
    s = spec_of(ctx)
    first, second = _report(ctx, s.groups[1], 1, 12), _report(ctx, s.groups[1], 1, 12)
    expect(first == second, f"calling {name_of(ctx, 'report')} twice with the same arguments gave different reports.")


def check_uses_your_functions(ctx):
    """The report calls the get function once, classify once per row, then summarize once."""
    s = spec_of(ctx)
    names = {role: s.functions[role] for role in ROLES}
    module = ctx.module
    originals = {role: getattr(module, name) for role, name in names.items()}
    calls = []

    def wrap(role):
        func = originals[role]

        def wrapper(*args, **kwargs):
            calls.append((role, list(inspect.signature(func).bind(*args, **kwargs).arguments.values())))
            return func(*args, **kwargs)
        return wrapper

    conn = ctx.connect()
    try:
        for role, name in names.items():
            setattr(module, name, wrap(role))
        getattr(module, s.functions["report"])(conn, s.groups[0], 1, 7)
    finally:
        for role, name in names.items():
            setattr(module, name, originals[role])
        conn.close()

    roles = [role for role, _ in calls]
    missing = [names[r] for r in ROLES if r not in roles]
    report = s.functions["report"]
    expect(not missing, f"{report} should call your {', '.join(missing)} function(s).")
    expect(roles.count("get") == 1, f"{report} should call {names['get']} exactly once.")
    args = calls[roles.index("get")][1]
    expect(args[0] is conn and args[1:] == [s.groups[0], 1, 7],
           f"{report} should pass its conn, group, start, and end to {names['get']}.")
    expect(roles.count("classify") == 7, f"for 7 rows, {report} should call {names['classify']} 7 times, "
                                         f"but called it {roles.count('classify')} times.")
    expect(roles.count("summarize") == 1, f"{report} should call {names['summarize']} exactly once.")
    expect(roles[0] == "get" and roles[-1] == "summarize",
           f"{report} should call {names['get']} first and {names['summarize']} last.")
