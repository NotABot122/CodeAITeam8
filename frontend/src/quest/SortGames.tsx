import {Box, Button, Typography} from '@mui/material';
import {useState} from 'react';

import type {ItemStep} from './types';

type Placed = Record<string, string>;
type Props = {step: ItemStep; value: Placed; onChange: (v: Placed) => void; disabled: boolean};

// Game skins for sort questions. Every one still answers {card id: bucket id}, so scoring is unchanged.
// No timers, lives or speed: each has a plain tap path that works with a keyboard or a screen reader.
const CODE = {fontFamily: 'var(--code-font)', whiteSpace: 'pre-wrap' as const};

/** Rows: tap the rows that belong in the first box. Untapped rows go in the last box. */
export function initialRows(step: ItemStep): Placed {
  const skip = step.buckets![step.buckets!.length - 1].id;
  return Object.fromEntries(step.cards!.map(c => [c.id, skip]));
}

export function RowsGame({step, value, onChange, disabled}: Props) {
  const [yes, ...rest] = step.buckets!;
  const no = rest[rest.length - 1];
  return (
    <Box>
      <Typography color="text.secondary" sx={{mb: 1}}>Tap every row that goes in “{yes.text}”. Tap again to take it back.</Typography>
      <Box role="group" aria-label={`Rows. Tapped rows go in ${yes.text}`} sx={{display: 'grid', gap: 0.75}}>
        {step.cards!.map(card => {
          const on = value[card.id] === yes.id;
          return (
            <Button key={card.id} aria-pressed={on} disabled={disabled} onClick={() => onChange({...value, [card.id]: on ? no.id : yes.id})}
              variant={on ? 'contained' : 'outlined'} color="primary"
              sx={{justifyContent: 'space-between', textTransform: 'none', py: 1.1, px: 2, textAlign: 'left', ...CODE}}>
              <span>{card.text}</span>
              <span aria-hidden>{on ? `✓ ${yes.text}` : ''}</span>
            </Button>
          );
        })}
      </Box>
    </Box>
  );
}

/** Belt: cards arrive one at a time; send each through the gate to the left or right lane. */
export function BeltGame({step, value, onChange, disabled}: Props) {
  const [left, right] = step.buckets!;
  const cards = step.cards!;
  const next = cards.find(c => !value[c.id]);
  const lane = (id: string) => cards.filter(c => value[c.id] === id);
  const send = (bucket: string) => next && onChange({...value, [next.id]: bucket});
  const undo = () => {
    const last = [...cards].reverse().find(c => value[c.id]);
    if (last) { const v = {...value}; delete v[last.id]; onChange(v); }
  };
  return (
    <Box onKeyDown={e => {
      if (disabled) return;
      if (e.key === 'ArrowLeft') { e.preventDefault(); send(left.id); }
      if (e.key === 'ArrowRight') { e.preventDefault(); send(right.id); }
    }}>
      <Typography color="text.secondary" sx={{mb: 1}}>Send each card the right way. Use the buttons or the left and right arrow keys. Take your time.</Typography>
      <Box sx={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mb: 1.5}}>
        {[left, right].map(b => (
          <Box key={b.id} aria-label={`${b.text} lane, ${lane(b.id).length} cards`} sx={{minHeight: 96, p: 1, borderRadius: '12px', border: 2, borderStyle: 'dashed', borderColor: 'primary.main', bgcolor: 'rgba(255,201,51,0.12)'}}>
            <Typography sx={{fontWeight: 800, color: 'primary.dark', mb: 0.5}}>{b.text}</Typography>
            {lane(b.id).map(c => <Box key={c.id} sx={{display: 'inline-block', m: 0.25, px: 1, py: 0.25, borderRadius: '8px', bgcolor: 'background.paper', border: 1, borderColor: 'divider', ...CODE}}>{c.text}</Box>)}
          </Box>
        ))}
      </Box>
      <Box aria-live="polite" sx={{textAlign: 'center', mb: 1.5, minHeight: 64}}>
        {next ? (
          <Box sx={{display: 'inline-block', px: 3, py: 1.5, borderRadius: '14px', bgcolor: 'primary.main', color: 'primary.contrastText', fontWeight: 800, fontSize: 22, boxShadow: 3, ...CODE}}>{next.text}</Box>
        ) : <Typography sx={{fontWeight: 700}}>All sorted. Press Check, or undo to change one.</Typography>}
      </Box>
      <Box sx={{display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap'}}>
        <Button variant="contained" disabled={disabled || !next} onClick={() => send(left.id)}>← {left.text}</Button>
        <Button variant="outlined" disabled={disabled || !cards.some(c => value[c.id])} onClick={undo}>Undo</Button>
        <Button variant="contained" disabled={disabled || !next} onClick={() => send(right.id)}>{right.text} →</Button>
      </Box>
    </Box>
  );
}

/** Chips: tap a word chip, then tap the box it belongs in. Tap a placed chip to take it back. */
export function ChipsGame({step, value, onChange, disabled}: Props) {
  const [held, setHeld] = useState<string | null>(null);
  const cards = step.cards!;
  const free = cards.filter(c => !value[c.id]);
  const chip = (id: string, text: string, onClick: () => void, on = false) => (
    <Button key={id} size="small" aria-pressed={on} disabled={disabled} onClick={onClick} variant={on ? 'contained' : 'outlined'} sx={{m: 0.25, textTransform: 'none', borderRadius: '999px', ...CODE}}>{text}</Button>
  );
  const drop = (bucket: string) => {
    if (!held) return;
    onChange({...value, [held]: bucket});
    setHeld(null);
  };
  return (
    <Box>
      <Typography color="text.secondary" sx={{mb: 1}}>Tap a chip, then tap the box where it goes.</Typography>
      <Box role="group" aria-label="Chips to place" sx={{minHeight: 48, mb: 1.5, p: 1, borderRadius: '12px', bgcolor: 'rgba(255,201,51,0.12)'}}>
        {free.length ? free.map(c => chip(c.id, c.text, () => setHeld(held === c.id ? null : c.id), held === c.id)) : <Typography sx={{py: 0.75}}>Every chip is placed.</Typography>}
      </Box>
      <Box sx={{display: 'grid', gap: 1}}>
        {step.buckets!.map(b => (
          <Box key={b.id} sx={{p: 1, borderRadius: '12px', border: 2, borderStyle: 'dashed', borderColor: held ? 'secondary.main' : 'divider'}}>
            <Button disabled={disabled || !held} onClick={() => drop(b.id)} aria-label={`Put ${held ? cards.find(c => c.id === held)?.text : 'the chosen chip'} in ${b.text}`}
              sx={{textTransform: 'none', fontWeight: 800, color: 'primary.dark', p: 0.5}}>{b.text}</Button>
            <Box>{cards.filter(c => value[c.id] === b.id).map(c => chip(c.id, c.text, () => { const v = {...value}; delete v[c.id]; onChange(v); }))}</Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
