import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {Markdown} from './markdown';

const html = (s: string) => renderToString(<Markdown source={s} />).replace(/<!-- -->/g, '');

describe('Markdown', () => {
  it('renders headings, code, tables and lists', () => {
    const out = html('# Title\n\nUse `conn` now.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n\n```python\nprint(1)\n```');
    expect(out).toContain('Title');
    expect(out).toContain('<code');
    expect(out).toContain('<th>A</th>');
    expect(out).toContain('<li>two</li>');
    expect(out).toContain('print(1)');
  });
  it('escapes markup instead of injecting it', () => {
    const out = html('<img src=x onerror=alert(1)> **bold**');
    expect(out).not.toContain('<img');
    expect(out).toContain('<strong>bold</strong>');
  });
});
