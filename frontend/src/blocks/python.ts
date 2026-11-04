// Blocks -> Python, working on Blockly's JSON (no Blockly needed). The output must parse to the
// same Python AST that webapi/blocks.py read the blocks from, so parentheses follow Python's
// precedence rules exactly. Extra parentheses never change the AST; missing ones do.
import {normaliseImports, normaliseParams, OPTIONAL_INPUTS, STATEMENTS, type BlockState, type WorkspaceState} from './format';

export interface Generated {
  code: string;
  /** Required slots left empty; each becomes None in the code. */
  emptySlots: number;
  /** Top-level expression blocks not attached to anything; they aren't in the code. */
  looseBlocks: number;
}

// Python precedence, low to high.
const P = {TERNARY: 2, OR: 3, AND: 4, NOT: 5, CMP: 6, BOR: 7, BXOR: 8, BAND: 9, SHIFT: 10, ADD: 11, MUL: 12, UNARY: 13, POW: 14, PRIMARY: 16, ATOM: 17};
const BINARY_PREC: Record<string, number> = {
  '|': P.BOR, '^': P.BXOR, '&': P.BAND, '<<': P.SHIFT, '>>': P.SHIFT, '+': P.ADD, '-': P.ADD,
  '*': P.MUL, '/': P.MUL, '//': P.MUL, '%': P.MUL, '**': P.POW,
};
const INDENT = '    ';

interface Expr {code: string; prec: number}

const field = (b: BlockState, name: string) => String(b.fields?.[name] ?? '');
const child = (b: BlockState, name: string) => b.inputs?.[name]?.block;
const nextOf = (b: BlockState) => b.next?.block;

/** A Python string literal for any text. */
export function pyString(s: string): string {
  let out = '"';
  for (const ch of s) {
    const c = ch.codePointAt(0)!;
    if (ch === '\\') out += '\\\\';
    else if (ch === '"') out += '\\"';
    else if (ch === '\n') out += '\\n';
    else if (ch === '\r') out += '\\r';
    else if (ch === '\t') out += '\\t';
    else if (c < 0x20 || (c >= 0x7f && c <= 0x9f)) out += '\\x' + c.toString(16).padStart(2, '0');
    else if (c >= 0xd800 && c <= 0xdfff) out += '\\u' + c.toString(16).padStart(4, '0');
    else out += ch;
  }
  return out + '"';
}

/** A triple-quoted literal, escaping only what would end it early. */
export function pyDocstring(s: string): string {
  let out = '"""';
  let run = 0;
  const chars = [...s];
  chars.forEach((ch, i) => {
    const c = ch.codePointAt(0)!;
    if (ch === '"') {
      if (run === 2 || i === chars.length - 1) { out += '\\"'; run = 0; } else { out += '"'; run++; }
      return;
    }
    run = 0;
    if (ch === '\\') out += '\\\\';
    else if (ch === '\n' || ch === '\t') out += ch;
    else if (ch === '\r') out += '\\r';
    else if (c < 0x20 || (c >= 0x7f && c <= 0x9f)) out += '\\x' + c.toString(16).padStart(2, '0');
    else if (c >= 0xd800 && c <= 0xdfff) out += '\\u' + c.toString(16).padStart(4, '0');
    else out += ch;
  });
  return out + '"""';
}

class Gen {
  emptySlots = 0;

