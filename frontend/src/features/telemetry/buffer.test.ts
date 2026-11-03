import {describe, expect, it} from 'vitest';

import type {TelemetryEvent} from '@/api/types';

import {BurstAggregator, TelemetryBuffer} from './buffer';

const run = (ok = true): TelemetryEvent => ({type: 'run', at: 't', ok});

describe('TelemetryBuffer', () => {
  it('reports a full batch', () => {
    const buffer = new TelemetryBuffer(2);
    expect(buffer.add(run())).toBe(false);
    expect(buffer.add(run())).toBe(true);
  });

  it('drains oldest first and empties itself', () => {
    const buffer = new TelemetryBuffer(10);
    buffer.add(run(true));
    buffer.add(run(false));
    expect(buffer.drain().map(e => e.type === 'run' && e.ok)).toEqual([true, false]);
    expect(buffer.size).toBe(0);
  });

  it('restores failed events ahead of newer ones', () => {
    const buffer = new TelemetryBuffer(10);
    buffer.add(run(false));
    buffer.restore([run(true)]);
    expect(buffer.drain().map(e => e.type === 'run' && e.ok)).toEqual([true, false]);
  });

  it('drops the oldest events past its hold limit', () => {
    const buffer = new TelemetryBuffer(10_000);
    for (let i = 0; i < 600; i++) buffer.add(run());
    expect(buffer.size).toBe(500);
  });
});

describe('BurstAggregator', () => {
  it('keeps keystrokes within the gap in one burst', () => {
    const agg = new BurstAggregator(1000);
    expect(agg.keystroke(0)).toBeUndefined();
    expect(agg.keystroke(500)).toBeUndefined();
    const burst = agg.close();
    expect(burst).toMatchObject({type: 'typing_burst', keystrokes: 2, durationMs: 500});
  });

  it('closes a burst when the gap is exceeded', () => {
    const agg = new BurstAggregator(1000);
    agg.keystroke(0);
    agg.keystroke(200);
    const finished = agg.keystroke(5000);
    expect(finished).toMatchObject({keystrokes: 2, durationMs: 200});
    expect(agg.close()).toMatchObject({keystrokes: 1});
  });

  it('returns nothing when no keys were pressed', () => {
    expect(new BurstAggregator().close()).toBeUndefined();
  });

  it('never carries typed text', () => {
    const agg = new BurstAggregator();
    agg.keystroke(0);
    expect(Object.keys(agg.close() ?? {}).sort()).toEqual(
      ['at', 'durationMs', 'keystrokes', 'type']
    );
  });
});
