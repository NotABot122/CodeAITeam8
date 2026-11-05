import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {CodeBlock, tokenize} from '@/ui/CodeBlock';
import {InlineText} from '@/ui/markdown';

import {ItemView, QuestionBody} from './StepView';
import type {ItemStep} from './types';

const html = (node: JSX.Element) => renderToString(node).replace(/<!-- -->/g, '');

describe('question layout: code is shown as code, not run into a sentence', () => {
  it('draws a code block with one row per line, numbered and labelled', () => {
    const out = html(<CodeBlock code={'count = 0\nfor day in range(3):\n    count += 1'} lang="python" />);
    expect(out).toContain('aria-label="Python code"');
    expect(out).toContain('<figcaption');
    expect(out.match(/aria-hidden="true"[^>]*>\d</g)?.length).toBe(3);   // line numbers 1-3
    expect(out).toContain('<span>    </span><span>count</span>');       // indentation kept, white-space: pre
    expect(out).toContain('white-space:pre');
  });

  it('highlights keywords, strings, numbers and comments, in Python and SQL', () => {
    const kinds = (line: string, lang: 'python' | 'sql') => tokenize(line, lang).filter(t => t.kind !== 'plain').map(t => `${t.kind}:${t.text}`);
    expect(kinds("if temp >= 35.0: print('HOT')  # hot", 'python')).toEqual(['keyword:if', 'number:35.0', 'call:print', "string:'HOT'", 'comment:# hot']);
    expect(kinds("WHERE station_id = 'ST-A' AND rain_mm > 0", 'sql')).toEqual(['keyword:WHERE', "string:'ST-A'", 'keyword:AND', 'number:0']);
    expect(kinds("label = '# not a comment'", 'python')).toEqual(["string:'# not a comment'"]);
  });

  it('escapes markup inside code instead of injecting it', () => {
    const out = html(<CodeBlock code={'x = "<img src=x onerror=alert(1)>"'} />);
    expect(out).not.toContain('<img');
    expect(out).toContain('&lt;img');
  });

  it('renders `backtick` names inside a sentence as inline code', () => {
    const out = html(<InlineText text="Today `rain_mm` is 3.2." />);
    expect(out).toMatch(/<code[^>]*>rain_mm<\/code>/);
    expect(out).not.toContain('`');
  });

  it('shows the code block and the data table under the prompt', () => {
    const step: ItemStep = {
      kind: 'item', id: 'q', type: 'choice', prompt: 'p', options: [],
      code: {lang: 'sql', text: 'SELECT * FROM daily_readings'},
      table: {columns: ['station_id', 'rain_mm'], rows: [['ST-A', '14.2']]},
    };
    const out = html(<QuestionBody step={step} />);
    expect(out).toContain('aria-label="SQL code"');
    expect(out).toContain('<th scope="col">station_id</th>');
    expect(out).toContain('<td>14.2</td>');
    expect(html(<QuestionBody step={{...step, code: undefined, table: undefined}} />)).toBe('');
  });

  it('draws a spot question as numbered program lines to tap, in order, with indentation', () => {
    const step: ItemStep = {
      kind: 'item', id: 's', type: 'spot', prompt: 'Tap the line with the bug.',
      options: [{id: 'a', text: "temp = row['t']"}, {id: 'b', text: 'if temp > 35.0:'}, {id: 'c', text: "    labels.append('hot')"}],
    };
    const out = html(<ItemView step={step} value="b" onChange={() => {}} disabled={false} />);
    expect(out.indexOf('Line 1:')).toBeLessThan(out.indexOf('Line 2:'));
    expect(out).toContain('aria-label="Line 2: if temp &gt; 35.0:"');
    expect(out).toMatch(/aria-checked="true"[^>]*aria-label="Line 2/);
    expect(out).toContain("    labels.append(&#x27;hot&#x27;)");
  });

  it('uses the code font for code options and inline code for text options', () => {
    const base: ItemStep = {kind: 'item', id: 'c', type: 'choice', prompt: 'p', options: [{id: 'a', text: 'for r in rains: print(r)'}]};
    expect(html(<ItemView step={{...base, option_format: 'code'}} value={null} onChange={() => {}} disabled={false} />)).toContain('var(--code-font)');
    const text = html(<ItemView step={{...base, options: [{id: 'a', text: '`label` is never set'}]}} value={null} onChange={() => {}} disabled={false} />);
    expect(text).toMatch(/<code[^>]*>label<\/code> is never set/);
    expect(text).toContain('aria-label="label is never set"');
  });
});
