import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CodeIcon from '@mui/icons-material/Code';
import ExtensionIcon from '@mui/icons-material/Extension';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {Alert, Box, Button, CircularProgress, Container, Paper, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useTheme} from '@mui/material';
import {lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {ApiError, createHttpClient, type ApiClient} from '@/api/client';
import type {Health, Outcome, StudentState} from '@/api/types';
import type {WorkspaceState} from '@/blocks/format';
import type {Generated} from '@/blocks/python';

import ConceptMeters from './ui/ConceptMeters';
import CodeEditor from './ui/CodeEditor';
import FunctionBank from './ui/FunctionBank';
import {PracticeDialog, ThemeDialog} from './ui/Dialogs';
import {Markdown} from './ui/markdown';
import PathStrip from './ui/PathStrip';
import QuestApp from './quest/QuestApp';
import Landing from './landing/Landing';
import PathwayScreen from './landing/PathwayScreen';
import TeacherApp from './teacher/TeacherApp';
import CoursePage from './ui/CoursePage';
import NextStepPanel from './ui/NextStepPanel';
import QuizPanel, {quizReady, SubmitQuiz, type QuizAnswers} from './ui/QuizPanel';
import RubberDuck from './ui/RubberDuck';
import Results, {HintCard} from './ui/Results';

const KEY = 'codeai.studentId';
const store = {
  get: () => { try { return localStorage.getItem(KEY); } catch { return null; } },
  set: (v: string) => { try { localStorage.setItem(KEY, v); } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(KEY); } catch { /* private mode */ } },
};
// The workspace is one file for every problem, so after an inserted practice the server's code is the
// practice's. Each problem's last text is kept here and restored when the student comes back to it.
const draftKey = (s: StudentState) => s.problem?.format === 'code' ? `codeai.draft.${s.studentId}.${s.project.id}.${s.problem.id}` : null;
const drafts = {
  get: (s: StudentState) => { const k = draftKey(s); try { return k ? localStorage.getItem(k) : null; } catch { return null; } },
  set: (s: StudentState, code: string) => { const k = draftKey(s); try { if (k) localStorage.setItem(k, code); } catch { /* private mode */ } },
};
const GRADE_KEY = 'codeai.grade';
const savedGrade = (): number | null => { try { const g = Number(localStorage.getItem(GRADE_KEY)); return g >= 9 && g <= 12 ? g : null; } catch { return null; } };
const HINT_COST = "Using a hint is fine. It counts toward how this level is scored.";
const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

// Blockly is large, so it only loads when a student first picks Blocks.
const BlockEditor = lazy(() => import('./blocks/BlockEditor'));
type EditorMode = 'text' | 'blocks';
const MODE_KEY = 'codeai.editorMode';
const savedEditorMode = (): EditorMode => { try { return localStorage.getItem(MODE_KEY) === 'blocks' ? 'blocks' : 'text'; } catch { return 'text'; } };
/** The block workspace to show: `workspace` null means start empty, and `problem` says why. */
interface BlockLoad {key: number; loading: boolean; workspace: WorkspaceState | null; problem: string | null}

