import {describe, expect, it} from 'vitest';

import {MOCK_SKILL_TREE} from '@/api/mock/data';
import type {SkillNode} from '@/api/types';

import {depthRows, edgesOf, layoutNodes} from './layout';

const node = (id: string, requires: string[] = []): SkillNode => ({
  id,
  title: id,
  description: '',
  categories: ['c'],
  requires,
  state: 'LOCKED',
  mastery: {conceptual: 0, syntax: 0, problemSolving: 0},
});

describe('depthRows', () => {
  it('puts a node one row below its deepest parent', () => {
    const rows = depthRows([node('a'), node('b', ['a']), node('c', ['a', 'b'])]);
    expect(rows).toEqual([['a'], ['b'], ['c']]);
  });

  it('places the two-parent While Loops node under both parents', () => {
    const rows = depthRows(MOCK_SKILL_TREE.nodes);
    const rowOf = (id: string) => rows.findIndex(r => r.includes(id));
    expect(rowOf('while-loops')).toBeGreaterThan(rowOf('if-statements'));
    expect(rowOf('while-loops')).toBeGreaterThan(rowOf('for-loops'));
  });

  it('ignores unknown parents', () => {
    expect(depthRows([node('a', ['missing'])])).toEqual([['a']]);
  });

  it('cuts a cycle instead of looping', () => {
    const rows = depthRows([node('a', ['b']), node('b', ['a'])]);
    expect(rows.flat().sort()).toEqual(['a', 'b']);
  });
});

describe('edgesOf', () => {
  it('has one edge per known parent', () => {
    const edges = edgesOf([node('a'), node('b', ['a', 'missing'])]);
    expect(edges).toEqual([{from: 'a', to: 'b'}]);
  });
});

describe('layoutNodes', () => {
  it('positions every node and points every edge downward', () => {
    const layout = layoutNodes(MOCK_SKILL_TREE.nodes);
    for (const n of MOCK_SKILL_TREE.nodes) expect(layout.nodes[n.id]).toBeDefined();
    for (const edge of layout.edges) {
      expect(layout.nodes[edge.to].y).toBeGreaterThan(layout.nodes[edge.from].y);
    }
  });
});
