import {Alert, Box, Button, Paper, TextField, Typography} from '@mui/material';
import {useState} from 'react';

import type {NextStep, StudentState} from '@/api/types';
import ConceptMeters from './ConceptMeters';

export default function NextStepPanel({state, busy, error, onPick, onRestart}: {
  state: StudentState; busy: boolean; error: string | null;
  onPick: (index: number, theme?: string) => void; onRestart: () => void;
}) {
  const step: NextStep | null = state.nextStep;
  const [theme, setTheme] = useState('');
  return (
    <Paper variant="outlined" sx={{p: {xs: 2, sm: 4}, mt: 2, borderRadius: '12px'}}>
      <Typography variant="h4" component="h2" sx={{textAlign: 'center'}}>You finished {state.project.title}!</Typography>
      {step && <Typography sx={{my: 2, textAlign: 'center', fontSize: 18}}>{step.reason}</Typography>}
      <Box sx={{display: 'grid', gap: 1.5, maxWidth: 520, mx: 'auto', mt: 2}}>
        {step?.options.map((o, i) => (
          o.kind === 'all_done' ? (
            <Alert key={i} severity="success">{o.label}</Alert>
          ) : (
            <Box key={i} sx={{display: 'grid', gap: 1}}>
              {o.kind === 'new_theme' && (
                <TextField size="small" label="Your theme" placeholder="pokemon, soccer, space" value={theme} disabled={busy}
                  slotProps={{htmlInput: {maxLength: 300}}} onChange={e => setTheme(e.target.value)} />
              )}
              <Button variant={i === 0 ? 'contained' : 'outlined'} size="large" disabled={busy || (o.kind === 'new_theme' && !theme.trim())}
                onClick={() => onPick(i, o.kind === 'new_theme' ? theme : undefined)}>
                {o.label}{i === 0 && ' (recommended)'}
              </Button>
            </Box>
          )
        ))}
        {busy && <Typography role="status" color="text.secondary" sx={{textAlign: 'center'}}>Setting that up…</Typography>}
        {error && <Alert severity="warning">{error}</Alert>}
      </Box>
      <Box sx={{maxWidth: 760, mx: 'auto', mt: 4}}><ConceptMeters state={state} highlight={[]} row /></Box>
      <Box sx={{textAlign: 'center', mt: 3}}><Button onClick={onRestart}>Start over as a new student</Button></Box>
    </Paper>
  );
}
