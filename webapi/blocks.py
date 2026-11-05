"""Translate a student's Python into a Blockly workspace for the block editor.

The UI turns blocks back into Python itself (frontend/src/blocks/python.ts). Both sides use the
block list in frontend/src/blocks/format.ts, so a change to one of the three needs the others.

Translation is all or nothing. If the code doesn't compile, or uses something the blocks
can't show, the result says why and the UI starts the block workspace empty. Nothing here
runs the student's code: it is only parsed and compiled.
"""
from __future__ import annotations

import ast
import io
import json
import keyword
import math
import re
import tokenize
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

MAX_CODE_CHARS = 20_000
MAX_BLOCKS = 2_000
# Must match IDENT and NUMBER in frontend/src/blocks/format.ts: the block fields reject anything else.
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
NUMBER = re.compile(r"(?:\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)\Z")

BINARY = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
          ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>", ast.BitOr: "|", ast.BitXor: "^", ast.BitAnd: "&"}
UNARY = {ast.Not: "not", ast.USub: "-", ast.UAdd: "+", ast.Invert: "~"}
COMPARE = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
           ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not"}
BOOL = {ast.And: "and", ast.Or: "or"}
COMPREHENSION = {ast.ListComp: "list", ast.SetComp: "set", ast.GeneratorExp: "generator"}

# How the "can't show this yet" message names a construct.
NAMES = {
    "Lambda": "a lambda", "JoinedStr": "an f-string", "Try": "try / except", "With": "a with block",
    "ClassDef": "a class", "Global": "global", "Nonlocal": "nonlocal", "Delete": "del", "Assert": "assert",
    "AsyncFunctionDef": "async def", "AsyncFor": "async for", "AsyncWith": "async with", "Await": "await",
    "Yield": "yield", "YieldFrom": "yield from", "NamedExpr": "the := operator", "Starred": "* unpacking",
    "AnnAssign": "a type annotation", "Match": "match / case", "Slice": "a slice inside a tuple",
    "MatMult": "the @ operator",
}


class Unsupported(Exception):
    def __init__(self, what: str, node: Optional[ast.AST] = None):
        super().__init__(what)
        self.what = what
        self.line = getattr(node, "lineno", None)


class TooBig(Exception):
    pass


@dataclass
class Comment:
    line: int
    text: str
    full_line: bool  # nothing but whitespace before the #


def _fail(reason: str, message: str, line: Optional[int] = None) -> Dict[str, Any]:
    return {"ok": False, "reason": reason, "message": message, "line": line}


def _comments(code: str) -> List[Comment]:
    found = []
    for tok in tokenize.generate_tokens(io.StringIO(code).readline):
        if tok.type == tokenize.COMMENT:
            text = tok.string[1:]
            found.append(Comment(tok.start[0], text[1:] if text.startswith(" ") else text,
                                 not tok.line[:tok.start[1]].strip()))
    return found


def _ident(name: str, node: ast.AST) -> str:
    if not IDENT.match(name) or keyword.iskeyword(name):
        raise Unsupported(f"the name {name!r}", node)
    return name


