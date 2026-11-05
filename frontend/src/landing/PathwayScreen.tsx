import AltRouteIcon from '@mui/icons-material/AltRoute';
import CheckIcon from '@mui/icons-material/Check';
import {Alert, Box, Button, Chip, CircularProgress, Container, Paper, Typography} from '@mui/material';
import {useEffect, useRef, useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {PathwayView, ProjectChoices, StudentState} from '@/api/types';

import {GRADES} from './Landing';
import {ThemeDialog} from '@/ui/Dialogs';

import MatchCard from './MatchCard';
import ProjectPicker from './ProjectPicker';

const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

/** After the readiness check: ask the Strands Decider 2B for a pathway, show it, then start it. */
export default function PathwayScreen({client, studentId, grade: initialGrade, existing, aiOn, aiReason, onGrade, onStart}: {
  client: ApiClient; studentId: string; grade: number | null; existing: PathwayView | null; aiOn: boolean; aiReason: string | null;
  onGrade: (g: number) => void; onStart: (state: StudentState | null) => void;
}) {
  const [grade, setGrade] = useState<number | null>(existing?.grade ?? initialGrade);
  const [pathway, setPathway] = useState<PathwayView | null>(existing);
  const [state, setState] = useState<StudentState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [choices, setChoices] = useState<ProjectChoices | null>(null);
  const [picking, setPicking] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [themeError, setThemeError] = useState<string | null>(null);
  const [themeDone, setThemeDone] = useState<string | null>(null);
  const asked = useRef(false);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const decide = async (g: number) => {
    asked.current = true;
    setBusy(true); setError(null);
    try {
      const r = await client.pathway(studentId, g);
      setPathway(r.pathway); setState(r.state);
    } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  // With the grade already known (picked on the landing page), ask once on arrival.
  useEffect(() => {
    if (!pathway && grade !== null && !asked.current) void decide(grade);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { headingRef.current?.focus(); }, [pathway?.id]);

  // The project choice opens once the pathway is known (the readiness check's goal suggests one).
  useEffect(() => {
    if (!pathway || choices) return;
    client.projectChoices(studentId).then(setChoices).catch(() => setChoices(null));
  }, [client, studentId, pathway, choices]);

  // "Make it yours" from the picker: the theme becomes the pathway's project (now, or after a review step).
  const build = async (request: string) => {
    setPicking(true); setThemeError(null);
    try {
      const r = await client.buildTheme(studentId, request);
      if (!r.built) { setThemeError(r.message); return; }
      setState(r.state); if (r.state.pathway) setPathway(r.state.pathway);
      setChoices(await client.projectChoices(studentId)); setThemeDone(r.message);
    } catch (e) { setThemeError(msg(e)); } finally { setPicking(false); }
  };
  const reset = async () => {
    setPicking(true);
    try {
      const s = await client.resetTheme(studentId); setState(s); if (s.pathway) setPathway(s.pathway);
      setChoices(await client.projectChoices(studentId)); setThemeOpen(false);
    } catch (e) { setThemeError(msg(e)); } finally { setPicking(false); }
  };

  const pick = async (project: string) => {
    setPicking(true); setError(null);
    try {
      const r = await client.chooseProject(studentId, project);
      setChoices(r); setState(r.state);
      if (r.state.pathway) setPathway(r.state.pathway);
    } catch (e) { setError(msg(e)); } finally { setPicking(false); }
  };

  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="md" sx={{py: 1.25}}>
          <Typography component="p" variant="h5">CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Your pathway</Typography></Typography>
        </Container>
      </Box>
      <Container maxWidth="md" sx={{py: 3, display: 'grid', gap: 2}}>
        {error && (
          <Alert severity="error" action={grade !== null ? <Button color="inherit" onClick={() => void decide(grade)}>Try again</Button> : undefined}>{error}</Alert>
        )}

        {!pathway && grade === null && (
          <Paper variant="outlined" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px', display: 'grid', gap: 2}}>
            <Typography variant="h5" component="h1" id="grade-q">What grade are you in?</Typography>
            <Typography color="text.secondary">Your grade helps us match your pathway to the standards for your grade.</Typography>
            <Box role="radiogroup" aria-labelledby="grade-q" sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
              {GRADES.map(g => (
                <Button key={g} role="radio" aria-checked={false} variant="outlined" sx={{minWidth: 88}}
                  onClick={() => { setGrade(g); onGrade(g); void decide(g); }}>Grade {g}</Button>
              ))}
            </Box>
          </Paper>
        )}

        {!pathway && grade !== null && busy && (
          <Paper variant="outlined" role="status" aria-live="polite" sx={{p: 4, borderRadius: '12px', display: 'grid', gap: 2, justifyItems: 'center', textAlign: 'center'}}>
            <CircularProgress aria-hidden />
            <Typography variant="h6" component="h1">Your AI guide is choosing your pathway…</Typography>
            <Typography color="text.secondary">It's looking at your answers, your grade and the CS standards for grade {grade}.</Typography>
          </Paper>
        )}

        {pathway && (
          <Paper variant="outlined" sx={{p: {xs: 2, sm: 4}, borderRadius: '12px', display: 'grid', gap: 2.5}}>
            <Box sx={{display: 'flex', gap: 1.5, alignItems: 'center'}}>
              <AltRouteIcon color="secondary" aria-hidden />
              <Typography variant="overline" color="secondary" sx={{fontWeight: 700}}>Your pathway</Typography>
            </Box>
            <Typography ref={headingRef} tabIndex={-1} variant="h4" component="h1" sx={{outline: 0, mt: -1.5}}>{pathway.title}</Typography>
            <Typography sx={{fontSize: 18}}>{pathway.message}</Typography>

            <Box>
              <Typography sx={{fontWeight: 700, mb: 1}}>What you'll do</Typography>
              <Box component="ol" sx={{listStyle: 'none', p: 0, m: 0, display: 'grid', gap: 1}}>
                {pathway.steps.map((s, i) => (
                  <Box component="li" key={i} sx={{display: 'flex', gap: 1.5, alignItems: 'center', p: 1.25, border: 1, borderRadius: '10px',
                    borderColor: s.status === 'current' ? 'primary.main' : 'divider', bgcolor: 'background.paper'}}>
                    <Box aria-hidden sx={{width: 28, height: 28, borderRadius: '50%', display: 'grid', placeItems: 'center', fontWeight: 700, flex: 'none',
                      bgcolor: s.status === 'done' ? 'success.main' : s.status === 'current' ? 'primary.main' : 'action.hover',
                      color: s.status === 'todo' ? 'text.secondary' : '#fff'}}>
                      {s.status === 'done' ? <CheckIcon sx={{fontSize: 16}} /> : i + 1}
                    </Box>
                    <Typography sx={{fontWeight: s.status === 'current' ? 700 : 400}}>{s.title}</Typography>
                    {s.status === 'current' && <Chip label="First" size="small" color="primary" sx={{ml: 'auto'}} />}
                  </Box>
                ))}
              </Box>
            </Box>

            {choices?.match && <MatchCard match={choices.match} heading="Suggested for you" />}
            {choices?.match?.themeIdea && aiOn && (
              <Typography color="text.secondary">
                None of the ready-made stories is about “{choices.match.themeIdea}”. Use Make it yours below to build one that is.
              </Typography>
            )}
            {choices && choices.choices.length > 1 && (
              <Box>
                <Typography sx={{fontWeight: 700, mb: 1}}>Pick your project</Typography>
                <ProjectPicker choices={choices.choices} locked={choices.locked} busy={picking} onPick={p => void pick(p)}
                  onCustom={() => { setThemeError(null); setThemeDone(null); setThemeOpen(true); }} />
              </Box>
            )}

            {pathway.standards.length > 0 && (
              <Box>
                <Typography sx={{fontWeight: 700, mb: 1}}>Skills from the CS standards you'll work on</Typography>
                <Box component="ul" sx={{display: 'flex', gap: 1, flexWrap: 'wrap', listStyle: 'none', p: 0, m: 0}}>
                  {pathway.standards.map(s => <Chip component="li" key={s.id} label={s.skill} title={s.id} variant="outlined" />)}
                </Box>
              </Box>
            )}

            <Typography variant="body2" color="text.secondary">
              {pathway.decidedBy === 'ai'
                ? 'Picked by your AI guide from your answers, your grade and the CS standards for your grade.'
                : 'Picked from your readiness check answers.'}
            </Typography>
            <Box><Button variant="contained" color="secondary" size="large" disabled={picking} onClick={() => onStart(state)}>Start my pathway</Button></Box>
          </Paper>
        )}
      </Container>
      <ThemeDialog open={themeOpen} aiOn={aiOn} aiReason={aiReason} themed={!!choices?.choices.some(c => c.custom && c.current)}
        busy={picking} error={themeError} done={themeDone} onBuild={r => void build(r)} onReset={() => void reset()}
        onClose={() => setThemeOpen(false)} />
    </Box>
  );
}
