// The student's skill tree. Layout logic is adapted from Code.org's adaptive
// map (see layout.ts); the rendering, category handling and detail panel are
// our own.

import CheckIcon from '@mui/icons-material/Check';
import LockIcon from '@mui/icons-material/Lock';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {
  Box,
  ButtonBase,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import {useMemo, useState} from 'react';

import type {NodeState, SkillNode, SkillTree as SkillTreeData} from '@/api/types';

import {
  LABEL_HEIGHT,
  NODE_RADIUS,
  layoutNodes,
  type TreeLayout,
} from './layout';

// Fixed order, so a category keeps its color as the tree changes.
const CATEGORY_COLORS = ['#1565c0', '#ef6c00', '#2e7d32', '#6a1b9a', '#c62828'];
const NODE_WIDTH = 190;

const STATE_LABEL: {[state in NodeState]: string} = {
  LOCKED: 'locked',
  AVAILABLE: 'available',
  MASTERED: 'mastered',
};

function categoryColor(tree: SkillTreeData, categoryId: string): string {
  const index = tree.categories.findIndex(c => c.id === categoryId);
  return CATEGORY_COLORS[Math.max(index, 0) % CATEGORY_COLORS.length];
}

function StateIcon({state}: {state: NodeState}) {
  if (state === 'MASTERED') return <CheckIcon />;
  if (state === 'AVAILABLE') return <PlayArrowIcon />;
  return <LockIcon />;
}

interface EdgesProps {
  layout: TreeLayout;
  nodesById: Map<string, SkillNode>;
}

function Edges({layout, nodesById}: EdgesProps) {
  return (
    <svg
      width={layout.width}
      height={layout.height}
      style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}
      aria-hidden="true"
    >
      {layout.edges.map(edge => {
        const a = layout.nodes[edge.from];
        const b = layout.nodes[edge.to];
        const y1 = a.y + NODE_RADIUS;
        const y2 = b.y - NODE_RADIUS - LABEL_HEIGHT;
        const mid = (y1 + y2) / 2;
        const done = nodesById.get(edge.from)?.state === 'MASTERED';
        return (
          <path
            key={`${edge.from}-${edge.to}`}
            d={`M ${a.x} ${y1} C ${a.x} ${mid}, ${b.x} ${mid}, ${b.x} ${y2}`}
            fill="none"
            stroke={done ? '#2e7d32' : '#9e9e9e'}
            strokeWidth={2}
            strokeDasharray={done ? undefined : '6 5'}
          />
        );
      })}
    </svg>
  );
}

interface NodeButtonProps {
  node: SkillNode;
  tree: SkillTreeData;
  x: number;
  y: number;
  selected: boolean;
  dimmed: boolean;
  onSelect: (id: string) => void;
}

function NodeButton({node, tree, x, y, selected, dimmed, onSelect}: NodeButtonProps) {
  const primary = categoryColor(tree, node.categories[0]);
  const filled = node.state === 'MASTERED';
  const locked = node.state === 'LOCKED';
  return (
    <Box
      sx={{
        position: 'absolute',
        left: x - NODE_WIDTH / 2,
        top: y - NODE_RADIUS - LABEL_HEIGHT,
        width: NODE_WIDTH,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        opacity: dimmed ? 0.3 : 1,
        transition: 'opacity 150ms',
      }}
    >
      <Typography
        variant="subtitle2"
        sx={{height: LABEL_HEIGHT, display: 'flex', alignItems: 'flex-end', pb: 0.5}}
      >
        {node.title}
      </Typography>
      <ButtonBase
        onClick={() => onSelect(node.id)}
        aria-label={`${node.title}: ${STATE_LABEL[node.state]}`}
        aria-pressed={selected}
        sx={{
          width: NODE_RADIUS * 2,
          height: NODE_RADIUS * 2,
          borderRadius: '50%',
          border: `3px solid ${locked ? '#9e9e9e' : primary}`,
          bgcolor: filled ? primary : 'background.paper',
          color: filled ? '#fff' : locked ? '#9e9e9e' : primary,
          outline: selected ? `3px solid ${primary}55` : 'none',
          outlineOffset: 3,
        }}
      >
        <StateIcon state={node.state} />
      </ButtonBase>
      {/* One dot per category: a poly-hierarchy node shows two or more. */}
      <Stack direction="row" spacing={0.5} sx={{mt: 0.75}} aria-hidden="true">
        {node.categories.map(categoryId => (
          <Box
            key={categoryId}
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: categoryColor(tree, categoryId),
            }}
          />
        ))}
      </Stack>
    </Box>
  );
}

