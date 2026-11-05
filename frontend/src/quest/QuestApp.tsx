import FlagIcon from '@mui/icons-material/Flag';
import StarIcon from '@mui/icons-material/Star';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import {Alert, Box, Button, Chip, CircularProgress, Container, LinearProgress, Paper, TextField, Typography} from '@mui/material';
import {useCallback, useEffect, useRef, useState} from 'react';

import type {ApiClient} from '@/api/client';

import {InlineText} from '@/ui/markdown';
import {expectedSeconds, SLOW_DOWN_MESSAGE, useCountdown, usePace} from '@/ui/pace';

import MatchCard from '@/landing/MatchCard';

import {ExplainView, initialResponse, ItemView, QuestionBody, responseReady} from './StepView';
import type {AnswerResult, Feedback, Game, QuestDone, QuestOptions, Step, Zone} from './types';

// Seconds this question should take: its prompt, its code block or table, and every option, card and box to read.
const stepSeconds = (step: Step) => step.kind === 'explain' ? 0 : expectedSeconds({
  prompt: [step.prompt, ...(step.table ? [step.table.columns, ...step.table.rows].flat() : [])].join(' '),
  code: step.code?.text ?? null,
  choices: [...(step.options ?? []), ...(step.cards ?? []), ...(step.buckets ?? [])].map(o => o.text),
});

const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');
const INTEREST_MAX_CHARS = 80;   // max_goal_chars in diagnostic.yaml

function ZoneBar({zones}: {zones: Zone[]}) {
  return (
    <Box component="ol" aria-label="Zones" sx={{display: 'flex', gap: 1, listStyle: 'none', p: 0, m: 0, flexWrap: 'wrap'}}>
      {zones.map(z => (
        <Chip component="li" key={z.id} label={z.name} size="small" color={z.done ? 'success' : z.current ? 'primary' : 'default'} variant={z.current ? 'filled' : 'outlined'}
          aria-current={z.current ? 'step' : undefined} />
      ))}
    </Box>
  );
}

