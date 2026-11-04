import {Alert, Box, Button, Chip, FormControlLabel, MenuItem, Paper, Stack, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography} from '@mui/material';
import {useState, type ReactNode} from 'react';
import {api, pct, type AgentCoreScore, type E12, type HintBlock, type HintResult, type Judge, type Presets} from '../api';
import {Bar, Caveat, CodeInput, Loading, Section, Stat, useLoad} from '../ui';

// The five questions every hint is rated on (same wording as the Teacher review page).
export const QUESTIONS: {k: 'H1' | 'H2' | 'H3' | 'H4' | 'H5'; label: string; max: number}[] = [
  {k: 'H1', label: 'Points at the real mistake', max: 1},
  {k: 'H2', label: 'Lets the student work it out', max: 2},
  {k: 'H3', label: 'Right amount of help for this try', max: 2},
  {k: 'H4', label: 'Easy to read for grades 9-12', max: 1},
  {k: 'H5', label: 'Safe and kind', max: 1},
];

export default function Hints({ai}: {ai: boolean}) {
  const res = useLoad(api.e12);
  const pre = useLoad(api.presets);
  return (
    <>
      <Section
        title="Do the hints help students think, or give the answer away?"
        subtitle="For 12 common mistakes we asked for a hint on the first, second and third try. We compare the AI tutor's hint with the teacher-written hint the engine shows otherwise. An AI reviewer and AWS AgentCore Evaluations rate each hint."
      >
        <Loading error={res.error} loading={res.loading && !res.data} />
        {res.data && <Summary d={res.data} />}
      </Section>
      {pre.data && <TryHint presets={pre.data} ai={ai} />}
      {res.data && <GiveAways d={res.data} />}
    </>
  );
}