  // Expressions -----------------------------------------------------------------------------
  expr(b: BlockState | undefined, owner?: BlockState, slot?: string): Expr {
    if (!b) {
      if (!(owner && slot && OPTIONAL_INPUTS[owner.type]?.includes(slot))) this.emptySlots++;
      return {code: 'None', prec: P.ATOM};
    }
    switch (b.type) {
      case 'py_name': return {code: field(b, 'NAME') || 'None', prec: P.ATOM};
      case 'py_number': return {code: field(b, 'NUM') || '0', prec: P.ATOM};
      case 'py_string': return {code: pyString(field(b, 'TEXT')), prec: P.ATOM};
      case 'py_constant': return {code: field(b, 'VALUE') || 'None', prec: P.ATOM};
      case 'py_binop': {
        const op = field(b, 'OP');
        const p = BINARY_PREC[op] ?? P.ADD;
        const a = this.expr(child(b, 'A'), b, 'A');
        const c = this.expr(child(b, 'B'), b, 'B');
        const left = op === '**' ? this.wrap(a, a.prec <= P.POW) : this.wrap(a, a.prec < p);
        const right = op === '**' ? this.wrap(c, c.prec < P.UNARY) : this.wrap(c, c.prec <= p);
        return {code: `${left} ${op} ${right}`, prec: p};
      }
      case 'py_unary': {
        const op = field(b, 'OP');
        const v = this.expr(child(b, 'VALUE'), b, 'VALUE');
        if (op === 'not') return {code: `not ${this.wrap(v, v.prec < P.NOT)}`, prec: P.NOT};
        return {code: `${op}${this.wrap(v, v.prec < P.UNARY)}`, prec: P.UNARY};
      }
      case 'py_compare': {
        const a = this.expr(child(b, 'A'), b, 'A');
        const c = this.expr(child(b, 'B'), b, 'B');
        return {code: `${this.wrap(a, a.prec <= P.CMP)} ${field(b, 'OP')} ${this.wrap(c, c.prec <= P.CMP)}`, prec: P.CMP};
      }
      case 'py_boolop': {
        const op = field(b, 'OP');
        const p = op === 'or' ? P.OR : P.AND;
        const a = this.expr(child(b, 'A'), b, 'A');
        const c = this.expr(child(b, 'B'), b, 'B');
        return {code: `${this.wrap(a, a.prec < p)} ${op} ${this.wrap(c, c.prec <= p)}`, prec: p};
      }
      case 'py_ternary': {
        const body = this.expr(child(b, 'BODY'), b, 'BODY');
        const cond = this.expr(child(b, 'COND'), b, 'COND');
        const other = this.expr(child(b, 'ELSE'), b, 'ELSE');
        return {code: `${this.wrap(body, body.prec <= P.TERNARY)} if ${this.wrap(cond, cond.prec <= P.TERNARY)} else ${other.code}`, prec: P.TERNARY};
      }
      case 'py_call': return {code: `${field(b, 'FUNC')}(${this.args(b)})`, prec: P.PRIMARY};
      case 'py_method': return {code: `${this.primary(child(b, 'OBJ'), b)}.${field(b, 'METHOD')}(${this.args(b)})`, prec: P.PRIMARY};
      case 'py_attribute': return {code: `${this.primary(child(b, 'OBJ'), b)}.${field(b, 'ATTR')}`, prec: P.PRIMARY};
      case 'py_index': return {code: `${this.primary(child(b, 'OBJ'), b)}[${this.expr(child(b, 'INDEX'), b, 'INDEX').code}]`, prec: P.PRIMARY};
      case 'py_slice': {
        const part = (name: string) => (child(b, name) ? this.expr(child(b, name), b, name).code : '');
        const step = child(b, 'STEP') ? `:${part('STEP')}` : '';
        return {code: `${this.primary(child(b, 'OBJ'), b)}[${part('START')}:${part('STOP')}${step}]`, prec: P.PRIMARY};
      }
      case 'py_list': return {code: `[${this.items(b).join(', ')}]`, prec: P.ATOM};
      case 'py_set': {
        const items = this.items(b);
        return items.length ? {code: `{${items.join(', ')}}`, prec: P.ATOM} : {code: 'set()', prec: P.PRIMARY};
      }
      case 'py_tuple': return {code: this.tuple(b, false), prec: P.ATOM};
      case 'py_dict': {
        const n = b.extraState?.items ?? 0;
        const pairs = Array.from({length: n}, (_, i) =>
          `${this.expr(child(b, `KEY${i}`), b, `KEY${i}`).code}: ${this.expr(child(b, `VALUE${i}`), b, `VALUE${i}`).code}`);
        return {code: `{${pairs.join(', ')}}`, prec: P.ATOM};
      }
      case 'py_comprehension': {
        const kind = field(b, 'KIND');
        const [open, close] = kind === 'set' ? ['{', '}'] : kind === 'generator' ? ['(', ')'] : ['[', ']'];
        return {code: `${open}${this.expr(child(b, 'ELT'), b, 'ELT').code}${this.comp(b)}${close}`, prec: P.ATOM};
      }
      case 'py_dictcomp':
        return {code: `{${this.expr(child(b, 'KEY'), b, 'KEY').code}: ${this.expr(child(b, 'VALUE'), b, 'VALUE').code}${this.comp(b)}}`, prec: P.ATOM};
      default:
        // A statement block plugged into a value slot can't happen in Blockly; treat as empty.
        this.emptySlots++;
        return {code: 'None', prec: P.ATOM};
    }
  }