function GameBar({game}: {game: Game}) {
  return (
    <Box sx={{display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap'}}>
      <Chip icon={<StarIcon />} label={`${game.xp} XP`} color="secondary" size="small" />
      <Chip label={game.rank} size="small" variant="outlined" />
      {game.streak > 1 && <Chip label={`${game.streak} in a row`} size="small" variant="outlined" color="success" />}
      {game.badges.map(b => <Chip key={b.id} label={b.name} size="small" variant="outlined" />)}
    </Box>
  );
}

type Phase =
  | {name: 'loading'}
  | {name: 'welcome'; options: QuestOptions}
  | {name: 'step'; step: Step; zones: Zone[]; shownAt: number}
  | {name: 'feedback'; step: Step; feedback: Feedback; zones: Zone[]}
  | {name: 'done'; result: QuestDone};

export default function QuestApp({client, resumeId, onStarted, onFinished, onSkip}: {
  client: ApiClient; resumeId: string | null; onStarted: (studentId: string) => void; onFinished: (studentId: string) => void; onSkip: () => void;
}) {
  const [phase, setPhase] = useState<Phase>({name: 'loading'});
  const [studentId, setStudentId] = useState<string | null>(resumeId);
  const [game, setGame] = useState<Game | null>(null);
  const [buddy, setBuddy] = useState<string | null>(null);
  const [goal, setGoal] = useState<string | null>(null);
  // Optional: what the student is into. The server screens it and drops it if it has personal details.
  const [interests, setInterests] = useState('');
  const [notices, setNotices] = useState<string[]>([]);
  const [value, setValue] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const pace = usePace();
  const stepNow = phase.name === 'step' ? phase.step : null;
  const expected = stepNow ? stepSeconds(stepNow) : 0;
  const waitLeft = useCountdown(pace.slow && !!stepNow && stepNow.kind !== 'explain', expected,
    phase.name === 'step' ? phase.shownAt : 0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const show = useCallback((r: Awaited<ReturnType<ApiClient['questNext']>>) => {
    if (r.done) { setPhase({name: 'done', result: r}); return; }
    setValue(r.step.kind === 'explain' ? null : initialResponse(r.step));
    setPhase({name: 'step', step: r.step, zones: r.zones, shownAt: Date.now()});
  }, []);

  useEffect(() => {
    let off = false;
    (async () => {
      try {
        if (resumeId) show(await client.questNext(resumeId));
        else if (!off) setPhase({name: 'welcome', options: await client.questOptions()});
      } catch (e) { if (!off) setError(msg(e)); }
    })();
    return () => { off = true; };
  }, [client, resumeId, show]);

  useEffect(() => { headingRef.current?.focus(); }, [phase.name, phase.name === 'step' ? phase.step.id : '']);

  const start = async () => {
    setBusy(true); setError(null);
    try {
      const r = await client.questStart(buddy, goal, interests.trim() || null);
      onStarted(r.student_id); setStudentId(r.student_id); setGame(r.welcome.game); setNotices(r.notices ?? []); show(r.first);
    } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  const send = async (step: Step, response: unknown) => {
    if (!studentId || phase.name !== 'step') return;
    setBusy(true); setError(null);
    try {
      const elapsed = Date.now() - phase.shownAt;
      // Typed answers and skips aren't timed: only questions with choices can be clicked through.
      if (step.kind !== 'explain') pace.record(elapsed, stepSeconds(step));
      const r: AnswerResult = await client.questAnswer(studentId, response, elapsed);
      setGame(r.game); setCount(c => c + 1);
      setPhase({name: 'feedback', step, feedback: r.feedback, zones: r.zones});
    } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  const next = async () => {
    if (!studentId) return;
    setBusy(true); setError(null);
    try { show(await client.questNext(studentId)); } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  const zones = phase.name === 'step' || phase.name === 'feedback' ? phase.zones : [];
  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="md" sx={{py: 1.25, display: 'flex', alignItems: 'baseline', gap: 1.5, flexWrap: 'wrap'}}>
          <Typography component="p" variant="h5" sx={{flex: 1}}>CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Storm Chaser Academy</Typography></Typography>
          {(phase.name === 'welcome') && <Button color="inherit" onClick={onSkip}>Skip to coding</Button>}
          {(phase.name === 'welcome') && <Button color="inherit" href="#/teacher">For teachers</Button>}
        </Container>
      </Box>
      <Container maxWidth="md" sx={{py: 3, display: 'grid', gap: 2}}>
        {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
        {notices.map((n, i) => <Alert key={i} severity="info" onClose={() => setNotices(ns => ns.filter((_, j) => j !== i))}>{n}</Alert>)}
        {phase.name === 'loading' && !error && <Box sx={{display: 'grid', placeItems: 'center', py: 8}}><CircularProgress aria-label="Loading" /></Box>}

        {phase.name === 'welcome' && (
          <Paper variant="outlined" sx={{p: {xs: 2, sm: 4}, borderRadius: '12px', display: 'grid', gap: 3}}>
            <Box>
              <Typography ref={headingRef} tabIndex={-1} variant="h4" component="h1" sx={{outline: 0}}>{phase.options.title}</Typography>
              <Typography sx={{mt: 1, fontSize: 18}}>{phase.options.message}</Typography>
            </Box>
            <Box component="fieldset" sx={{border: 0, p: 0, m: 0}}>
              <Typography component="legend" sx={{fontWeight: 700, mb: 1}}>Pick a buddy</Typography>
              <Box role="radiogroup" sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                {phase.options.buddies.map(b => (
                  <Button key={b.id} role="radio" aria-checked={buddy === b.id} variant={buddy === b.id ? 'contained' : 'outlined'} onClick={() => setBuddy(b.id)}>{b.label}</Button>
                ))}
              </Box>
            </Box>
            <Box component="fieldset" sx={{border: 0, p: 0, m: 0}}>
              <Typography component="legend" sx={{fontWeight: 700, mb: 1}}>What do you want to make?</Typography>
              <Box role="radiogroup" sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
                {phase.options.goals.map(g => (
                  <Button key={g.id} role="radio" aria-checked={goal === g.id} variant={goal === g.id ? 'contained' : 'outlined'} onClick={() => setGoal(g.id)}>{g.label}</Button>
                ))}
              </Box>
            </Box>
            <Box>
              <TextField fullWidth label="What are you into? (optional)" placeholder="soccer, animals, video games, books"
                value={interests} onChange={e => setInterests(e.target.value)} slotProps={{htmlInput: {maxLength: INTEREST_MAX_CHARS}}}
                helperText="We use this to pick a project story for you. Don't include your name or other personal details." />
            </Box>
            <Box><ZoneBar zones={phase.options.zones} /></Box>
            <Box sx={{display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap'}}>
              <Button variant="contained" color="secondary" size="large" disabled={busy || !buddy || !goal} onClick={start}>{busy ? 'Starting…' : "Let's go"}</Button>
              <Typography variant="body2" color="text.secondary">Takes about 15 minutes. There are no grades, just a fun way to find your starting spot.</Typography>
            </Box>
          </Paper>
        )}

        {(phase.name === 'step' || phase.name === 'feedback') && (
          <>
            <Box sx={{display: 'grid', gap: 1}}>
              <ZoneBar zones={zones} />
              {game && <GameBar game={game} />}
              <LinearProgress variant="determinate" value={Math.min(100, (count / 14) * 100)} aria-label="Quest progress" sx={{borderRadius: 4, height: 6}} />
            </Box>
            <Paper variant="outlined" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px', display: 'grid', gap: 2}}>
              {phase.step.intro && phase.name === 'step' && <Typography color="text.secondary">{phase.step.intro}</Typography>}
              <Typography ref={headingRef} tabIndex={-1} variant="h5" component="h1" sx={{outline: 0, lineHeight: 1.45}}><InlineText text={phase.step.prompt} /></Typography>
              {phase.step.kind !== 'explain' && <QuestionBody step={phase.step} />}

              {phase.name === 'step' && phase.step.kind !== 'explain' && (
                <>
                  <ItemView step={phase.step} value={value} onChange={setValue} disabled={busy} />
                  {pace.justSlowed && <Alert severity="warning" onClose={pace.dismiss}>{SLOW_DOWN_MESSAGE}</Alert>}
                  <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap'}}>
                    <Button variant="contained" color="secondary" size="large" disabled={busy || waitLeft > 0 || !responseReady(phase.step, value)}
                      onClick={() => send(phase.step, value)} aria-describedby={waitLeft > 0 ? 'check-wait' : undefined}>
                      {waitLeft > 0 ? `Check (${waitLeft})` : 'Check'}
                    </Button>
                    {waitLeft > 0 && (
                      <Typography id="check-wait" variant="body2" color="text.secondary" role="timer" aria-live="off">
                        Read the question and every answer. Check is ready in {waitLeft} second{waitLeft === 1 ? '' : 's'}.
                      </Typography>
                    )}
                  </Box>
                </>
              )}
              {phase.name === 'step' && phase.step.kind === 'explain' && (
                <ExplainView step={phase.step} disabled={busy} onSend={t => send(phase.step, {text: t})} onSkip={() => send(phase.step, {skip: true})} />
              )}

              {phase.name === 'feedback' && (
                <Box role="status" aria-live="polite" sx={{display: 'grid', gap: 1.5}}>
                  <Alert severity={phase.feedback.correct === false ? 'info' : 'success'}>
                    <Typography sx={{fontWeight: 700}}><InlineText text={phase.feedback.message} /></Typography>
                    {phase.feedback.tip && <Typography><InlineText text={phase.feedback.tip} /></Typography>}
                  </Alert>
                  {phase.feedback.new_badges.map(b => <Chip key={b.id} color="secondary" label={`New badge: ${b.name}`} sx={{justifySelf: 'start'}} />)}
                  {phase.feedback.zone_cleared && <Typography>Zone cleared!</Typography>}
                  <Box><Button variant="contained" size="large" autoFocus disabled={busy} onClick={next}>Next</Button></Box>
                </Box>
              )}
            </Paper>
          </>
        )}

        {phase.name === 'done' && (
          <Paper variant="outlined" sx={{p: {xs: 2, sm: 4}, borderRadius: '12px', display: 'grid', gap: 2}}>
            <Typography ref={headingRef} tabIndex={-1} variant="h4" component="h1" sx={{outline: 0}}>Quest complete!</Typography>
            <Typography sx={{fontSize: 18}}>{phase.result.message}</Typography>
            {phase.result.next_stop?.activity && (
              <Paper variant="outlined" sx={{p: 2, borderRadius: '10px', borderColor: 'secondary.main', display: 'flex', gap: 1.5, alignItems: 'center'}}>
                <FlagIcon color="secondary" aria-hidden />
                <Box>
                  <Typography variant="overline" color="secondary" sx={{fontWeight: 700, lineHeight: 1.4}}>You will start with</Typography>
                  <Typography sx={{fontWeight: 700, fontSize: 18}}>
                    {phase.result.next_stop.activity.title}
                    {phase.result.next_stop.project && <Typography component="span" color="text.secondary" sx={{fontWeight: 400}}> in {phase.result.next_stop.project}</Typography>}
                  </Typography>
                  {phase.result.goal_connection && <Typography color="text.secondary">{phase.result.goal_connection}</Typography>}
                </Box>
              </Paper>
            )}
            {!phase.result.next_stop?.activity && phase.result.goal_connection && <Typography color="text.secondary">{phase.result.goal_connection}</Typography>}
            {phase.result.match && <MatchCard match={phase.result.match} />}
            {game && <GameBar game={game} />}
            <Box>
              <Typography sx={{fontWeight: 700, mb: 1}}>Your skill map</Typography>
              <Box component="ul" sx={{display: 'flex', gap: 1, flexWrap: 'wrap', listStyle: 'none', p: 0, m: 0}}>
                {phase.result.skill_tree.map(n => (
                  <Chip component="li" key={n.id} label={n.name} size="small"
                    icon={n.state === 'star' ? <StarIcon /> : n.state === 'open' ? <RadioButtonUncheckedIcon /> : <LockOutlinedIcon />}
                    color={n.state === 'star' ? 'success' : n.try_next ? 'primary' : 'default'} variant={n.state === 'locked' ? 'outlined' : 'filled'}
                    aria-label={`${n.name}: ${n.state === 'star' ? 'star' : n.state === 'open' ? 'ready to try' : 'locked'}`} />
                ))}
              </Box>
            </Box>
            <Box><Button variant="contained" color="secondary" size="large" onClick={() => studentId && onFinished(studentId)}>Find my pathway</Button></Box>
          </Paper>
        )}
      </Container>
    </Box>
  );
}
