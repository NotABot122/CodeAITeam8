// How each py_* block looks in Blockly. The block list and field names are in format.ts; the
// Python they stand for is in python.ts. Fields validate what students type, so a block can't
// hold a name or number that isn't valid Python.
import {FieldMultilineInput} from '@blockly/field-multilineinput';
import * as Blockly from 'blockly/core';
import * as En from 'blockly/msg/en';

import {
  BINARY_OPS, BOOL_OPS, COMPARE_OPS, COMPREHENSION_KINDS, CONSTANTS, isDotted, isIdent, KEYWORD_STMTS,
  normaliseImports, normaliseParams, NUMBER, UNARY_OPS,
} from './format';

export const COLOURS = {func: 290, logic: 210, loop: 120, math: 230, text: 160, list: 260, variable: 330, other: 20, comment: '#8a8a99'};

type Block = Blockly.Block & {argCount?: number; keywords?: string[]; itemCount?: number};
type Colour = number | string;

const text = (value: string, check: (s: string) => string | null) => new Blockly.FieldTextInput(value, s => check(s));
const nameField = (value: string) => text(value, s => (isDotted(s.trim()) ? s.trim() : null));
const identField = (value: string) => text(value, s => (isIdent(s.trim()) ? s.trim() : null));
const dropdown = (values: readonly string[], labels: Record<string, string> = {}) =>
  new Blockly.FieldDropdown(values.map(v => [labels[v] ?? v, v] as [string, string]));

function statement(b: Block, colour: Colour, tooltip: string) {
  b.setPreviousStatement(true);
  b.setNextStatement(true);
  b.setColour(colour);
  b.setTooltip(tooltip);
}
function value(b: Block, colour: Colour, tooltip: string) {
  b.setOutput(true);
  b.setColour(colour);
  b.setInputsInline(true);
  b.setTooltip(tooltip);
}

// Variable-length inputs (call arguments, list items, dictionary pairs) --------------------------
const DYNAMIC = /^(ARG|KW|ITEM|KEY|VALUE)\d+$/;

/** Make the block's dynamic inputs exactly `wanted`, in order, just before the CLOSE input.
 *  Removing an input unplugs whatever was in it rather than deleting it. */
function syncInputs(b: Block, wanted: {name: string; label: string}[]) {
  const keep = new Set(wanted.map(w => w.name));
  for (const input of [...b.inputList]) if (DYNAMIC.test(input.name) && !keep.has(input.name)) b.removeInput(input.name);
  for (const w of wanted) {
    if (!b.getInput(w.name)) b.appendValueInput(w.name).appendField(new Blockly.FieldLabel(w.label), `SEP_${w.name}`);
    b.getField(`SEP_${w.name}`)?.setValue(w.label);
    b.moveInputBefore(w.name, 'CLOSE');
  }
}

/** Change a block's shape as one undoable step, and tell listeners (so the code updates). */
function mutate(b: Block, change: () => void) {
  const svg = b as Blockly.BlockSvg;
  const before = Blockly.Events.BlockChange.getExtraBlockState_(svg);
  Blockly.Events.setGroup(true);
  change();
  const after = Blockly.Events.BlockChange.getExtraBlockState_(svg);
  Blockly.Events.fire(new (Blockly.Events.get(Blockly.Events.BLOCK_CHANGE))(b, 'mutation', null, before, after));
  Blockly.Events.setGroup(false);
}

const count = (n: unknown) => (typeof n === 'number' && Number.isInteger(n) && n >= 0 && n <= 50 ? n : 0);

const argsMixin = {
  saveExtraState(this: Block) { return {args: this.argCount ?? 0, keywords: [...(this.keywords ?? [])]}; },
  loadExtraState(this: Block, state: {args?: number; keywords?: unknown}) {
    this.argCount = count(state?.args);
    this.keywords = Array.isArray(state?.keywords) ? state.keywords.filter((k): k is string => typeof k === 'string' && isIdent(k)) : [];
    (this as unknown as {updateArgs(): void}).updateArgs();
  },
  updateArgs(this: Block) {
    const n = this.argCount ?? 0;
    const kws = this.keywords ?? [];
    syncInputs(this, [
      ...Array.from({length: n}, (_, i) => ({name: `ARG${i}`, label: i ? ',' : ''})),
      ...kws.map((k, i) => ({name: `KW${i}`, label: `${i + n ? ', ' : ''}${k}=`})),
    ]);
  },
  customContextMenu(this: Block, options: Blockly.ContextMenuRegistry.LegacyContextMenuOption[]) {
    if (!this.isEditable()) return;
    const update = () => (this as unknown as {updateArgs(): void}).updateArgs();
    options.push(
      {text: 'Add an argument', enabled: true, callback: () => mutate(this, () => { this.argCount = (this.argCount ?? 0) + 1; update(); })},
      {text: 'Remove the last argument', enabled: (this.argCount ?? 0) > 0, callback: () => mutate(this, () => { this.argCount = (this.argCount ?? 1) - 1; update(); })},
    );
    if (this.keywords?.length) {
      const last = this.keywords[this.keywords.length - 1];
      options.push({text: `Remove ${last}=`, enabled: true, callback: () => mutate(this, () => { this.keywords = this.keywords!.slice(0, -1); update(); })});
    }
  },
};

