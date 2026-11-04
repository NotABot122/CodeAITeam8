import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {initialResponse, ItemView, responseReady} from './StepView';
import type {ItemStep} from './types';

const base: Omit<ItemStep, "display"> = {
  kind: 'item', id: 'x', type: 'sort', prompt: 'p',
  cards: [{id: 'a', text: 'ST-A 01'}, {id: 'b', text: 'ST-B 02'}, {id: 'c', text: 'ST-A 03'}],
  buckets: [{id: 'keep', text: 'Returned'}, {id: 'skip', text: 'Not returned'}],
};

describe('game-style sort questions', () => {
  it('rows start fully answered with every row in the last box', () => {
    const step = {...base, display: 'rows' as const};
    const v = initialResponse(step) as Record<string, string>;
    expect(Object.values(v)).toEqual(['skip', 'skip', 'skip']);
    expect(responseReady(step, v)).toBe(true);
    expect(renderToString(<ItemView step={step} value={v} onChange={() => {}} disabled={false} />)).toContain('aria-pressed="false"');
  });
  it('belt shows the next card and needs every card sent', () => {
    const step = {...base, display: 'belt' as const};
    const html = renderToString(<ItemView step={step} value={{a: 'keep'}} onChange={() => {}} disabled={false} />);
    expect(html).toContain('ST-B 02');
    expect(responseReady(step, {a: 'keep'})).toBe(false);
  });
  it('chips list unplaced chips and the boxes', () => {
    const step = {...base, display: 'chips' as const};
    const html = renderToString(<ItemView step={step} value={{}} onChange={() => {}} disabled={false} />);
    expect(html).toContain('Not returned');
    expect(html).toContain('ST-A 03');
  });
});