export default function App({client: injected}: {client?: ApiClient}) {
  const client = useMemo(() => injected ?? createHttpClient(import.meta.env.VITE_API_BASE_URL ?? ''), [injected]);
  const [state, setState] = useState<StudentState | null>(null);
  // The first screen is the readiness quest. 'resume' continues one that was started; 'lesson' is the coding screen.
  const [teacher, setTeacher] = useState(() => location.hash === '#/teacher');
  useEffect(() => {
    const on = () => setTeacher(location.hash === '#/teacher');
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  // landing -> quest (readiness check) -> pathway (Strands Decider 2B) -> lesson. 'resume' continues a started quest.
  const [mode, setMode] = useState<'loading' | 'landing' | 'quest' | 'resume' | 'pathway' | 'lesson'>('loading');
  const [grade, setGradeState] = useState<number | null>(savedGrade);
  const setGrade = (g: number) => { setGradeState(g); try { localStorage.setItem(GRADE_KEY, String(g)); } catch { /* private mode */ } };
  const [health, setHealth] = useState<Health | null>(null);
  const [code, setCode] = useState('');
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [answers, setAnswers] = useState<QuizAnswers>({});
  const [stepBusy, setStepBusy] = useState(false);
  const [stepError, setStepError] = useState<string | null>(null);
  const [practiceShown, setPracticeShown] = useState(false);
  const [showCourse, setShowCourse] = useState(false);
  // A hint the student asked for (not one that came with a failed run).
  const [asked, setAsked] = useState<{hint: string; source: Outcome['hintSource']} | null>(null);
  const [hintBusy, setHintBusy] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [themeBusy, setThemeBusy] = useState(false);
  const [themeError, setThemeError] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const dark = useTheme().palette.mode === 'dark';
  const [editorMode, setEditorMode] = useState<EditorMode>(savedEditorMode);
  const [blocks, setBlocks] = useState<BlockLoad>({key: 0, loading: false, workspace: null, problem: null});
  const [blockInfo, setBlockInfo] = useState<{emptySlots: number; looseBlocks: number}>({emptySlots: 0, looseBlocks: 0});
  // Bumped whenever the code is replaced from the server (new problem, new project), so Blocks mode reloads.
  const [codeEpoch, setCodeEpoch] = useState(0);
  const codeRef = useRef(code);
  codeRef.current = code;
  const translation = useRef(0);

  const adopt = useCallback((s: StudentState, keepCode = false) => {
    setState(s);
    if (!keepCode) { setCode(drafts.get(s) ?? s.code); setCodeEpoch(n => n + 1); }
    store.set(s.studentId);
  }, []);

  useEffect(() => { if (state) drafts.set(state, code); }, [state, code]);
  const problemId = state?.problem?.id;
  useEffect(() => { setAsked(null); }, [problemId]);

  // Text -> blocks. If the code has an error, or uses something blocks can't show, the workspace
  // starts empty and says why. The student's text stays as it is until they change the blocks.
  const toBlocks = useCallback(async (source: string) => {
    const ticket = ++translation.current;
    setBlocks(b => ({...b, loading: true}));
    let next: Omit<BlockLoad, 'key'>;
    try {
      const r = await client.toBlocks(source);
      next = r.ok ? {loading: false, workspace: r.workspace, problem: null} : {loading: false, workspace: null, problem: r.message};
    } catch (e) {
      next = {loading: false, workspace: null, problem: `Couldn't turn the code into blocks: ${msg(e)}`};
    }
    if (ticket === translation.current) setBlocks(b => ({key: b.key + 1, ...next}));
  }, [client]);

  const isCode = state?.problem?.format === 'code';
  useEffect(() => {
    if (editorMode === 'blocks' && isCode) void toBlocks(codeRef.current);
  }, [editorMode, isCode, codeEpoch, toBlocks]);

  const switchMode = (next: EditorMode | null) => {
    if (!next || next === editorMode) return;
    setEditorMode(next);
    try { localStorage.setItem(MODE_KEY, next); } catch { /* private mode */ }
  };

  const onBlocks = useCallback((g: Generated, changed: boolean) => {
    setBlockInfo({emptySlots: g.emptySlots, looseBlocks: g.looseBlocks});
    if (changed) setCode(g.code);
  }, []);

  useEffect(() => {
    let off = false;
    (async () => {
      try {
        setHealth(await client.health());
        const saved = store.get();
        if (saved) {
          try {
            const st = await client.getState(saved);
            if (off) return;
            adopt(st);
            // The landing page always comes first; it offers "Continue" for a saved student.
            setMode('landing');
            return;
          } catch (e) { if (!(e instanceof ApiError && e.status === 404)) throw e; store.clear(); }
        }
        if (!off) setMode('landing');
      } catch (e) { if (!off) setLoadError(msg(e)); }
    })();
    return () => { off = true; };
  }, [client, adopt]);

  const run = async () => {
    if (!state || running) return;
    setRunning(true); setError(null); setAsked(null);
    try {
      const prevId = state.problem?.id;
      const res = state.problem?.format === 'quiz' ? await client.answer(state.studentId, answers) : await client.submit(state.studentId, code);
      // Keep what they typed unless a new problem loaded (then its saved draft or starter code replaces it).
      const moved = res.state.problem?.id !== prevId;
      // After repeated tries the practice dialog explains the move, so the old level's result isn't shown too.
      setOutcome(moved && res.state.problem?.inserted === 'struggle' ? null : res.outcome);
      adopt(res.state, !moved);
      if (moved) setAnswers({});
      if (res.state.problem?.kind === 'practice' && moved) setPracticeShown(true);
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({block: 'nearest', behavior: 'smooth'}));
    } catch (e) { setError(msg(e)); } finally { setRunning(false); }
  };

  const askHint = async () => {
    if (!state?.problem || hintBusy) return;
    setHintBusy(true); setError(null);
    try {
      // The current text goes along so the AI tutor (when on) can phrase the hint from it.
      const res = await client.hint(state.studentId, state.problem.format === 'code' ? code : undefined);
      setAsked(res.outcome.hint ? {hint: res.outcome.hint, source: res.outcome.hintSource} : null);
      if (!res.outcome.hint) setError('There are no more hints for this one.');
      adopt(res.state, true);
    } catch (e) { setError(msg(e)); } finally { setHintBusy(false); }
  };

  const pick = async (index: number, theme?: string) => {
    if (!state) return;
    setStepBusy(true); setStepError(null);
    try {
      const res = await client.startNext(state.studentId, index, theme);
      if (res.built) { adopt(res.state); setOutcome(null); setAnswers({}); } else setStepError(res.message);
    } catch (e) { setStepError(msg(e)); } finally { setStepBusy(false); }
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

  const restart = () => {
    store.clear(); setOutcome(null); setLoadError(null); setState(null); setMode('landing');
  };

  const skipQuest = async () => {
    try { adopt(await client.newStudent()); setMode('lesson'); } catch (e) { setLoadError(msg(e)); }
  };

  const finishedQuest = async (id: string) => {
    try { adopt(await client.getState(id)); setOutcome(null); setMode('pathway'); } catch (e) { setLoadError(msg(e)); }
  };

  const startPathway = async (next: StudentState | null) => {
    try { adopt(next ?? await client.getState(state!.studentId)); setOutcome(null); setMode('lesson'); } catch (e) { setLoadError(msg(e)); }
  };

  if (teacher) return <TeacherApp onExit={() => { location.hash = ''; }} />;
  if (loadError) return <Container sx={{py: 6}}><Alert severity="error" action={<Button color="inherit" onClick={() => location.reload()}>Retry</Button>}>{loadError}</Alert></Container>;
  // Where a saved student picks up: a half-done check, the pathway screen (check done, no pathway yet), or the lesson.
  const resumeMode = (s: StudentState) => s.diagnostic === 'in_progress' ? 'resume' : s.diagnostic !== 'none' && !s.pathway ? 'pathway' : 'lesson';
  if (mode === 'landing') {
    const saved = state ? {
      label: state.diagnostic === 'in_progress' ? 'your readiness check'
        : state.diagnostic !== 'none' && !state.pathway ? 'choosing your pathway'
        : state.pathway ? `${state.pathway.title}: ${state.project.title}` : state.project.title,
      onResume: () => setMode(resumeMode(state)),
    } : null;
    // Starting the check again makes a new student, so the old one is forgotten first.
    return <Landing grade={grade} onGrade={setGrade} resume={saved}
      onStart={() => { if (state) { store.clear(); setState(null); setOutcome(null); } setMode('quest'); }}
      onSkip={() => void skipQuest()} />;
  }
  if (mode === 'pathway' && state) {
    return <PathwayScreen client={client} studentId={state.studentId} grade={grade} existing={state.pathway}
      onGrade={setGrade} onStart={s => void startPathway(s)} />;
  }
  if (mode === 'quest' || (mode === 'resume' && state)) {
    return <QuestApp client={client} resumeId={mode === 'resume' ? state!.studentId : null}
      onStarted={id => store.set(id)} onFinished={id => { store.set(id); void finishedQuest(id); }} onSkip={() => void skipQuest()} />;
  }
  if (!state || mode === 'loading') return <Box sx={{display: 'grid', placeItems: 'center', minHeight: '60vh'}}><CircularProgress aria-label="Loading" /></Box>;

  const p = state.problem;
  const themed = state.themed;
  const quiz = p?.format === 'quiz' && p.questions ? p : null;
  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="xl" sx={{display: 'flex', alignItems: 'center', gap: 2, py: 1.25}}>
          <Typography component="h1" variant="h5" sx={{flex: 1, display: 'flex', gap: 1.5, alignItems: 'baseline', flexWrap: 'wrap'}}>
            CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>{state.project.title}</Typography>
            {state.pathway && <Typography component="span" variant="body2" sx={{opacity: 0.85}}>Pathway: {state.pathway.title}</Typography>}
          </Typography>
          <Button color="inherit" onClick={() => setShowCourse(v => !v)}>{showCourse ? 'My lesson' : 'My course'}</Button>
          {state.project.topic === 'data-logic' && <Button color="inherit" startIcon={<AutoAwesomeIcon />} onClick={() => { setThemeError(null); setThemeOpen(true); }}>Make it yours</Button>}
        </Container>
      </Box>

      <Container maxWidth="xl" sx={{py: 2}}>
        {showCourse ? <CoursePage client={client} studentId={state.studentId} onBack={() => setShowCourse(false)} /> : <>
        <Box sx={{display: 'flex', flexDirection: {xs: 'column', lg: 'row'}, gap: 2, alignItems: {lg: 'center'}, justifyContent: 'space-between'}}>
          <PathStrip path={state.path} />
          {!state.complete && p && (
            <Box sx={{flex: 'none', width: {xs: '100%', lg: 'min(760px, 56vw)'}}}>
              <ConceptMeters state={state} highlight={p.concepts} row />
            </Box>
          )}
        </Box>
        {state.onFallback && <Alert severity="info" sx={{my: 1}}>You're on the standard path for the rest of this project.</Alert>}
        {state.notices.map((n, i) => <Alert key={i} severity="info" sx={{my: 1}}>{n}</Alert>)}

        {state.complete || !p ? (
          <NextStepPanel state={state} busy={stepBusy} error={stepError} onPick={pick} onRestart={restart} />
        ) : (
          <Box sx={{display: 'grid', gap: 2, mt: 1, gridTemplateColumns: {xs: '1fr', md: 'minmax(0,5fr) minmax(0,6fr)', xl: 'minmax(0,5fr) minmax(0,7fr)'}, alignItems: 'stretch'}}>
            <Paper variant="outlined" component="section" aria-label="Instructions" sx={{p: 2.5, borderRadius: '12px', height: {md: 'calc(100vh - 210px)'}, minHeight: {md: 480}, overflow: 'auto'}}>
              {p.kind === 'practice' && <Typography variant="overline" color="secondary" sx={{fontWeight: 700}}>Practice</Typography>}
              <Markdown source={p.instructions} />
            </Paper>

            <Box sx={{display: 'flex', flexDirection: 'column', gap: 1.5, height: {md: 'calc(100vh - 210px)'}, minHeight: {md: 480}, overflowY: {md: 'auto'}}}>
              {quiz ? (
                <Box sx={{flex: '1 0 auto'}}>
                  <QuizPanel questions={quiz.questions!} answers={answers} onChange={setAnswers} results={outcome?.questionResults ?? []} disabled={running} />
                </Box>
              ) : (
                <>
                  <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap'}}>
                    <ToggleButtonGroup size="small" exclusive value={editorMode} onChange={(_, v: EditorMode | null) => switchMode(v)} aria-label="How to write your code">
                      <ToggleButton value="text" sx={{px: 1.5, gap: 0.75}}><CodeIcon fontSize="small" />Text</ToggleButton>
                      <ToggleButton value="blocks" sx={{px: 1.5, gap: 0.75}}><ExtensionIcon fontSize="small" />Blocks</ToggleButton>
                    </ToggleButtonGroup>
                    {editorMode === 'blocks' && !blocks.loading && (blockInfo.emptySlots > 0 || blockInfo.looseBlocks > 0) && (
                      <Typography variant="caption" color="text.secondary" role="status">
                        {[blockInfo.emptySlots && `${blockInfo.emptySlots} empty ${blockInfo.emptySlots === 1 ? 'slot runs' : 'slots run'} as None`,
                          blockInfo.looseBlocks && `${blockInfo.looseBlocks} loose ${blockInfo.looseBlocks === 1 ? "block isn't" : "blocks aren't"} connected, so ${blockInfo.looseBlocks === 1 ? "it won't" : "they won't"} run`]
                          .filter(Boolean).join(' · ')}
                      </Typography>
                    )}
                  </Box>
                  {editorMode === 'text' ? (
                    <Box sx={{display: 'flex', flexDirection: {xs: 'column', sm: 'row'}, gap: 1.5, flex: '1 0 260px', minHeight: 0}}>
                      {p.functions && <FunctionBank functions={p.functions} />}
                      <Box sx={{flex: 1, minWidth: 0, display: 'flex'}}>
                        <CodeEditor value={code} onChange={setCode} onRun={run} disabled={running} />
                      </Box>
                    </Box>
                  ) : blocks.loading ? (
                    <Box sx={{flex: '1 0 360px', display: 'grid', placeItems: 'center'}}><CircularProgress aria-label="Turning your code into blocks" /></Box>
                  ) : (
                    <>
                      {blocks.problem && (
                        <Alert severity="warning">
                          {blocks.problem} So the block workspace starts empty. Your text code is unchanged until you add blocks here,
                          and adding blocks replaces it. To keep it, switch back to Text and fix it there.
                        </Alert>
                      )}
                      <Suspense fallback={<Box sx={{flex: '1 0 360px', display: 'grid', placeItems: 'center'}}><CircularProgress aria-label="Loading blocks" /></Box>}>
                        <BlockEditor key={blocks.key} initial={blocks.workspace} onChange={onBlocks} dark={dark} />
                      </Suspense>
                    </>
                  )}
                </>
              )}
              {quiz ? (
                <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                  <SubmitQuiz onClick={run} busy={running} disabled={!quizReady(quiz.questions!, answers)} />
                  <HintButton left={p!.hintCount - p!.hintsSeen} total={p!.hintCount} busy={hintBusy} disabled={running} onClick={askHint} />
                  <Typography variant="caption" color="text.secondary" sx={{ml: 'auto'}}>Attempts: {p!.attempts}</Typography>
                </Box>
              ) : (
              <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
                <Button variant="contained" color="secondary" size="large" startIcon={running ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />} disabled={running || (editorMode === 'blocks' && blocks.loading)} onClick={run}>
                  {running ? 'Checking…' : 'Run'}
                </Button>
                <HintButton left={p.hintCount - p.hintsSeen} total={p.hintCount} busy={hintBusy} disabled={running} onClick={askHint} />
                {editorMode === 'text' && <Typography variant="caption" color="text.secondary">Ctrl/⌘ + Enter</Typography>}
                <Typography variant="caption" color="text.secondary" sx={{ml: 'auto'}}>Attempts: {p.attempts}</Typography>
              </Box>
              )}
              {error && <Alert severity="error">{error}</Alert>}
              {asked && <HintCard hint={asked.hint} source={asked.source} note={HINT_COST} />}
              <div ref={resultsRef}>{outcome && <Results outcome={outcome} />}</div>
            </Box>

          </Box>
        )}
        </>}
      </Container>

      {practiceShown && <PracticeDialog state={state} onClose={() => setPracticeShown(false)} />}
      <ThemeDialog open={themeOpen} aiOn={!!health?.ai} aiReason={health?.aiReason ?? null} themed={themed} busy={themeBusy} error={themeError}
        onBuild={build} onReset={resetTheme} onClose={() => setThemeOpen(false)} />
    </Box>
  );
}

function HintButton({left, total, busy, disabled, onClick}: {left: number; total: number; busy: boolean; disabled: boolean; onClick: () => void}) {
  if (total === 0) return null;
  const none = left <= 0;
  return (
    <Tooltip title={none ? 'You have used every hint for this one.' : HINT_COST}>
      <span>
        <Button variant="outlined" size="large" disabled={disabled || busy || none} onClick={onClick}
          startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <RubberDuck fontSize="small" title="Ask Ducky" />}>
          {none ? 'No hints left' : `Hint (${left} left)`}
        </Button>
      </span>
    </Tooltip>
  );
}
