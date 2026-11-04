import {Alert, Box, Button, CircularProgress, Container, Paper, Typography} from '@mui/material';
import {useEffect, useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {ProjectChoices, StudentState} from '@/api/types';

import ProjectPicker from './ProjectPicker';

const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

/** For students who skip the readiness check: pick a project, then start coding. */
export default function ChooseScreen({client, studentId, onStart}: {
  client: ApiClient; studentId: string; onStart: (state: StudentState | null) => void;
}) {
  const [choices, setChoices] = useState<ProjectChoices | null>(null);
  const [state, setState] = useState<StudentState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { client.projectChoices(studentId).then(setChoices).catch(e => setError(msg(e))); }, [client, studentId]);

  const pick = async (project: string) => {
    setBusy(true); setError(null);
    try { const r = await client.chooseProject(studentId, project); setChoices(r); setState(r.state); }
    catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="md" sx={{py: 1.25}}>
          <Typography component="p" variant="h5">CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Pick a project</Typography></Typography>
        </Container>
      </Box>
      <Container maxWidth="md" sx={{py: 3}}>
        <Paper variant="outlined" sx={{p: {xs: 2, sm: 4}, borderRadius: '12px', display: 'grid', gap: 2}}>
          <Typography variant="h4" component="h1">What do you want to build?</Typography>
          <Typography color="text.secondary">Pick the project that sounds most fun. You can change it until you run your code for the first time.</Typography>
          {error && <Alert severity="error">{error}</Alert>}
          {!choices && !error && <Box sx={{display: 'grid', placeItems: 'center', py: 4}}><CircularProgress aria-label="Loading projects" /></Box>}
          {choices && <ProjectPicker choices={choices.choices} locked={choices.locked} busy={busy} onPick={p => void pick(p)} />}
          <Box><Button variant="contained" color="secondary" size="large" disabled={busy || !choices} onClick={() => onStart(state)}>Start coding</Button></Box>
        </Paper>
      </Container>
    </Box>
  );
}