  wrap(e: Expr, parens: boolean) { return parens ? `(${e.code})` : e.code; }

  /** The object in obj.x / obj(...) / obj[...]; `1.real` needs parentheses too. */
  primary(b: BlockState | undefined, owner: BlockState) {
    const e = this.expr(b, owner, 'OBJ');
    return this.wrap(e, e.prec < P.PRIMARY || (b?.type === 'py_number' && /^\d+$/.test(e.code)));
  }

  args(b: BlockState): string {
    const n = b.extraState?.args ?? 0;
    const kws = b.extraState?.keywords ?? [];
    const pos = Array.from({length: n}, (_, i) => this.expr(child(b, `ARG${i}`), b, `ARG${i}`).code);
    const named = kws.map((k, i) => `${k}=${this.expr(child(b, `KW${i}`), b, `KW${i}`).code}`);
    return [...pos, ...named].join(', ');
  }

  items(b: BlockState): string[] {
    const n = b.extraState?.items ?? 0;
    return Array.from({length: n}, (_, i) => this.expr(child(b, `ITEM${i}`), b, `ITEM${i}`).code);
  }

  /** Tuples get parentheses except where Python's own style leaves them off (a, b = ...). */
  tuple(b: BlockState, bare: boolean): string {
    const items = this.items(b);
    if (items.length === 0) return '()';
    if (items.length === 1) return bare ? `${items[0]},` : `(${items[0]},)`;
    return bare ? items.join(', ') : `(${items.join(', ')})`;
  }

  /** A target, value or return value: a tuple there needs no parentheses. */
  bareExpr(b: BlockState | undefined, owner: BlockState, slot: string): string {
    if (b?.type === 'py_tuple' && (b.extraState?.items ?? 0) > 0) return this.tuple(b, true);
    return this.expr(b, owner, slot).code;
  }

  comp(b: BlockState): string {
    const iter = this.expr(child(b, 'ITER'), b, 'ITER');
    let out = ` for ${this.bareExpr(child(b, 'TARGET'), b, 'TARGET')} in ${this.wrap(iter, iter.prec <= P.TERNARY)}`;
    if (child(b, 'COND')) {
      const cond = this.expr(child(b, 'COND'), b, 'COND');
      out += ` if ${this.wrap(cond, cond.prec <= P.TERNARY)}`;
    }
    return out;
  }

  // Statements ------------------------------------------------------------------------------
  /** One entry per statement line. An entry can hold newlines from a multi-line string; only its
   *  start is indented, since indenting inside the string would change its value. */
  body(first: BlockState | undefined, depth: number): string[] {
    const out: string[] = [];
    let statements = 0;  // comments alone don't make a valid body
    for (let b = first; b; b = nextOf(b)) {
      const lines = this.stmt(b, depth);
      out.push(...lines);
      if (b.type !== 'py_comment' && lines.length) statements++;
    }
    if (!statements) out.push(INDENT.repeat(depth) + 'pass');
    return out;
  }

  stmt(b: BlockState, depth: number): string[] {
    const pad = INDENT.repeat(depth);
    const lines = this.stmtLines(b, depth);
    const note = b.icons?.comment?.text?.trim();
    if (!note || !lines.length) return lines;
    // Block comments: one line goes after the statement's first line; longer ones go above it.
    if (!note.includes('\n')) return [`${lines[0]}  # ${note}`, ...lines.slice(1)];
    return [...note.split('\n').map(l => `${pad}# ${l.trim()}`.trimEnd()), ...lines];
  }