function itemsMixin(kind: 'items' | 'pairs', noun: string) {
  return {
    saveExtraState(this: Block) { return {items: this.itemCount ?? 0}; },
    loadExtraState(this: Block, state: {items?: number}) {
      this.itemCount = count(state?.items);
      (this as unknown as {updateItems(): void}).updateItems();
    },
    updateItems(this: Block) {
      const n = this.itemCount ?? 0;
      syncInputs(this, kind === 'items'
        ? Array.from({length: n}, (_, i) => ({name: `ITEM${i}`, label: i ? ',' : ''}))
        : Array.from({length: n}, (_, i) => [{name: `KEY${i}`, label: i ? ',' : ''}, {name: `VALUE${i}`, label: ':'}]).flat());
    },
    customContextMenu(this: Block, options: Blockly.ContextMenuRegistry.LegacyContextMenuOption[]) {
      if (!this.isEditable()) return;
      const update = () => (this as unknown as {updateItems(): void}).updateItems();
      options.push(
        {text: `Add ${noun}`, enabled: true, callback: () => mutate(this, () => { this.itemCount = (this.itemCount ?? 0) + 1; update(); })},
        {text: `Remove the last ${noun.replace(/^an? /, '')}`, enabled: (this.itemCount ?? 0) > 0, callback: () => mutate(this, () => { this.itemCount = (this.itemCount ?? 1) - 1; update(); })},
      );
    },
  };
}

function define(type: string, init: (this: Block) => void, extra: object = {}) {
  Blockly.Blocks[type] = {init, ...extra};
}

/** Call, method call, and their statement forms share one layout: head ( args ) */
function defineCalls() {
  const callHead = (b: Block) => b.appendDummyInput('HEAD').appendField(nameField('print'), 'FUNC').appendField('(');
  const methodHead = (b: Block) => b.appendValueInput('OBJ').appendField('');
  const methodName = (b: Block) => b.appendDummyInput('HEAD').appendField('.').appendField(identField('append'), 'METHOD').appendField('(');
  const close = (b: Block) => { b.appendDummyInput('CLOSE').appendField(')'); b.setInputsInline(true); b.argCount = 0; b.keywords = []; };
  const tip = 'Calls a function. Right-click to add or remove arguments.';
  define('py_call', function () { callHead(this); close(this); value(this, COLOURS.func, tip); }, argsMixin);
  define('py_call_stmt', function () { callHead(this); close(this); statement(this, COLOURS.func, tip); }, argsMixin);
  define('py_method', function () { methodHead(this); methodName(this); close(this); value(this, COLOURS.func, 'Calls a method on a value, like my_list.append(x).'); }, argsMixin);
  define('py_method_stmt', function () { methodHead(this); methodName(this); close(this); statement(this, COLOURS.func, 'Calls a method on a value, like my_list.append(x).'); }, argsMixin);
}

function defineCollections() {
  const shape = (b: Block, open: string, close: string) => {
    b.appendDummyInput('OPEN').appendField(open);
    b.appendDummyInput('CLOSE').appendField(close);
    b.itemCount = 0;
  };
  const tip = 'Right-click to add or remove items.';
  define('py_list', function () { shape(this, '[', ']'); value(this, COLOURS.list, `A list. ${tip}`); }, itemsMixin('items', 'an item'));
  define('py_tuple', function () { shape(this, '(', ')'); value(this, COLOURS.list, `A tuple: values grouped together, like (row, labels). ${tip}`); }, itemsMixin('items', 'an item'));
  define('py_set', function () { shape(this, '{', '}'); value(this, COLOURS.list, `A set: values with no repeats. ${tip}`); }, itemsMixin('items', 'an item'));
  define('py_dict', function () { shape(this, '{', '}'); value(this, COLOURS.list, 'A dictionary of key: value pairs. Right-click to add or remove pairs.'); }, itemsMixin('pairs', 'a key and value'));
}

