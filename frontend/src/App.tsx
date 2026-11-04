import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {Alert, Box, Button, CircularProgress, Container, Paper, Typography} from '@mui/material';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {ApiError, createHttpClient, type ApiClient} from '@/api/client';
import type {Health, Outcome, StudentState} from '@/api/types';

import ConceptMeters from './ui/ConceptMeters';
import CodeEditor from './ui/CodeEditor';
import {PracticeDialog, ThemeDialog} from './ui/Dialogs';
import {Markdown} from './ui/markdown';
import PathStrip from './ui/PathStrip';
import Results from './ui/Results';

const KEY = 'codeai.studentId';
const store = {
  get: () => { try { return localStorage.getItem(KEY); } catch { return null; } },
  set: (v: string) => { try { localStorage.setItem(KEY, v); } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(KEY); } catch { /* private mode */ } },
};
const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

export default function App({client: injected}: {client?: ApiClient}) {
  const client = useMemo(() => injected ?? createHttpClient(import.meta.env.VITE_API_BASE_URL ?? ''), [injected]);
  const [state, setState] = useState<StudentState | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [code, setCode] = useState('');
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [practiceShown, setPracticeShown] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [themeBusy, setThemeBusy] = useState(false);
  const [themeError, setThemeError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const adopt = useCallback((s: StudentState, keepCode = false) => {
    setState(s);
    if (!keepCode) setCode(s.code);
    store.set(s.studentId);
  }, []);

  useEffect(() => {
    let off = false;
    (async () => {
      try {
        setHealth(await client.health());
        const saved = store.get();
        if (saved) {
          try { if (!off) adopt(await client.getState(saved)); return; }
          catch (e) { if (!(e instanceof ApiError && e.status === 404)) throw e; store.clear(); }
        }
        if (!off) adopt(await client.newStudent());
      } catch (e) { if (!off) setLoadError(msg(e)); }
    })();
    return () => { off = true; };
  }, [client, adopt]);

  const run = async () => {
    if (!state || running) return;
    setRunning(true); setError(null);
    try {
      const prevId = state.problem?.id;
      const res = await client.submit(state.studentId, code);
      setOutcome(res.outcome);
      // Keep what they typed unless a new problem loaded (then the starter code replaces it).
      const moved = res.state.problem?.id !== prevId;
      adopt(res.state, !moved);
      if (moved && res.outcome.passed) setOutcome(res.outcome);
      if (res.state.problem?.kind === 'practice' && moved) setPracticeShown(true);
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({block: 'nearest', behavior: 'smooth'}));
    } catch (e) { setError(msg(e)); } finally { setRunning(false); }
  };

  const build = async (request: string) => {
    if (!state) return;
    setThemeBusy(true); setThemeError(null);
    try {
      const res = await client.buildTheme(state.studentId, request);
      if (res.built) { adopt(res.state); setOutcome(null); setThemeOpen(false); }
      else setThemeError(res.message);
    } catch (e) { setThemeError(msg(e)); } finally { setThemeBusy(false); }
  };

  const resetTheme = async () => {
    if (!state) return;
    setThemeBusy(true);
    try { adopt(await client.resetTheme(state.studentId)); setOutcome(null); setThemeOpen(false); }
    catch (e) { setThemeError(msg(e)); } finally { setThemeBusy(false); }
  };

  const restart = async () => {
    store.clear(); setOutcome(null); setLoadError(null);
    try { adopt(await client.newStudent()); } catch (e) { setLoadError(msg(e)); }
  };

  if (loadError) return <Container sx={{py: 6}}><Alert severity="error" action={<Button color="inherit" onClick={() => location.reload()}>Retry</Button>}>{loadError}</Alert></Container>;
  if (!state) return <Box sx={{display: 'grid', placeItems: 'center', minHeight: '60vh'}}><CircularProgress aria-label="Loading" /></Box>;

  const p = state.problem;
  const themed = state.project.id !== 'weather-station';
  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="xl" sx={{display: 'flex', alignItems: 'center', gap: 2, py: 1.25}}>
          <Typography component="h1" variant="h5" sx={{flex: 1, display: 'flex', gap: 1.5, alignItems: 'baseline', flexWrap: 'wrap'}}>
            CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>{state.project.title}</Typography>
          </Typography>
          <Button color="inherit" startIcon={<AutoAwesomeIcon />} onClick={() => { setThemeError(null); setThemeOpen(true); }}>Make it yours</Button>
        </Container>
      </Box>

      <Container maxWidth="xl" sx={{py: 2}}>
        <Box sx={{display: 'flex', flexDirection: {xs: 'column', lg: 'row'}, gap: 2, alignItems: {lg: 'center'}, justifyContent: 'space-between'}}>
          <PathStrip path={state.path} />
          {!state.complete && p && (
            <Box sx={{flex: 'none', width: {xs: '100%', lg: 'auto'}, minWidth: {lg: 520}}}>
              <ConceptMeters state={state} highlight={p.concepts} row />
            </Box>
          )}
        </Box>
        {state.onFallback && <Alert severity="info" sx={{my: 1}}>You're on the standard path for the rest of this project.</Alert>}
        {state.notices.map((n, i) => <Alert key={i} severity="info" sx={{my: 1}}>{n}</Alert>)}

        {state.complete || !p ? (
          <Paper variant="outlined" sx={{p: 4, mt: 2, textAlign: 'center'}}>
            <Typography variant="h4" component="h2">You finished {state.project.title}!</Typography>
            <Typography sx={{my: 2}}>Here's where you ended up on each idea.</Typography>
            <Box sx={{maxWidth: 420, mx: 'auto', textAlign: 'left'}}><ConceptMeters state={state} highlight={[]} /></Box>
            <Box sx={{display: 'flex', gap: 1, justifyContent: 'center', mt: 3}}>
              <Button variant="outlined" onClick={() => setThemeOpen(true)}>Try it in your own theme</Button>
              <Button variant="contained" onClick={restart}>Start over as a new student</Button>
            </Box>
          </Paper>
        ) : (
          <Box sx={{display: 'grid', gap: 2, mt: 1, gridTemplateColumns: {xs: '1fr', md: 'minmax(0,5fr) minmax(0,6fr)', xl: 'minmax(0,5fr) minmax(0,7fr)'}, alignItems: 'stretch'}}>
            <Paper variant="outlined" component="section" aria-label="Instructions" sx={{p: 2.5, borderRadius: '12px', height: {md: 'calc(100vh - 210px)'}, minHeight: {md: 480}, overflow: 'auto'}}>
              {p.kind === 'practice' && <Typography variant="overline" color="secondary" sx={{fontWeight: 700}}>Practice</Typography>}
              <Markdown source={p.instructions} />
            </Paper>

            <Box sx={{display: 'flex', flexDirection: 'column', gap: 1.5, height: {md: 'calc(100vh - 210px)'}, minHeight: {md: 480}, overflowY: {md: 'auto'}}}>
              <CodeEditor value={code} onChange={setCode} onRun={run} disabled={running} />
              <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                <Button variant="contained" color="secondary" size="large" startIcon={running ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />} disabled={running} onClick={run}>
                  {running ? 'Checking…' : 'Run'}
                </Button>
                <Typography variant="caption" color="text.secondary">Ctrl/⌘ + Enter</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ml: 'auto'}}>Attempts: {p.attempts}</Typography>
              </Box>
              {error && <Alert severity="error">{error}</Alert>}
              <div ref={resultsRef}>{outcome && <Results outcome={outcome} />}</div>
            </Box>

          </Box>
        )}
      </Container>

      {practiceShown && <PracticeDialog state={state} onClose={() => setPracticeShown(false)} />}
      <ThemeDialog open={themeOpen} aiOn={!!health?.ai} aiReason={health?.aiReason ?? null} themed={themed} busy={themeBusy} error={themeError}
        onBuild={build} onReset={resetTheme} onClose={() => setThemeOpen(false)} />
    </Box>
  );
}
