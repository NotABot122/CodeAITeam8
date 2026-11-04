import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import {Box, Button, IconButton, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useState} from 'react';

import type {ExplainStep, ItemStep} from './types';

export type Response = string | string[] | Record<string, string> | {text: string} | {skip: true};

// What a child answers with. Taps for choices; up/down buttons for ordering; a box pick for sorting.
export function responseReady(step: ItemStep, value: unknown): boolean {
  if (step.type === 'order') return Array.isArray(value) && value.length === (step.cards?.length ?? 0);
  if (step.type === 'sort') return !!value && Object.keys(value as object).length === (step.cards?.length ?? 0);
  return typeof value === 'string';
}

export function initialResponse(step: ItemStep): unknown {
  return step.type === 'order' ? (step.cards ?? []).map(c => c.id) : step.type === 'sort' ? {} : null;
}

export function ItemView({step, value, onChange, disabled}: {step: ItemStep; value: unknown; onChange: (v: unknown) => void; disabled: boolean}) {
  if (step.type === 'order') {
    const ids = value as string[];
    const text = (id: string) => step.cards!.find(c => c.id === id)?.text ?? id;
    const move = (i: number, d: number) => {
      const next = [...ids];
      [next[i], next[i + d]] = [next[i + d], next[i]];
      onChange(next);
    };
    return (
      <Box component="ol" sx={{listStyle: 'none', p: 0, m: 0, display: 'grid', gap: 1}} aria-label="Put these in order, first at the top">
        {ids.map((id, i) => (
          <Box component="li" key={id} sx={{display: 'flex', alignItems: 'center', gap: 1, p: 1.25, border: 1, borderColor: 'divider', borderRadius: '10px', bgcolor: 'background.paper'}}>
            <Typography sx={{fontWeight: 700, width: 24, color: 'primary.main'}}>{i + 1}</Typography>
            <Typography sx={{flex: 1}}>{text(id)}</Typography>
            <IconButton aria-label={`Move "${text(id)}" up`} disabled={disabled || i === 0} onClick={() => move(i, -1)}><ArrowUpwardIcon /></IconButton>
            <IconButton aria-label={`Move "${text(id)}" down`} disabled={disabled || i === ids.length - 1} onClick={() => move(i, 1)}><ArrowDownwardIcon /></IconButton>
          </Box>
        ))}
      </Box>
    );
  }
  if (step.type === 'sort') {
    const placed = (value ?? {}) as Record<string, string>;
    return (
      <Box sx={{display: 'grid', gap: 1.25}}>
        {step.cards!.map(card => (
          <Box key={card.id} sx={{p: 1.25, border: 1, borderColor: placed[card.id] ? 'primary.main' : 'divider', borderRadius: '10px', bgcolor: 'background.paper'}}>
            <Typography sx={{mb: 1}}>{card.text}</Typography>
            <ToggleButtonGroup exclusive size="small" value={placed[card.id] ?? null} disabled={disabled} aria-label={`Where does "${card.text}" go?`}
              onChange={(_, v) => v && onChange({...placed, [card.id]: v})} sx={{flexWrap: 'wrap'}}>
              {step.buckets!.map(b => <ToggleButton key={b.id} value={b.id} sx={{textTransform: 'none', px: 2}}>{b.text}</ToggleButton>)}
            </ToggleButtonGroup>
          </Box>
        ))}
      </Box>
    );
  }
  return (
    <Box role="radiogroup" aria-label="Answer choices" sx={{display: 'grid', gap: 1}}>
      {step.options!.map(o => {
        const on = value === o.id;
        return (
          <Button key={o.id} role="radio" aria-checked={on} disabled={disabled} onClick={() => onChange(o.id)} variant={on ? 'contained' : 'outlined'} color="primary"
            sx={{justifyContent: 'flex-start', textAlign: 'left', py: 1.5, px: 2, fontSize: 16, fontFamily: step.type === 'trace' ? 'var(--code-font)' : undefined}}>
            {o.text}
          </Button>
        );
      })}
    </Box>
  );
}

export function ExplainView({step, onSend, onSkip, disabled}: {step: ExplainStep; onSend: (text: string) => void; onSkip: () => void; disabled: boolean}) {
  const [text, setText] = useState('');
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      <TextField multiline minRows={3} fullWidth label="Your words" value={text} disabled={disabled} onChange={e => setText(e.target.value)}
        slotProps={{htmlInput: {maxLength: step.max_chars}}} helperText={`${text.length} / ${step.max_chars}`} />
      <Box sx={{display: 'flex', gap: 1}}>
        <Button variant="contained" color="secondary" disabled={disabled || !text.trim()} onClick={() => onSend(text.trim())}>Send</Button>
        {step.can_skip && <Button disabled={disabled} onClick={onSkip}>Skip this one</Button>}
      </Box>
    </Box>
  );
}
