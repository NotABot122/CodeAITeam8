import FitnessCenterIcon from '@mui/icons-material/FitnessCenter';
import {Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography} from '@mui/material';
import {useState} from 'react';

import type {StudentState} from '@/api/types';

export function PracticeDialog({state, onClose}: {state: StudentState; onClose: () => void}) {
  const p = state.problem;
  if (!p) return null;
  const names = state.concepts.filter(c => p.concepts.includes(c.id)).map(c => c.name).join(', ');
  return (
    <Dialog open onClose={onClose} aria-labelledby="practice-title" maxWidth="xs" fullWidth>
      <DialogTitle id="practice-title" sx={{display: 'flex', gap: 1, alignItems: 'center'}}>
        <FitnessCenterIcon color="secondary" /> A quick practice first
      </DialogTitle>
      <DialogContent>
        <Typography>
          Let's strengthen {names || 'this idea'} with a short task: <strong>{p.title}</strong>. Pass it and you'll head straight back to the main path.
        </Typography>
      </DialogContent>
      <DialogActions><Button variant="contained" autoFocus onClick={onClose}>Let's go</Button></DialogActions>
    </Dialog>
  );
}

export function ThemeDialog({open, aiOn, aiReason, themed, busy, error, onBuild, onReset, onClose}: {
  open: boolean; aiOn: boolean; aiReason: string | null; themed: boolean; busy: boolean; error: string | null;
  onBuild: (request: string) => void; onReset: () => void; onClose: () => void;
}) {
  const [text, setText] = useState('');
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} aria-labelledby="theme-title" maxWidth="xs" fullWidth>
      <DialogTitle id="theme-title">Make it yours</DialogTitle>
      <DialogContent>
        {!aiOn ? (
          <Alert severity="info">Themes need the AI tutor, which is off right now{aiReason ? ` (${aiReason})` : ''}.</Alert>
        ) : (
          <>
            <Typography sx={{mb: 2}}>Tell us what you're into and we'll rebuild the same project around it. Same concepts, your theme.</Typography>
            <TextField autoFocus fullWidth label="I like…" placeholder="pokemon, soccer, space" value={text} disabled={busy}
              slotProps={{htmlInput: {maxLength: 300}}} onChange={e => setText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && text.trim() && !busy) onBuild(text); }} />
            {busy && <Typography role="status" sx={{mt: 2}} color="text.secondary">Building your project. This takes about half a minute…</Typography>}
            {error && <Alert severity="warning" sx={{mt: 2}}>{error}</Alert>}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {themed && <Button disabled={busy} onClick={onReset}>Back to Weather Station</Button>}
        <Button disabled={busy} onClick={onClose}>Close</Button>
        {aiOn && <Button variant="contained" disabled={busy || !text.trim()} onClick={() => onBuild(text)}>Build it</Button>}
      </DialogActions>
    </Dialog>
  );
}
