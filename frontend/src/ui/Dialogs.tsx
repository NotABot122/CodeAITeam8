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
        <FitnessCenterIcon color="secondary" /> {p.inserted === 'struggle' ? "Let's practice the idea first" : 'A quick practice first'}
      </DialogTitle>
      <DialogContent>
        {p.inserted === 'struggle' ? (
          <Typography>
            This one's tricky, so let's practice {names || 'the idea'} first: <strong>{p.title}</strong>.
            Then you'll come back to <strong>{p.returnTo?.title ?? 'your level'}</strong>, and your code there will be waiting for you.
          </Typography>
        ) : p.inserted === 'planned' ? (
          <Typography>
            Your readiness check showed {names || 'this idea'} is worth a quick warm-up: <strong>{p.title}</strong>. Pass it and you'll move on to your next level.
          </Typography>
        ) : (
          <Typography>
            Let's strengthen {names || 'this idea'} with a short task: <strong>{p.title}</strong>. Pass it and you'll head straight back to the main path.
          </Typography>
        )}
      </DialogContent>
      <DialogActions><Button variant="contained" autoFocus onClick={onClose}>Let's go</Button></DialogActions>
    </Dialog>
  );
}

/** "Make it yours": the AI builds the same project around a theme the student picks.
 *  `later`: the student is on another step first (a review), so the theme waits until they reach the project.
 *  `done`: the success message after a build that doesn't switch the screen. */
export function ThemeDialog({open, aiOn, aiReason, themed, busy, error, onBuild, onReset, onClose, later = false, done = null}: {
  open: boolean; aiOn: boolean; aiReason: string | null; themed: boolean; busy: boolean; error: string | null;
  onBuild: (request: string) => void; onReset: () => void; onClose: () => void; later?: boolean; done?: string | null;
}) {
  const [text, setText] = useState('');
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} aria-labelledby="theme-title" maxWidth="xs" fullWidth>
      <DialogTitle id="theme-title">Make it yours</DialogTitle>
      <DialogContent>
        {done ? (
          <Alert severity="success">{done}</Alert>
        ) : !aiOn ? (
          <Alert severity="info">Themes need the AI tutor, which is off right now{aiReason ? ` (${aiReason})` : ''}.</Alert>
        ) : (
          <>
            <Typography sx={{mb: 2}}>Tell us what you're into and we'll rebuild the same project around it. Same concepts, your theme.</Typography>
            {later && <Typography variant="body2" color="text.secondary" sx={{mb: 2}}>You'll finish what you're working on first, then start your themed project.</Typography>}
            <TextField autoFocus fullWidth label="I like…" placeholder="soccer, space, music" value={text} disabled={busy}
              slotProps={{htmlInput: {maxLength: 300}}} onChange={e => setText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && text.trim() && !busy) onBuild(text); }} />
            {busy && <Typography role="status" sx={{mt: 2}} color="text.secondary">Building your project. This takes about half a minute…</Typography>}
            {error && <Alert severity="warning" sx={{mt: 2}}>{error}</Alert>}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {themed && !done && <Button disabled={busy} onClick={onReset}>Back to the ready-made projects</Button>}
        <Button disabled={busy} onClick={onClose}>Close</Button>
        {aiOn && !done && <Button variant="contained" disabled={busy || !text.trim()} onClick={() => onBuild(text)}>Build it</Button>}
      </DialogActions>
    </Dialog>
  );
}
