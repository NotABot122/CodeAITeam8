// The block bank shown on the left of the block workspace. Each entry is a ready-to-use block.
import type {BlockState} from './format';
import {COLOURS} from './defs';

const name = (n: string): BlockState => ({type: 'py_name', fields: {NAME: n}});
const num = (n: string): BlockState => ({type: 'py_number', fields: {NUM: n}});
const str = (s: string): BlockState => ({type: 'py_string', fields: {TEXT: s}});
const put = (block: BlockState, inputs: Record<string, BlockState>): BlockState =>
  ({...block, inputs: Object.fromEntries(Object.entries(inputs).map(([k, b]) => [k, {block: b}]))});
const call = (func: string, args: BlockState[], statement = false): BlockState =>
  put({type: statement ? 'py_call_stmt' : 'py_call', fields: {FUNC: func}, extraState: {args: args.length, keywords: []}},
    Object.fromEntries(args.map((a, i) => [`ARG${i}`, a])));
const method = (obj: string, m: string, args: BlockState[], statement = false): BlockState =>
  put({type: statement ? 'py_method_stmt' : 'py_method', fields: {METHOD: m}, extraState: {args: args.length, keywords: []}},
    {OBJ: name(obj), ...Object.fromEntries(args.map((a, i) => [`ARG${i}`, a]))});

const category = (label: string, colour: number | string, blocks: BlockState[]) =>
  ({kind: 'category', name: label, colour: String(colour), contents: blocks.map(b => ({kind: 'block', ...b}))});

export const TOOLBOX = {
  kind: 'categoryToolbox',
  contents: [
    category('Functions', COLOURS.func, [
      {type: 'py_def', fields: {NAME: 'my_function', PARAMS: 'rows'}},
      {type: 'py_return'},
      call('len', [name('rows')]),
      call('round', [name('total'), num('1')]),
      call('print', [str('hello')], true),
      method('my_list', 'append', [name('x')], true),
      method('my_list', 'sort', [], true),
      method('my_dict', 'get', [name('key'), num('0')]),
      method('conn', 'execute', [str('SELECT * FROM daily_readings WHERE station_id = ?'), {type: 'py_tuple', extraState: {items: 1}, inputs: {ITEM0: {block: name('station_id')}}}]),
      method('cursor', 'fetchall', []),
    ]),
    category('Logic', COLOURS.logic, [
      {type: 'py_if'},
      {type: 'py_if_else'},
      put({type: 'py_compare', fields: {OP: '>='}}, {A: name('x'), B: num('0')}),
      {type: 'py_boolop', fields: {OP: 'and'}},
      {type: 'py_unary', fields: {OP: 'not'}},
      {type: 'py_constant', fields: {VALUE: 'True'}},
      {type: 'py_constant', fields: {VALUE: 'None'}},
      {type: 'py_ternary'},
    ]),
    category('Loops', COLOURS.loop, [
      put({type: 'py_for'}, {TARGET: name('row'), ITER: name('rows')}),
      {type: 'py_while'},
      {type: 'py_keyword', fields: {WORD: 'break'}},
      {type: 'py_keyword', fields: {WORD: 'continue'}},
      {type: 'py_keyword', fields: {WORD: 'pass'}},
    ]),
    category('Variables', COLOURS.variable, [
      name('x'),
      put({type: 'py_assign'}, {TARGET: name('total'), VALUE: num('0')}),
      put({type: 'py_augassign', fields: {OP: '+'}}, {TARGET: name('total'), VALUE: num('1')}),
    ]),
    category('Math', COLOURS.math, [
      num('0'),
      {type: 'py_binop', fields: {OP: '+'}},
      {type: 'py_binop', fields: {OP: '/'}},
      {type: 'py_unary', fields: {OP: '-'}},
    ]),
    category('Text', COLOURS.text, [
      str(''),
      put({type: 'py_slice'}, {OBJ: name('text'), STOP: num('7')}),
    ]),
    category('Lists & Dicts', COLOURS.list, [
      {type: 'py_list', extraState: {items: 0}},
      {type: 'py_dict', extraState: {items: 0}},
      {type: 'py_tuple', extraState: {items: 2}},
      put({type: 'py_index'}, {OBJ: name('row'), INDEX: str('date')}),
      put({type: 'py_index'}, {OBJ: name('my_list'), INDEX: num('0')}),
      put({type: 'py_compare', fields: {OP: 'in'}}, {A: name('key'), B: name('my_dict')}),
      {type: 'py_comprehension', fields: {KIND: 'list'}},
      {type: 'py_dictcomp'},
    ]),
    category('Other', COLOURS.other, [
      {type: 'py_comment', fields: {TEXT: 'note'}},
      {type: 'py_docstring', fields: {TEXT: 'What this does.'}},
      {type: 'py_expr'},
      {type: 'py_import', fields: {NAMES: 'math'}},
      {type: 'py_from_import', fields: {MODULE: 'math', NAMES: 'sqrt'}},
      {type: 'py_raise'},
    ]),
  ],
};
