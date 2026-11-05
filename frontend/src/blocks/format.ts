// The block language shared by webapi/blocks.py (Python -> blocks), python.ts (blocks -> Python)
// and defs.ts (how Blockly draws them). Change all three together.
//
// No imports on purpose: python.ts and this file run without Blockly (tests, Node).

/** Blockly's JSON serialization of one block (the parts this editor uses). */
export interface BlockState {
  type: string;
  id?: string;
  x?: number;
  y?: number;
  fields?: Record<string, unknown>;
  inputs?: Record<string, {block?: BlockState; shadow?: BlockState}>;
  next?: {block?: BlockState};
  extraState?: {args?: number; keywords?: string[]; items?: number} | null;
  icons?: {comment?: {text?: string}};
  enabled?: boolean;
  disabledReasons?: string[];
}

export interface WorkspaceState {
  blocks?: {languageVersion?: number; blocks?: BlockState[]};
}

// Must match IDENT and NUMBER in webapi/blocks.py. Fields reject anything else, so the server
// never sends a value the blocks would silently drop.
export const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
export const NUMBER = /^(?:\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)$/;
export const KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del',
  'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal',
  'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
]);

export const isIdent = (s: string) => IDENT.test(s) && !KEYWORDS.has(s);
export const isDotted = (s: string) => s.split('.').every(isIdent);

/** "a,  b ,c" -> "a, b, c"; null if any part isn't a name. Empty is fine (no parameters). */
export function normaliseParams(s: string): string | null {
  const t = s.trim();
  if (!t) return '';
  const parts = t.split(',').map(p => p.trim());
  return parts.every(isIdent) ? parts.join(', ') : null;
}

/** "os.path, numpy as np" -> normalised, or null. */
export function normaliseImports(s: string): string | null {
  const parts = s.split(',').map(p => p.trim().split(/\s+/));
  const ok = parts.every(p => (p.length === 1 && isDotted(p[0])) || (p.length === 3 && isDotted(p[0]) && p[1] === 'as' && isIdent(p[2])));
  return ok ? parts.map(p => p.join(' ')).join(', ') : null;
}

export const BINARY_OPS = ['+', '-', '*', '/', '//', '%', '**', '<<', '>>', '|', '^', '&'] as const;
export const UNARY_OPS = ['not', '-', '+', '~'] as const;
export const COMPARE_OPS = ['==', '!=', '<', '<=', '>', '>=', 'in', 'not in', 'is', 'is not'] as const;
export const BOOL_OPS = ['and', 'or'] as const;
export const CONSTANTS = ['True', 'False', 'None'] as const;
export const KEYWORD_STMTS = ['pass', 'break', 'continue'] as const;
export const COMPREHENSION_KINDS = ['list', 'set', 'generator'] as const;

/** Blocks with a previous/next connection. Every other py_* block is an expression. */
export const STATEMENTS = new Set([
  'py_def', 'py_return', 'py_if', 'py_if_else', 'py_for', 'py_while', 'py_assign', 'py_augassign', 'py_expr',
  'py_call_stmt', 'py_method_stmt', 'py_keyword', 'py_comment', 'py_docstring', 'py_import', 'py_from_import',
  'py_raise',
]);

/** Inputs that may be left empty without being a mistake. */
export const OPTIONAL_INPUTS: Record<string, string[]> = {
  py_return: ['VALUE'],
  py_raise: ['VALUE'],
  py_slice: ['START', 'STOP', 'STEP'],
  py_comprehension: ['COND'],
  py_dictcomp: ['COND'],
};
