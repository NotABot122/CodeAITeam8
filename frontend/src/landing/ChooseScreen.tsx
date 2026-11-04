import {Alert, Box, Button, CircularProgress, Container, Paper, Typography} from '@mui/material';
import {useEffect, useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {ProjectChoices, StudentState} from '@/api/types';

import {ThemeDialog} from '@/ui/Dialogs';

import ProjectPicker from './ProjectPicker';

const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

/** For students who skip the readiness check: pick a project, then start coding. */
export default function ChooseScreen({client, studentId, aiOn, aiReason, onStart}: {
  client: ApiClient; studentId: string; aiOn: boolean; aiReason: string | null; onStart: (state: StudentState | null) => void;
}) {
  const [themeOpen, setThemeOpen] = useState(false);
  const [themeBusy, setThemeBusy] = useState(false);
  const [themeError, setThemeError] = useState<string | null>(null);
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

  // "Make it yours": the AI builds this project around the student's theme, and it becomes their project.
  const build = async (request: string) => {
    setThemeBusy(true); setThemeError(null);
    try {
      const r = await client.buildTheme(studentId, request);
      if (!r.built) { setThemeError(r.message); return; }
      setState(r.state); setChoices(await client.projectChoices(studentId)); setThemeOpen(false);
    } catch (e) { setThemeError(msg(e)); } finally { setThemeBusy(false); }
  };
  const reset = async () => {
    setThemeBusy(true);
    try { setState(await client.resetTheme(studentId)); setChoices(await client.projectChoices(studentId)); setThemeOpen(false); }
    catch (e) { setThemeError(msg(e)); } finally { setThemeBusy(false); }
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
          {choices && <ProjectPicker choices={choices.choices} locked={choices.locked} busy={busy || themeBusy} onPick={p => void pick(p)}
            onCustom={() => { setThemeError(null); setThemeOpen(true); }} />}
          <Box><Button variant="contained" color="secondary" size="large" disabled={busy || !choices} onClick={() => onStart(state)}>Start coding</Button></Box>
        </Paper>
      </Container>
      <ThemeDialog open={themeOpen} aiOn={aiOn} aiReason={aiReason} themed={!!choices?.choices.some(c => c.custom && c.current)}
        busy={themeBusy} error={themeError} onBuild={r => void build(r)} onReset={() => void reset()} onClose={() => setThemeOpen(false)} />
    </Box>
  );
}