const MASTERY_ROWS = [
  ['conceptual', 'Concepts'],
  ['syntax', 'Syntax'],
  ['problemSolving', 'Problem solving'],
] as const;

function NodeDetail({node, tree}: {node: SkillNode; tree: SkillTreeData}) {
  const titles = new Map(tree.categories.map(c => [c.id, c.title]));
  return (
    <Paper variant="outlined" sx={{p: 2, minWidth: 260}}>
      <Typography variant="h6">{node.title}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{mb: 1.5}}>
        {node.description}
      </Typography>
      <Stack direction="row" spacing={0.5} useFlexGap sx={{flexWrap: 'wrap', mb: 2}}>
        {node.categories.map(id => (
          <Chip
            key={id}
            size="small"
            label={titles.get(id) ?? id}
            sx={{bgcolor: categoryColor(tree, id), color: '#fff'}}
          />
        ))}
      </Stack>
      <Typography variant="caption" color="text.secondary">
        Status: {STATE_LABEL[node.state]}
      </Typography>
      {MASTERY_ROWS.map(([key, label]) => (
        <Box key={key} sx={{mt: 1}}>
          <Typography variant="caption">
            {label}: {Math.round(node.mastery[key] * 100)}%
          </Typography>
          <LinearProgress
            variant="determinate"
            value={node.mastery[key] * 100}
            aria-label={`${label} mastery`}
          />
        </Box>
      ))}
    </Paper>
  );
}

interface SkillTreeProps {
  tree: SkillTreeData;
}

export default function SkillTree({tree}: SkillTreeProps) {
  const [selectedId, setSelectedId] = useState<string>();
  const [activeCategory, setActiveCategory] = useState<string>();
  const layout = useMemo(() => layoutNodes(tree.nodes), [tree.nodes]);
  const nodesById = useMemo(
    () => new Map(tree.nodes.map(n => [n.id, n])),
    [tree.nodes]
  );
  const selected = selectedId ? nodesById.get(selectedId) : undefined;

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} useFlexGap sx={{flexWrap: 'wrap'}}>
        {tree.categories.map(category => {
          const active = activeCategory === category.id;
          return (
            <Chip
              key={category.id}
              label={category.title}
              onClick={() => setActiveCategory(active ? undefined : category.id)}
              variant={active ? 'filled' : 'outlined'}
              sx={{
                borderColor: categoryColor(tree, category.id),
                bgcolor: active ? categoryColor(tree, category.id) : undefined,
                color: active ? '#fff' : undefined,
              }}
            />
          );
        })}
      </Stack>
      <Stack direction={{xs: 'column', md: 'row'}} spacing={3} sx={{alignItems: 'flex-start'}}>
        <Box sx={{overflowX: 'auto', maxWidth: '100%'}}>
          <Box sx={{position: 'relative', width: layout.width, height: layout.height}}>
            <Edges layout={layout} nodesById={nodesById} />
            {tree.nodes.map(node => (
              <NodeButton
                key={node.id}
                node={node}
                tree={tree}
                x={layout.nodes[node.id].x}
                y={layout.nodes[node.id].y}
                selected={node.id === selectedId}
                dimmed={!!activeCategory && !node.categories.includes(activeCategory)}
                onSelect={setSelectedId}
              />
            ))}
          </Box>
        </Box>
        {selected ? (
          <NodeDetail node={selected} tree={tree} />
        ) : (
          <Typography variant="body2" color="text.secondary">
            Select a skill to see its mastery.
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}