def _dotted(node: ast.AST) -> Optional[str]:
    """`a.b.c` as text when it is only names and attributes, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    if not all(IDENT.match(p) and not keyword.iskeyword(p) for p in parts):
        return None
    return ".".join(reversed(parts))


def _chain(blocks: List[dict]) -> Optional[dict]:
    for first, second in zip(blocks, blocks[1:]):
        first["next"] = {"block": second}
    return blocks[0] if blocks else None


class _Translator:
    def __init__(self):
        self.count = 0

    def block(self, type_: str, fields: Optional[dict] = None, inputs: Optional[dict] = None,
              extra: Optional[dict] = None) -> dict:
        self.count += 1
        if self.count > MAX_BLOCKS:
            raise TooBig()
        out: Dict[str, Any] = {"type": type_}
        if fields:
            out["fields"] = fields
        connected = {name: {"block": b} for name, b in (inputs or {}).items() if b is not None}
        if connected:
            out["inputs"] = connected
        if extra is not None:
            out["extraState"] = extra
        return out

    # Statements -------------------------------------------------------------------------------
    def body(self, stmts: List[ast.stmt], comments: List[Comment]) -> List[dict]:
        """Blocks for one statement list, with comments placed between statements by line."""
        out: List[dict] = []
        pending = list(comments)
        for stmt in stmts:
            out += [self.comment(c) for c in pending if c.line < stmt.lineno]
            inside = [c for c in pending if stmt.lineno <= c.line <= stmt.end_lineno]
            pending = [c for c in pending if c.line > stmt.end_lineno]
            out.append(self.stmt(stmt, inside))
        return out + [self.comment(c) for c in pending]

    def comment(self, c: Comment) -> dict:
        return self.block("py_comment", {"TEXT": c.text})

    def body_input(self, stmts: List[ast.stmt], comments: List[Comment]) -> Optional[dict]:
        return _chain(self.body(stmts, comments))

    def stmt(self, node: ast.stmt, comments: List[Comment]) -> dict:
        compound = isinstance(node, (ast.FunctionDef, ast.If, ast.For, ast.While))
        if compound:
            # Comments at the end of header lines (`if x:  # note`) go on the block itself.
            first_child = node.body[0].lineno
            header = [c for c in comments if c.line < first_child and not c.full_line]
            rest = [c for c in comments if c not in header]
            block = self.compound(node, rest)
            attached = header
        else:
            block = self.simple(node)
            attached = comments
        if attached:
            block["icons"] = {"comment": {"text": "\n".join(c.text for c in attached), "pinned": False}}
        return block

    def compound(self, node: ast.stmt, comments: List[Comment]) -> dict:
        if isinstance(node, ast.FunctionDef):
            args = node.args
            if (node.decorator_list or node.returns or args.posonlyargs or args.vararg or args.kwonlyargs
                    or args.kwarg or args.defaults or any(a.annotation for a in args.args)):
                raise Unsupported("a def with decorators, default values, *args, or annotations", node)
            params = ", ".join(_ident(a.arg, node) for a in args.args)
            return self.block("py_def", {"NAME": _ident(node.name, node), "PARAMS": params},
                              {"BODY": self.body_input(node.body, comments)})
        if isinstance(node, ast.If):
            if not node.orelse:
                return self.block("py_if", inputs={"COND": self.expr(node.test),
                                                   "DO": self.body_input(node.body, comments)})
            split = node.orelse[0].lineno
            return self.block("py_if_else", inputs={
                "COND": self.expr(node.test),
                "DO": self.body_input(node.body, [c for c in comments if c.line < split]),
                "ELSE": self.body_input(node.orelse, [c for c in comments if c.line >= split])})
        if node.orelse:
            raise Unsupported(f"{'for' if isinstance(node, ast.For) else 'while'} ... else", node)
        if isinstance(node, ast.For):
            return self.block("py_for", inputs={"TARGET": self.expr(node.target), "ITER": self.expr(node.iter),
                                                "DO": self.body_input(node.body, comments)})
        return self.block("py_while", inputs={"COND": self.expr(node.test),
                                              "DO": self.body_input(node.body, comments)})

    def simple(self, node: ast.stmt) -> dict:
        if isinstance(node, ast.Expr):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return self.block("py_docstring", {"TEXT": value.value})
            if isinstance(value, ast.Call):
                return self.call(value, statement=True)
            return self.block("py_expr", inputs={"VALUE": self.expr(value)})
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise Unsupported("assigning to more than one name at once (a = b = ...)", node)
            return self.block("py_assign", inputs={"TARGET": self.expr(node.targets[0]),
                                                   "VALUE": self.expr(node.value)})
        if isinstance(node, ast.AugAssign):
            op = BINARY.get(type(node.op))
            if op is None:
                raise Unsupported(NAMES.get(type(node.op).__name__, "that operator"), node)
            return self.block("py_augassign", {"OP": op}, {"TARGET": self.expr(node.target),
                                                            "VALUE": self.expr(node.value)})
        if isinstance(node, ast.Return):
            return self.block("py_return", inputs={"VALUE": None if node.value is None else self.expr(node.value)})
        if isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
            return self.block("py_keyword", {"WORD": type(node).__name__.lower()})
        if isinstance(node, ast.Import):
            return self.block("py_import", {"NAMES": self.aliases(node.names, node)})
        if isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                raise Unsupported("a relative import", node)
            if any(a.name == "*" for a in node.names):
                raise Unsupported("import *", node)
            module = ".".join(_ident(p, node) for p in node.module.split("."))
            return self.block("py_from_import", {"MODULE": module, "NAMES": self.aliases(node.names, node)})
        if isinstance(node, ast.Raise):
            if node.cause is not None:
                raise Unsupported("raise ... from", node)
            return self.block("py_raise", inputs={"VALUE": None if node.exc is None else self.expr(node.exc)})
        name = type(node).__name__
        raise Unsupported(NAMES.get(name, name), node)

    @staticmethod
    def aliases(names: List[ast.alias], node: ast.AST) -> str:
        parts = []
        for a in names:
            text = ".".join(_ident(p, node) for p in a.name.split("."))
            if a.asname:
                text += f" as {_ident(a.asname, node)}"
            parts.append(text)
        return ", ".join(parts)

    # Expressions ------------------------------------------------------------------------------
    def expr(self, node: ast.expr) -> dict:
        if isinstance(node, ast.Name):
            return self.block("py_name", {"NAME": _ident(node.id, node)})
        if isinstance(node, ast.Attribute):
            dotted = _dotted(node)
            if dotted is not None:
                return self.block("py_name", {"NAME": dotted})
            return self.block("py_attribute", {"ATTR": _ident(node.attr, node)}, {"OBJ": self.expr(node.value)})
        if isinstance(node, ast.Constant):
            return self.constant(node)
        if isinstance(node, ast.UnaryOp):
            return self.block("py_unary", {"OP": UNARY[type(node.op)]}, {"VALUE": self.expr(node.operand)})
        if isinstance(node, ast.BinOp):
            op = BINARY.get(type(node.op))
            if op is None:
                raise Unsupported(NAMES.get(type(node.op).__name__, "that operator"), node)
            return self.block("py_binop", {"OP": op}, {"A": self.expr(node.left), "B": self.expr(node.right)})
        if isinstance(node, ast.BoolOp):
            # a and b and c is one node in Python; the blocks nest it from the left.
            acc = self.expr(node.values[0])
            for value in node.values[1:]:
                acc = self.block("py_boolop", {"OP": BOOL[type(node.op)]}, {"A": acc, "B": self.expr(value)})
            return acc
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise Unsupported("a chained comparison like a < b < c", node)
            return self.block("py_compare", {"OP": COMPARE[type(node.ops[0])]},
                              {"A": self.expr(node.left), "B": self.expr(node.comparators[0])})
        if isinstance(node, ast.Call):
            return self.call(node, statement=False)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                s = node.slice
                return self.block("py_slice", inputs={
                    "OBJ": self.expr(node.value),
                    "START": None if s.lower is None else self.expr(s.lower),
                    "STOP": None if s.upper is None else self.expr(s.upper),
                    "STEP": None if s.step is None else self.expr(s.step)})
            return self.block("py_index", inputs={"OBJ": self.expr(node.value), "INDEX": self.expr(node.slice)})
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            kind = {ast.List: "py_list", ast.Tuple: "py_tuple", ast.Set: "py_set"}[type(node)]
            return self.block(kind, inputs={f"ITEM{i}": self.expr(e) for i, e in enumerate(node.elts)},
                              extra={"items": len(node.elts)})
        if isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise Unsupported("** unpacking in a dictionary", node)
            inputs: Dict[str, Optional[dict]] = {}
            for i, (k, v) in enumerate(zip(node.keys, node.values)):
                inputs[f"KEY{i}"] = self.expr(k)
                inputs[f"VALUE{i}"] = self.expr(v)
            return self.block("py_dict", inputs=inputs, extra={"items": len(node.keys)})
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            gen = self.generator(node)
            if isinstance(node, ast.DictComp):
                return self.block("py_dictcomp", inputs={"KEY": self.expr(node.key), "VALUE": self.expr(node.value), **gen})
            return self.block("py_comprehension", {"KIND": COMPREHENSION[type(node)]}, {"ELT": self.expr(node.elt), **gen})
        if isinstance(node, ast.IfExp):
            return self.block("py_ternary", inputs={"BODY": self.expr(node.body), "COND": self.expr(node.test),
                                                    "ELSE": self.expr(node.orelse)})
        name = type(node).__name__
        raise Unsupported(NAMES.get(name, name), node)

    def generator(self, node) -> Dict[str, Optional[dict]]:
        if len(node.generators) != 1 or node.generators[0].is_async or len(node.generators[0].ifs) > 1:
            raise Unsupported("a comprehension with more than one for or if", node)
        g = node.generators[0]
        return {"TARGET": self.expr(g.target), "ITER": self.expr(g.iter),
                "COND": self.expr(g.ifs[0]) if g.ifs else None}

    def constant(self, node: ast.Constant) -> dict:
        v = node.value
        if v is None or isinstance(v, bool):
            return self.block("py_constant", {"VALUE": repr(v)})
        if isinstance(v, (int, float)):
            text = repr(v)
            if isinstance(v, float) and not math.isfinite(v) or not NUMBER.match(text):
                raise Unsupported(f"the number {text}", node)
            return self.block("py_number", {"NUM": text})
        if isinstance(v, str):
            return self.block("py_string", {"TEXT": v})
        if isinstance(v, complex):
            raise Unsupported("an imaginary number", node)
        if isinstance(v, bytes):
            raise Unsupported("a bytes value", node)
        raise Unsupported("...", node)

    def call(self, node: ast.Call, statement: bool) -> dict:
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            raise Unsupported("* or ** in a call", node)
        inputs: Dict[str, Optional[dict]] = {f"ARG{i}": self.expr(a) for i, a in enumerate(node.args)}
        names = []
        for i, k in enumerate(node.keywords):
            names.append(_ident(k.arg, node))
            inputs[f"KW{i}"] = self.expr(k.value)
        extra = {"args": len(node.args), "keywords": names}
        suffix = "_stmt" if statement else ""
        dotted = _dotted(node.func)
        if dotted is not None:
            return self.block("py_call" + suffix, {"FUNC": dotted}, inputs, extra)
        if isinstance(node.func, ast.Attribute):
            return self.block("py_method" + suffix, {"METHOD": _ident(node.func.attr, node)},
                              {"OBJ": self.expr(node.func.value), **inputs}, extra)
        raise Unsupported("calling something that isn't a name, like f()()", node)


def python_to_blocks(code: str) -> Dict[str, Any]:
    """{"ok": True, "workspace": ..., "blockCount": n}, or {"ok": False, "reason", "message", "line"}."""
    if len(code) > MAX_CODE_CHARS:
        return _fail("too_long", "This code is too long to show as blocks.")
    try:
        tree = ast.parse(code, "<your code>")
        compile(tree, "<your code>", "exec", dont_inherit=True)  # catches `return` outside a def, and so on
        comments = _comments(code)
    except SyntaxError as err:
        line = err.lineno
        return _fail("syntax_error", f"Line {line}: {err.msg}." if line else f"{err.msg}.", line)
    except (tokenize.TokenError, ValueError) as err:
        return _fail("syntax_error", f"The code can't be read: {err}.")
    except (RecursionError, MemoryError):
        return _fail("too_complex", "This code is nested too deeply to show as blocks.")

    tr = _Translator()
    try:
        head = _chain(tr.body(tree.body, comments))
        top = []
        if head is not None:
            head.update({"x": 20, "y": 20})
            top.append(head)
        workspace = {"blocks": {"languageVersion": 0, "blocks": top}}
        json.dumps(workspace)  # the HTTP layer will serialise it; fail here, not there
    except Unsupported as err:
        where = f"Line {err.line} uses" if err.line else "This code uses"
        return _fail("unsupported", f"{where} {err.what}, which blocks can't show yet.", err.line)
    except TooBig:
        return _fail("too_long", "This code has too many parts to show as blocks.")
    except (RecursionError, MemoryError):
        return _fail("too_complex", "This code is nested too deeply to show as blocks.")
    return {"ok": True, "workspace": workspace, "blockCount": tr.count}
