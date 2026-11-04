import {Box, Typography} from '@mui/material';
import {useState} from 'react';

import type {CourseView} from '@/api/types';
import {DuckShapes} from './RubberDuck';

type Concept = CourseView['concepts'][number];

/**
 * Honeycomb skill tree: hexagon cells like CodeAI's progression map, joined by glowing paths
 * like a game skill tree. One hex per idea; the colour is the stage, the orange hex with the
 * duck is what the student is working on now. Positions are a layout choice, not engine data.
 */

const DX = 123; // hex-to-hex distance across a row
const DY = 106.5; // row-to-row distance
const R = 54; // hex radius (smaller than the spacing so the paths show between cells)

interface Spot { id: string; x: number; y: number; parents: string[]; icon: string; blurb: string; }

const SPOTS: Spot[] = [
  {id: 'database_retrieval', x: 213, y: 300, parents: [], icon: '🗄️', blurb: 'Ask the database for exactly the rows you need.'},
  {id: 'conditionals', x: 213 + DX / 2, y: 300 - DY, parents: ['database_retrieval'], icon: '🔀', blurb: 'Make the program choose with if and else.'},
  {id: 'loops', x: 213 + DX / 2, y: 300 + DY, parents: ['database_retrieval'], icon: '🔁', blurb: 'Repeat steps for every item without copying code.'},
  {id: 'functions', x: 213 + DX, y: 300, parents: ['conditionals', 'loops'], icon: '🧩', blurb: 'Give steps a name so you can use them again.'},
  {id: 'lists', x: 213 + 2 * DX, y: 300, parents: ['functions'], icon: '📋', blurb: 'Keep many values in order in one place.'},
  {id: 'dictionaries', x: 213 + 2.5 * DX, y: 300 - DY, parents: ['lists'], icon: '📖', blurb: 'Look things up by name with keys and values.'},
];
const START = {x: 90, y: 300};
// ghost cells that make the board look like a honeycomb: "more ideas coming"
const GHOST_SPOTS = [
  {x: 213 + 1.5 * DX, y: 300 - DY}, {x: 213 + 1.5 * DX, y: 300 + DY},
  {x: 213 + 2.5 * DX, y: 300 + DY}, {x: 213 + 3 * DX, y: 300}, {x: 213 + 3.5 * DX, y: 300 - DY},
];

const hex = (x: number, y: number, r = R) =>
  Array.from({length: 6}, (_, k) => `${(x + r * Math.cos(((-90 + 60 * k) * Math.PI) / 180)).toFixed(1)},${(y + r * Math.sin(((-90 + 60 * k) * Math.PI) / 180)).toFixed(1)}`).join(' ');

const FILL = ['#4a4026', '#ffd23f', '#ff6b8a', '#2fd27a']; // Missing, Beginning, Meeting, Exceeding
const INK = ['#d8cfa8', '#2b2200', '#2b0a14', '#0d3b22'];

function labelLines(name: string): string[] {
  const parts = name.split(' ');
  return parts.length > 1 ? parts : [name];
}