let defined = false;

/** Register every py_* block with Blockly. Safe to call more than once. */
export function defineBlocks() {
  if (defined) return;
  defined = true;
  Blockly.setLocale(En as unknown as Record<string, string>);

  // Functions
  define('py_def', function () {
    this.appendDummyInput().appendField('def').appendField(identField('my_function'), 'NAME').appendField('(')
      .appendField(text('', s => normaliseParams(s)), 'PARAMS').appendField('):');
    this.appendStatementInput('BODY');
    statement(this, COLOURS.func, 'Defines a function. List the parameters between the brackets, separated by commas.');
  });
  define('py_return', function () {
    this.appendValueInput('VALUE').appendField('return');
    statement(this, COLOURS.func, 'Ends the function and gives back a value. Leave the slot empty to return nothing.');
  });
  defineCalls();

  // Logic
  define('py_if', function () {
    this.appendValueInput('COND').appendField('if');
    this.appendDummyInput().appendField(':');
    this.appendStatementInput('DO');
    this.setInputsInline(true);
    statement(this, COLOURS.logic, 'Runs the blocks inside only when the condition is true.');
  });
  define('py_if_else', function () {
    this.appendValueInput('COND').appendField('if');
    this.appendDummyInput().appendField(':');
    this.appendStatementInput('DO');
    this.appendDummyInput().appendField('else:');
    this.appendStatementInput('ELSE');
    this.setInputsInline(true);
    statement(this, COLOURS.logic, 'Runs the first blocks when the condition is true, otherwise the blocks under else. Put another if under else to make an elif.');
  });
  define('py_compare', function () {
    this.appendValueInput('A');
    this.appendValueInput('B').appendField(dropdown(COMPARE_OPS), 'OP');
    value(this, COLOURS.logic, 'Compares two values and gives True or False.');
  });
  define('py_boolop', function () {
    this.appendValueInput('A');
    this.appendValueInput('B').appendField(dropdown(BOOL_OPS), 'OP');
    value(this, COLOURS.logic, 'and: both must be true. or: at least one must be true.');
  });
  define('py_unary', function () {
    this.appendValueInput('VALUE').appendField(dropdown(UNARY_OPS), 'OP');
    value(this, COLOURS.logic, 'not flips True and False. - makes a number negative.');
  });
  define('py_ternary', function () {
    this.appendValueInput('BODY');
    this.appendValueInput('COND').appendField('if');
    this.appendValueInput('ELSE').appendField('else');
    value(this, COLOURS.logic, 'Gives the first value when the condition is true, otherwise the last one.');
  });
  define('py_constant', function () {
    this.appendDummyInput().appendField(dropdown(CONSTANTS), 'VALUE');
    value(this, COLOURS.logic, 'True, False, or None (no value).');
  });

  // Loops
  define('py_for', function () {
    this.appendValueInput('TARGET').appendField('for');
    this.appendValueInput('ITER').appendField('in');
    this.appendDummyInput().appendField(':');
    this.appendStatementInput('DO');
    this.setInputsInline(true);
    statement(this, COLOURS.loop, 'Runs the blocks inside once for each item.');
  });
  define('py_while', function () {
    this.appendValueInput('COND').appendField('while');
    this.appendDummyInput().appendField(':');
    this.appendStatementInput('DO');
    this.setInputsInline(true);
    statement(this, COLOURS.loop, 'Keeps running the blocks inside while the condition is true.');
  });
  define('py_keyword', function () {
    this.appendDummyInput().appendField(dropdown(KEYWORD_STMTS), 'WORD');
    statement(this, COLOURS.loop, 'pass does nothing. break leaves the loop. continue skips to the next item.');
  });

  // Variables and values
  define('py_name', function () {
    this.appendDummyInput().appendField(nameField('x'), 'NAME');
    value(this, COLOURS.variable, 'A variable or name, like total or cursor.description.');
  });
  define('py_assign', function () {
    this.appendValueInput('TARGET');
    this.appendValueInput('VALUE').appendField('=');
    this.setInputsInline(true);
    statement(this, COLOURS.variable, 'Stores the value on the right in the name on the left.');
  });
  define('py_augassign', function () {
    this.appendValueInput('TARGET');
    this.appendValueInput('VALUE').appendField(dropdown(BINARY_OPS, Object.fromEntries(BINARY_OPS.map(o => [o, `${o}=`]))), 'OP');
    this.setInputsInline(true);
    statement(this, COLOURS.variable, 'Updates a variable, like total += 1 (add one to total).');
  });
  define('py_number', function () {
    this.appendDummyInput().appendField(text('0', s => (NUMBER.test(s.trim()) ? s.trim() : null)), 'NUM');
    value(this, COLOURS.math, 'A number, like 3 or 35.0.');
  });
  define('py_binop', function () {
    this.appendValueInput('A');
    this.appendValueInput('B').appendField(dropdown(BINARY_OPS), 'OP');
    value(this, COLOURS.math, 'Arithmetic: + - * / (divide), // (whole-number divide), % (remainder), ** (power).');
  });
  define('py_string', function () {
    this.appendDummyInput().appendField('"').appendField(new Blockly.FieldTextInput(''), 'TEXT').appendField('"');
    value(this, COLOURS.text, 'Text.');
  });

  // Lists and dictionaries
  defineCollections();
  define('py_index', function () {
    this.appendValueInput('OBJ');
    this.appendValueInput('INDEX').appendField('[');
    this.appendDummyInput().appendField(']');
    value(this, COLOURS.list, 'Gets one item: my_list[0] is the first item, my_dict["key"] is the value for that key.');
  });
  define('py_slice', function () {
    this.appendValueInput('OBJ');
    this.appendValueInput('START').appendField('[');
    this.appendValueInput('STOP').appendField(':');
    this.appendValueInput('STEP').appendField(':');
    this.appendDummyInput().appendField(']');
    value(this, COLOURS.list, 'Gets part of a list or text: text[:7] is the first 7 characters. Empty slots mean "from the start" or "to the end".');
  });
  define('py_attribute', function () {
    this.appendValueInput('OBJ');
    this.appendDummyInput().appendField('.').appendField(identField('attribute'), 'ATTR');
    value(this, COLOURS.list, 'Gets an attribute of a value.');
  });
  define('py_comprehension', function () {
    this.appendValueInput('ELT').appendField(dropdown(COMPREHENSION_KINDS, {list: '[ list', set: '{ set', generator: '( generator'}), 'KIND');
    this.appendValueInput('TARGET').appendField('for');
    this.appendValueInput('ITER').appendField('in');
    this.appendValueInput('COND').appendField('if');
    value(this, COLOURS.list, 'Builds a list from a loop in one line. The if slot is optional.');
  });
  define('py_dictcomp', function () {
    this.appendValueInput('KEY').appendField('{');
    this.appendValueInput('VALUE').appendField(':');
    this.appendValueInput('TARGET').appendField('for');
    this.appendValueInput('ITER').appendField('in');
    this.appendValueInput('COND').appendField('if');
    this.appendDummyInput().appendField('}');
    value(this, COLOURS.list, 'Builds a dictionary from a loop in one line. The if slot is optional.');
  });

  // Other statements
  define('py_expr', function () {
    this.appendValueInput('VALUE').appendField('do');
    statement(this, COLOURS.other, 'Works out a value as its own line, for example a method call.');
  });
  define('py_comment', function () {
    this.appendDummyInput().appendField('#').appendField(new Blockly.FieldTextInput('note'), 'TEXT');
    statement(this, COLOURS.comment, 'A note for people reading the code. Python ignores it.');
  });
  define('py_docstring', function () {
    this.appendDummyInput().appendField('"""').appendField(new FieldMultilineInput(''), 'TEXT').appendField('"""');
    statement(this, COLOURS.comment, 'A description of the file or function, in triple quotes.');
  });
  define('py_import', function () {
    this.appendDummyInput().appendField('import').appendField(text('math', s => normaliseImports(s)), 'NAMES');
    statement(this, COLOURS.other, 'Loads a module, like import math.');
  });
  define('py_from_import', function () {
    this.appendDummyInput().appendField('from').appendField(nameField('math'), 'MODULE')
      .appendField('import').appendField(text('sqrt', s => normaliseImports(s)), 'NAMES');
    statement(this, COLOURS.other, 'Loads names from a module, like from math import sqrt.');
  });
  define('py_raise', function () {
    this.appendValueInput('VALUE').appendField('raise');
    statement(this, COLOURS.other, 'Stops with an error.');
  });
}
