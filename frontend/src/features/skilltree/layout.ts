// Rows by dependency depth: a node's row is the length of the longest
// `requires` chain beneath it, so every edge points downward.
//
// Adapted from code-dot-org/code-dot-org
//   apps/src/adaptive/views/map/layout/graph.ts and layout/tree.ts (Apache-2.0).
// Changed: takes our SkillNode instead of their Checkpoint, merges the two
// files, and exports the board size as part of the layout.

import type {SkillNode} from '@/api/types';

export const BOARD_WIDTH = 760;
export const NODE_RADIUS = 30;
export const LABEL_HEIGHT = 40;
const ROW_HEIGHT = 170;
const TOP_MARGIN = 96;
const BOTTOM_MARGIN = 60;

export interface Edge {
  from: string;
  to: string;
}

export interface NodePosition {
  id: string;
  row: number;
  x: number;
  y: number;
}

export interface TreeLayout {
  nodes: {[id: string]: NodePosition};
  edges: Edge[];
  width: number;
  height: number;
}

/** One edge per known `requires`, parent to child. */
export function edgesOf(nodes: SkillNode[]): Edge[] {
  const ids = new Set(nodes.map(n => n.id));
  const edges: Edge[] = [];
  for (const node of nodes) {
    for (const parent of node.requires) {
      if (ids.has(parent)) edges.push({from: parent, to: node.id});
    }
  }
  return edges;
}

/**
 * Node ids grouped by depth. Unknown parents are ignored and a cycle is cut
 * rather than followed, so a bad payload still draws.
 */
export function depthRows(nodes: SkillNode[]): string[][] {
  const byId = new Map(nodes.map(n => [n.id, n]));
  const rowOf = new Map<string, number>();

  const rowFor = (id: string, path: Set<string>): number => {
    const known = rowOf.get(id);
    if (known !== undefined) return known;
    const parents = (byId.get(id)?.requires ?? []).filter(
      p => byId.has(p) && !path.has(p)
    );
    const row = parents.length
      ? 1 + Math.max(...parents.map(p => rowFor(p, new Set(path).add(id))))
      : 0;
    rowOf.set(id, row);
    return row;
  };
  nodes.forEach(n => rowFor(n.id, new Set([n.id])));

  const rows: string[][] = [];
  for (const node of nodes) {
    const row = rowOf.get(node.id) ?? 0;
    (rows[row] ||= []).push(node.id);
  }
  return rows;
}

export function layoutNodes(nodes: SkillNode[]): TreeLayout {
  const rows = depthRows(nodes);
  const positions: {[id: string]: NodePosition} = {};
  rows.forEach((ids, row) => {
    ids.forEach((id, i) => {
      positions[id] = {
        id,
        row,
        x: Math.round((BOARD_WIDTH * (i + 1)) / (ids.length + 1)),
        y: TOP_MARGIN + row * ROW_HEIGHT,
      };
    });
  });
  return {
    nodes: positions,
    edges: edgesOf(nodes),
    width: BOARD_WIDTH,
    height: TOP_MARGIN + (rows.length - 1) * ROW_HEIGHT + BOTTOM_MARGIN,
  };
}
