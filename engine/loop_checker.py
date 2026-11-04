"""Static check that a function uses a loop and avoids aggregate shortcuts."""
from __future__ import annotations

import ast
from typing import List

BANNED_CALLS = ("sum", "max", "min", "len", "sorted")


def find_loop_problems(source: str, function_name: str) -> List[str]:
    """Return plain-language problems. An empty list means the check passed.

    Comprehensions don't count as loops. Nested functions inside the target
    function are checked too. Method calls such as list.sort() are allowed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # the grader reports syntax errors separately

    target = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target = node
    if target is None:
        return []  # the REQUIRED check reports a missing function

    has_loop = False
    banned_lines = {}
    for node in ast.walk(target):
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            has_loop = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            banned_lines.setdefault(node.func.id, set()).add(node.lineno)

    problems = []
    if not has_loop:
        problems.append(f"{function_name} must use a for or while loop.")
    for name in BANNED_CALLS:
        if name in banned_lines:
            lines = sorted(banned_lines[name])
            where = f"line {lines[0]}" if len(lines) == 1 else "lines " + ", ".join(map(str, lines))
            problems.append(f"{function_name} must not call {name}() ({where}). Work it out with a loop instead.")
    return problems