  stmtLines(b: BlockState, depth: number): string[] {
    const pad = INDENT.repeat(depth);
    const block = (header: string, name: string) => [pad + header, ...this.body(child(b, name), depth + 1)];
    switch (b.type) {
      case 'py_def': return block(`def ${field(b, 'NAME')}(${normaliseParams(field(b, 'PARAMS')) ?? field(b, 'PARAMS')}):`, 'BODY');
      case 'py_return': return [pad + (child(b, 'VALUE') ? `return ${this.bareExpr(child(b, 'VALUE'), b, 'VALUE')}` : 'return')];
      case 'py_raise': return [pad + (child(b, 'VALUE') ? `raise ${this.expr(child(b, 'VALUE'), b, 'VALUE').code}` : 'raise')];
      case 'py_if': return block(`if ${this.expr(child(b, 'COND'), b, 'COND').code}:`, 'DO');
      case 'py_if_else': {
        const out = block(`if ${this.expr(child(b, 'COND'), b, 'COND').code}:`, 'DO');
        const other = child(b, 'ELSE');
        // else: containing only an if is the same Python as elif, so write it the usual way.
        if (other && (other.type === 'py_if' || other.type === 'py_if_else') && !nextOf(other)) {
          const nested = this.stmt(other, depth);
          const first = nested.findIndex(l => l.startsWith(pad + 'if '));
          nested[first] = pad + 'el' + nested[first].slice(pad.length);
          return [...out, ...nested];
        }
        return [...out, pad + 'else:', ...this.body(other, depth + 1)];
      }
      case 'py_for': {
        const iter = this.expr(child(b, 'ITER'), b, 'ITER');
        return block(`for ${this.bareExpr(child(b, 'TARGET'), b, 'TARGET')} in ${iter.code}:`, 'DO');
      }
      case 'py_while': return block(`while ${this.expr(child(b, 'COND'), b, 'COND').code}:`, 'DO');
      case 'py_assign': return [pad + `${this.bareExpr(child(b, 'TARGET'), b, 'TARGET')} = ${this.bareExpr(child(b, 'VALUE'), b, 'VALUE')}`];
      case 'py_augassign': return [pad + `${this.expr(child(b, 'TARGET'), b, 'TARGET').code} ${field(b, 'OP')}= ${this.bareExpr(child(b, 'VALUE'), b, 'VALUE')}`];
      case 'py_expr': return [pad + this.expr(child(b, 'VALUE'), b, 'VALUE').code];
      case 'py_call_stmt': return [pad + this.expr({...b, type: 'py_call'}).code];
      case 'py_method_stmt': return [pad + this.expr({...b, type: 'py_method'}).code];
      case 'py_keyword': return [pad + (field(b, 'WORD') || 'pass')];
      case 'py_comment': return [`${pad}# ${field(b, 'TEXT')}`.trimEnd()];
      case 'py_docstring': return [pad + pyDocstring(field(b, 'TEXT'))];
      case 'py_import': return [pad + `import ${normaliseImports(field(b, 'NAMES')) ?? field(b, 'NAMES')}`];
      case 'py_from_import': return [pad + `from ${field(b, 'MODULE')} import ${normaliseImports(field(b, 'NAMES')) ?? field(b, 'NAMES')}`];
      default: return [];
    }
  }
}

const isDef = (b: BlockState) => b.type === 'py_def';

/** Python for a whole workspace. Top-level stacks run top to bottom, then left to right. */
export function workspaceToPython(state: WorkspaceState | null | undefined): Generated {
  const gen = new Gen();
  const tops = [...(state?.blocks?.blocks ?? [])].sort((a, b) => (a.y ?? 0) - (b.y ?? 0) || (a.x ?? 0) - (b.x ?? 0));
  const stmts: BlockState[] = [];
  let looseBlocks = 0;
  for (const top of tops) {
    if (!STATEMENTS.has(top.type)) { looseBlocks++; continue; }
    for (let b: BlockState | undefined = top; b; b = nextOf(b)) stmts.push(b);
  }
  // PEP 8: two blank lines around top-level functions; comments right above a def stay with it.
  const startsDefGroup = (i: number) => {
    let j = i;
    while (j < stmts.length && stmts[j].type === 'py_comment') j++;
    return j < stmts.length && isDef(stmts[j]);
  };
  const out: string[] = [];
  stmts.forEach((b, i) => {
    if (i > 0 && (isDef(stmts[i - 1]) || (startsDefGroup(i) && stmts[i - 1].type !== 'py_comment'))) out.push('', '');
    out.push(...gen.stmt(b, 0));
  });
  return {code: out.length ? out.join('\n') + '\n' : '', emptySlots: gen.emptySlots, looseBlocks};
}