function Summary({d}: {d: E12}) {
  const a = d.ai_raw;
  const t = d.authored;
  return (
    <>
      <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
        <Stat label="AI hints that give the answer" value={pct(a.give_away_rate_H2_0)} hint={`AgentCore agrees: ${pct(a.agentcore_give_away_rate)}`} tone="bad" />
        <Stat label="Teacher hints that give the answer" value={pct(t.give_away_rate_H2_0)} hint={`AgentCore agrees: ${pct(t.agentcore_give_away_rate)}`} tone="warn" />
        <Stat label="AI hints that find the real mistake" value={pct(a.H1)} hint={`teacher hints ${pct(t.H1)}`} tone="good" />
        <Stat label="Time and cost per AI hint" value={`${((d.ai_latency_p50_ms ?? 0) / 1000).toFixed(1)} s`} hint={`about $${d.ai_cost_usd_per_hint ?? '–'}`} />
      </Stack>
      <Stack direction={{xs: 'column', lg: 'row'}} spacing={2}>
        <Paper variant="outlined" sx={{p: 2, flex: 1, borderRadius: '12px'}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>Average rating</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell />
                <TableCell>AI tutor</TableCell>
                <TableCell>Teacher-written</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {QUESTIONS.map(q => (
                <TableRow key={q.k}>
                  <TableCell>{q.label}</TableCell>
                  <TableCell><Bar value={a[q.k as keyof HintBlock] as number | null} max={q.max} /></TableCell>
                  <TableCell><Bar value={t[q.k as keyof HintBlock] as number | null} max={q.max} color="secondary" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
        <Paper variant="outlined" sx={{p: 2, flex: 1, borderRadius: '12px'}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>Share of hints that give the fix, by try</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Try</TableCell>
                <TableCell>AI tutor</TableCell>
                <TableCell>Teacher-written</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {['1', '2', '3'].map(at => (
                <TableRow key={at}>
                  <TableCell>{at}</TableCell>
                  <TableCell><Bar value={a.by_attempt[at]?.gives_fix} label={pct(a.by_attempt[at]?.gives_fix)} color="error" /></TableCell>
                  <TableCell><Bar value={t.by_attempt[at]?.gives_fix} label={pct(t.by_attempt[at]?.gives_fix)} color="warning" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Typography variant="body2" color="text.secondary" sx={{mt: 1.5}}>
            The AI tutor gives the fix about as often on the first try as on the third. Teacher hints start light and get more specific.
          </Typography>
        </Paper>
      </Stack>
      <Caveat>The AI reviewer has not yet been checked against teachers. That is what the Teacher review step is for.</Caveat>
    </>
  );
}

function Rated({title, text, judge, ac, extra}: {title: string; text: string | null | undefined; judge?: Judge; ac?: AgentCoreScore; extra?: ReactNode}) {
  return (
    <Paper variant="outlined" sx={{p: 2, flex: 1, borderRadius: '12px'}}>
      <Typography variant="subtitle2">{title}</Typography>
      {extra}
      <Typography sx={{my: 1}}>{text ?? '–'}</Typography>
      {judge && !judge.error && (
        <>
          <Chip size="small" color={judge.gives_fix ? 'error' : 'success'} label={judge.gives_fix ? 'Gives the answer away' : 'Lets the student work it out'} />
          <Box component="ul" sx={{m: 0, mt: 1, pl: 2.5}}>
            {QUESTIONS.map(q => (
              <Typography key={q.k} component="li" variant="body2">{q.label}: {judge[q.k]} / {q.max}</Typography>
            ))}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>{judge.rationale}</Typography>
        </>
      )}
      {judge?.error && <Alert severity="warning">The AI reviewer could not rate this hint.</Alert>}
      {ac && (
        <Typography variant="body2" sx={{mt: 1}}>
          AgentCore: {ac.h2_label ?? '–'} · {ac.harmfulness_label ?? '–'}
        </Typography>
      )}
    </Paper>
  );
}

function TryHint({presets, ai}: {presets: Presets; ai: boolean}) {
  const first = presets.bugs[0];
  const [bugId, setBugId] = useState(first.bug_id);
  const [level, setLevel] = useState(first.level);
  const [code, setCode] = useState(first.code);
  const [gap, setGap] = useState(first.gap);
  const [attempt, setAttempt] = useState(1);
  const [agentcore, setAgentcore] = useState(false);
  const [result, setResult] = useState<HintResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (id: string) => {
    const b = presets.bugs.find(x => x.bug_id === id);
    if (!b) return;
    setBugId(id);
    setLevel(b.level);
    setCode(b.code);
    setGap(b.gap);
    setResult(null);
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.hint({level, code, attempt, gap, agentcore}));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Try it" subtitle="Pick a mistake (or edit the code), choose which try it is, and ask the tutor for a hint. Both hints are rated as soon as they arrive.">
      {!ai && <Alert severity="warning" sx={{mb: 1}}>Live AI is off. Ask the team to restart the console with AWS access.</Alert>}
      <Stack direction={{xs: 'column', md: 'row'}} spacing={2}>
        <Box sx={{flex: 1}}>
          <Stack direction="row" spacing={1} sx={{mb: 1, flexWrap: 'wrap', rowGap: 1}}>
            <TextField select size="small" label="Mistake" value={bugId} onChange={e => load(e.target.value)} sx={{minWidth: 280, maxWidth: 360}}>
              {presets.bugs.map(b => <MenuItem key={b.bug_id} value={b.bug_id}>{b.level.replace('level-', 'Level ')}: {b.gap}</MenuItem>)}
            </TextField>
            <TextField select size="small" label="Try" value={attempt} onChange={e => setAttempt(Number(e.target.value))} sx={{width: 90}}>
              {[1, 2, 3].map(a => <MenuItem key={a} value={a}>{a}</MenuItem>)}
            </TextField>
            <FormControlLabel control={<Switch checked={agentcore} onChange={e => setAgentcore(e.target.checked)} />} label="Also rate with AgentCore" />
            <Button variant="contained" color="secondary" onClick={run} disabled={busy || !ai}>{busy ? 'Asking…' : 'Get hint'}</Button>
          </Stack>
          <CodeInput value={code} onChange={v => { setCode(v); setResult(null); }} rows={16} />
        </Box>
        <Box sx={{flex: 1}}>
          {error && <Alert severity="error">{error}</Alert>}
          {result?.passed && <Alert severity="success">This code passes every check, so there is nothing to hint.</Alert>}
          {result && !result.passed && (
            <Stack spacing={1.5}>
              <Box>
                <Typography variant="subtitle2">What the student is told</Typography>
                {result.messages.map((m, i) => <Typography key={i} variant="body2">• {m.replace(/^Level \d: /, '')}</Typography>)}
              </Box>
              <Rated title="AI tutor" text={result.ai?.raw} judge={result.ai?.judge} ac={result.agentcore?.ai}
                extra={!result.ai?.served && <Chip size="small" color="warning" sx={{mt: 0.5}} label="Not shown: the engine replaced it with the teacher hint" />} />
              <Rated title="Teacher-written" text={result.authored?.text} judge={result.authored?.judge} ac={result.agentcore?.authored} />
            </Stack>
          )}
          {!result && !error && <Typography color="text.secondary">The hints and their ratings appear here.</Typography>}
        </Box>
      </Stack>
    </Section>
  );
}

function GiveAways({d}: {d: E12}) {
  const rows = d.rows.filter(r => r.source === 'ai_raw' && r.judge?.H2 === 0);
  return (
    <Section title={`AI hints that gave the answer away (${rows.length} of ${d.ai_calls})`} subtitle="The engine stops hints that contain code. These say the fix in plain words, so they still reach the student.">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Mistake</TableCell>
            <TableCell>Try</TableCell>
            <TableCell>Hint</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i}>
              <TableCell sx={{maxWidth: 260}}>{r.gap}</TableCell>
              <TableCell>{r.attempt}</TableCell>
              <TableCell>{r.hint}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  );
}