export function SkillTreeBoard({concepts, onPick, picked}: {concepts: Concept[]; onPick: (id: string) => void; picked: string}) {
  const byId = new Map(concepts.map(c => [c.id, c]));
  const reached = (id: string) => { const c = byId.get(id); return !!c && (c.stage >= 1 || c.inProject); };
  const open = (s: Spot) => s.parents.every(p => (byId.get(p)?.stage ?? 0) >= 1) ;
  const pos = new Map<string, {x: number; y: number}>(SPOTS.map(s => [s.id, s]));
  const edges: {a: {x: number; y: number}; b: {x: number; y: number}; lit: boolean}[] = [
    {a: START, b: pos.get('database_retrieval')!, lit: reached('database_retrieval')},
  ];
  for (const s of SPOTS) for (const p of s.parents) edges.push({a: pos.get(p)!, b: s, lit: reached(s.id) && (byId.get(p)?.stage ?? 0) >= 1});

  return (
    <Box
      component="svg"
      viewBox="28 92 685 400"
      role="group"
      aria-label="Skill tree: one hexagon for each idea"
      sx={{
        width: '100%', maxHeight: 'calc(100vh - 330px)', minHeight: 220, display: 'block', borderRadius: '16px',
        background: 'radial-gradient(ellipse at 30% 40%, #4a3c12 0%, #17130a 72%)',
        '@keyframes pulse': {'0%': {opacity: 0.9, transform: 'scale(1)'}, '100%': {opacity: 0, transform: 'scale(1.35)'}},
        '@keyframes bob': {'0%,100%': {transform: 'translateY(0)'}, '50%': {transform: 'translateY(-4px)'}},
        '.pulse': {transformBox: 'fill-box', transformOrigin: 'center', animation: 'pulse 1.6s ease-out infinite'},
        '.bob': {animation: 'bob 1.4s ease-in-out infinite'},
        '@media (prefers-reduced-motion: reduce)': {'.pulse, .bob': {animation: 'none'}},
        '.cell:focus-visible polygon.body': {stroke: '#ffffff', strokeWidth: 6},
      }}
    >
      <defs>
        <filter id="glow" filterUnits="userSpaceOnUse" x="0" y="0" width="720" height="600"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>

      {GHOST_SPOTS.map((g, i) => (
        <g key={i} aria-hidden>
          <polygon points={hex(g.x, g.y)} fill="none" stroke="#6d6137" strokeWidth={2} strokeDasharray="6 6" />
          <text x={g.x} y={g.y + 8} textAnchor="middle" fontSize={22} fill="#6d6137" fontWeight={700}>?</text>
        </g>
      ))}

      {edges.map((e, i) => (
        <line key={i} x1={e.a.x} y1={e.a.y} x2={e.b.x} y2={e.b.y} strokeLinecap="round"
          stroke={e.lit ? '#ffe28a' : '#5c5030'} strokeWidth={e.lit ? 7 : 5} filter={e.lit ? 'url(#glow)' : undefined} />
      ))}

      <g aria-hidden>
        <polygon points={hex(START.x, START.y)} fill="#f46800" stroke="#ffffff" strokeWidth={4} strokeLinejoin="round" />
        <text x={START.x} y={START.y - 4} textAnchor="middle" fontSize={26}>⭐</text>
        <text x={START.x} y={START.y + 22} textAnchor="middle" fontSize={13} fontWeight={800} fill="#ffffff">START</text>
      </g>

      {SPOTS.map(s => {
        const c = byId.get(s.id);
        if (!c) return null;
        const isOpen = open(s);
        const locked = c.stage === 0 && !c.inProject && !isOpen;
        const fill = c.stage === 0 ? (c.inProject ? '#f46800' : isOpen ? '#8a6d1f' : FILL[0]) : FILL[c.stage];
        const ink = c.stage === 0 ? (c.inProject || isOpen ? '#ffffff' : INK[0]) : INK[c.stage];
        const state = c.inProject ? 'you are here' : locked ? 'locked' : c.stage === 0 ? 'ready to start' : c.stageName;
        const lines = labelLines(c.name);
        return (
          <g
            key={s.id} className="cell" role="button" tabIndex={0} aria-pressed={picked === s.id}
            aria-label={`${c.name}: ${c.stageName}, ${state}`}
            style={{cursor: 'pointer', outline: 'none'}}
            onClick={() => onPick(s.id)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(s.id); } }}
          >
            {c.inProject && <polygon className="pulse" points={hex(s.x, s.y, R + 4)} fill="none" stroke="#ffd2b0" strokeWidth={5} />}
            {picked === s.id && <polygon points={hex(s.x, s.y, R + 9)} fill="none" stroke="#ffe28a" strokeWidth={3} strokeDasharray="5 4" />}
            <polygon className="body" points={hex(s.x, s.y)} fill={fill} stroke={locked ? '#6d6137' : '#ffffff'} strokeWidth={locked ? 2 : 4} strokeLinejoin="round" />
            <text x={s.x} y={s.y - 12} textAnchor="middle" fontSize={24}>{locked ? '🔒' : s.icon}</text>
            {lines.map((l, i) => (
              <text key={i} x={s.x} y={s.y + 8 + i * 12} textAnchor="middle" fontSize={11} fontWeight={800} fill={ink}>{l}</text>
            ))}
            {[1, 2, 3].map(i => (
              <circle key={i} cx={s.x + (i - 2) * 11} cy={s.y + 8 + lines.length * 12 + 3} r={3.6}
                fill={i <= c.stage ? ink : 'none'} stroke={ink} strokeWidth={1.5} opacity={0.9} />
            ))}
            {c.stage >= 2 && (
              <g transform={`translate(${s.x} ${s.y - R - 8}) rotate(-8)`}>
                <rect x={-34} y={-12} width={68} height={22} rx={11} fill="#f46800" stroke="#ffffff" strokeWidth={2} />
                <text x={0} y={4} textAnchor="middle" fontSize={13} fontWeight={800} fill="#ffffff">Learned!</text>
              </g>
            )}
            {c.inProject && (
              <g transform={`translate(${s.x + R - 14} ${s.y - R - 10}) scale(0.95)`}>
                <g className="bob"><DuckShapes /></g>
              </g>
            )}
          </g>
        );
      })}
    </Box>
  );
}

export default function SkillTree({concepts}: {concepts: Concept[]}) {
  const current = concepts.find(c => c.inProject)?.id ?? SPOTS.find(s => s.parents.every(p => (concepts.find(c => c.id === p)?.stage ?? 0) >= 1) && (concepts.find(c => c.id === s.id)?.stage ?? 0) < 3)?.id ?? SPOTS[0].id;
  const [picked, setPicked] = useState(current);
  const spot = SPOTS.find(s => s.id === picked) ?? SPOTS[0];
  const c = concepts.find(x => x.id === picked);
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      <SkillTreeBoard concepts={concepts} picked={picked} onPick={setPicked} />
      {c && (
        <Box sx={{p: 1.5, borderRadius: '12px', border: 1, borderColor: 'divider', bgcolor: 'background.paper', display: 'flex', gap: 1.5, alignItems: 'center'}} aria-live="polite">
          <Typography component="span" sx={{fontSize: 32}} aria-hidden>{spot.icon}</Typography>
          <Box>
            <Typography sx={{fontWeight: 700}}>{c.name} · {c.inProject ? 'you are working on this now' : c.stageName}</Typography>
            <Typography color="text.secondary">{spot.blurb}</Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
}
