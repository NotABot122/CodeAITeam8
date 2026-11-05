import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import {Box, Button, IconButton, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useState} from 'react';

import {CodeBlock, DataTable} from '@/ui/CodeBlock';
import {InlineText} from '@/ui/markdown';

import {BeltGame, ChipsGame, initialRows, RowsGame} from './SortGames';
import type {ExplainStep, ItemStep} from './types';

export type Response = string | string[] | Record<string, string> | {text: string} | {skip: true};

// What a student answers with. Taps for choices; up/down buttons for ordering; a box pick for sorting.
// Code is never part of a sentence: it comes as a block (step.code), a table (step.table), lines the student
// taps (spot), or options/cards drawn in the code font (option_format 'code', which keeps indentation).
const CODE_LINE = {fontFamily: 'var(--code-font)', whiteSpace: 'pre-wrap' as const};
const isCode = (step: ItemStep) => (step.option_format ?? (step.type === 'choice' || step.type === 'sort' ? 'text' : 'code')) === 'code';
/** Text for screen-reader labels: `code` marks dropped. */
export const plain = (text: string) => text.replace(/`/g, '');

/** What a question shows between its prompt and its answers: a code block and/or a data table. */
export function QuestionBody({step}: {step: ItemStep}) {
  if (!step.code && !step.table) return null;
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      {step.code && <CodeBlock code={step.code.text} lang={step.code.lang} />}
      {step.table && <DataTable columns={step.table.columns} rows={step.table.rows} />}
    </Box>
  );
}

/** A spot question: the program's lines in order, each one a choice. */
function SpotLines({step, value, onChange, disabled}: {step: ItemStep; value: unknown; onChange: (v: unknown) => void; disabled: boolean}) {
  return (
    <Box role="radiogroup" aria-label="Lines of code. Tap the line with the bug." sx={{borderRadius: '10px', border: 1, borderColor: 'divider', overflow: 'hidden'}}>
      {step.options!.map((o, i) => {
        const on = value === o.id;
        return (
          <Box key={o.id} component="button" type="button" role="radio" aria-checked={on} disabled={disabled} onClick={() => onChange(o.id)}
            aria-label={`Line ${i + 1}: ${o.text.trim()}`}
            sx={{display: 'flex', width: '100%', alignItems: 'center', gap: 1.5, px: 1, py: 1, border: 0, borderTop: i ? 1 : 0, borderColor: 'divider',
              bgcolor: on ? 'primary.main' : 'background.paper', color: on ? 'primary.contrastText' : 'text.primary', cursor: disabled ? 'default' : 'pointer',
              textAlign: 'left', fontSize: 15, '&:hover': disabled ? undefined : {bgcolor: on ? 'primary.main' : 'action.hover'},
              '&:focus-visible': {outline: 3, outlineColor: 'secondary.main', outlineOffset: -3}}}>
            <Box component="span" aria-hidden sx={{flex: 'none', width: 28, textAlign: 'right', color: on ? 'inherit' : 'text.disabled', fontFamily: 'var(--code-font)'}}>{i + 1}</Box>
            <Box component="span" sx={{...CODE_LINE, whiteSpace: 'pre'}}>{o.text}</Box>
          </Box>
        );
      })}
    </Box>
  );
}

export function responseReady(step: ItemStep, value: unknown): boolean {
  if (step.type === 'order') return Array.isArray(value) && value.length === (step.cards?.length ?? 0);
  if (step.type === 'sort') return !!value && Object.keys(value as object).length === (step.cards?.length ?? 0);
  return typeof value === 'string';
}

export function initialResponse(step: ItemStep): unknown {
  if (step.type === 'sort' && step.display === 'rows') return initialRows(step);
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
            <Typography sx={{fontWeight: 700, width: 24, color: 'primary.dark'}}>{i + 1}</Typography>
            {isCode(step)
              ? <Typography sx={{flex: 1, ...CODE_LINE}}>{text(id)}</Typography>
              : <Typography sx={{flex: 1}}><InlineText text={text(id)} /></Typography>}
            <IconButton aria-label={`Move "${plain(text(id)).trim()}" up`} disabled={disabled || i === 0} onClick={() => move(i, -1)}><ArrowUpwardIcon /></IconButton>
            <IconButton aria-label={`Move "${plain(text(id)).trim()}" down`} disabled={disabled || i === ids.length - 1} onClick={() => move(i, 1)}><ArrowDownwardIcon /></IconButton>
          </Box>
        ))}
      </Box>
    );
  }
  if (step.type === 'sort' && step.display) {
    const Game = step.display === 'rows' ? RowsGame : step.display === 'belt' ? BeltGame : ChipsGame;
    return <Game step={step} value={(value ?? {}) as Record<string, string>} onChange={onChange} disabled={disabled} />;
  }
  if (step.type === 'sort') {
    const placed = (value ?? {}) as Record<string, string>;
    return (
      <Box sx={{display: 'grid', gap: 1.25}}>
        {step.cards!.map(card => (
          <Box key={card.id} sx={{p: 1.25, border: 1, borderColor: placed[card.id] ? 'primary.main' : 'divider', borderRadius: '10px', bgcolor: 'background.paper'}}>
            <Typography sx={{mb: 1, ...(isCode(step) ? CODE_LINE : {})}}>{isCode(step) ? card.text : <InlineText text={card.text} />}</Typography>
            <ToggleButtonGroup exclusive size="small" value={placed[card.id] ?? null} disabled={disabled} aria-label={`Where does "${plain(card.text)}" go?`}
              onChange={(_, v) => v && onChange({...placed, [card.id]: v})} sx={{flexWrap: 'wrap'}}>
              {step.buckets!.map(b => <ToggleButton key={b.id} value={b.id} sx={{textTransform: 'none', px: 2}}>{b.text}</ToggleButton>)}
            </ToggleButtonGroup>
          </Box>
        ))}
      </Box>
    );
  }
  if (step.type === 'spot') return <SpotLines step={step} value={value} onChange={onChange} disabled={disabled} />;
  const code = isCode(step);
  return (
    <Box role="radiogroup" aria-label="Answer choices" sx={{display: 'grid', gap: 1}}>
      {step.options!.map(o => {
        const on = value === o.id;
        return (
          <Button key={o.id} role="radio" aria-checked={on} disabled={disabled} onClick={() => onChange(o.id)} variant={on ? 'contained' : 'outlined'} color="primary"
            aria-label={code ? undefined : plain(o.text)}
            sx={{justifyContent: 'flex-start', textAlign: 'left', textTransform: 'none', py: 1.5, px: 2, fontSize: code ? 15 : 16,
              ...(code ? {fontFamily: 'var(--code-font)', whiteSpace: 'pre-wrap'} : {})}}>
            {code ? o.text : <span><InlineText text={o.text} /></span>}
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
