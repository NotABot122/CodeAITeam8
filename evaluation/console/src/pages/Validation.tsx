import {Alert, Box, Button, MenuItem, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useEffect, useState} from 'react';
import {api, pct, type Presets, type ValidateResult} from '../api';
import {Caveat, CodeInput, Loading, Section, Stat, useLoad, Verdict} from '../ui';

const LEVEL = (id: string) => id.replace('level-', 'Level ');

export default function Validation() {
  const res = useLoad(api.e01);
  const pre = useLoad(api.presets);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'disagree'>('disagree');

  const rerun = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await api.run('e01');
      res.reload();
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <Section
        title="Does the grader agree with a teacher?"
        subtitle="We wrote student answers for every level, both correct ones in different styles and ones that break a rule in the instructions, and compared the engine's pass/fail with what a teacher would decide."
        action={
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={rerun} disabled={running}>
            {running ? 'Running…' : 'Run again'}
          </Button>
        }
      >
        {runError && <Alert severity="error">{runError}</Alert>}
        <Loading error={res.error} loading={res.loading && !res.data} />
        {res.data && (
          <>
            <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
              <Stat label="Same decision as the teacher" value={pct(res.data.agreement)} hint={`${res.data.n_scored} answers`} tone={res.data.agreement >= 0.95 ? 'good' : 'warn'} />
              <Stat label="Wrong answers accepted" value={res.data.false_pass.length} tone={res.data.false_pass.length ? 'bad' : 'good'} />
              <Stat label="Correct answers rejected" value={res.data.false_fail.length} tone={res.data.false_fail.length ? 'bad' : 'good'} />
              <Stat label="Left for a teacher" value={res.data.n_review} hint="no clear right answer" />
            </Stack>
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)} sx={{mb: 1}}>
              <ToggleButton value="disagree">Where they differ</ToggleButton>
              <ToggleButton value="all">All answers</ToggleButton>
            </ToggleButtonGroup>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Level</TableCell>
                  <TableCell>Teacher</TableCell>
                  <TableCell>Grader</TableCell>
                  <TableCell>The answer</TableCell>
                  <TableCell>What the student is told</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {res.data.rows
                  .filter(r => filter === 'all' || r.key === 'review' || r.key !== r.grader)
                  .map(r => (
                    <TableRow key={r.id} sx={r.key !== 'review' && r.key !== r.grader ? {bgcolor: 'action.selected'} : undefined}>
                      <TableCell sx={{whiteSpace: 'nowrap'}}>{LEVEL(r.level)}</TableCell>
                      <TableCell>{r.key === 'review' ? 'unsure' : r.key}</TableCell>
                      <TableCell><Verdict ok={r.grader === 'pass'} /></TableCell>
                      <TableCell>{r.why}</TableCell>
                      <TableCell>{r.first_message.replace(/^Level \d: /, '')}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
            <Caveat>
              The teacher decisions are our draft and still need a real teacher to confirm them. The grader only says pass or fail; how far a student has got (the stage) comes from
              how many tries they needed, not from how good the code is.
            </Caveat>
          </>
        )}
      </Section>
      {pre.data && <TryIt presets={pre.data} />}
    </>
  );
}

function TryIt({presets}: {presets: Presets}) {
  const [level, setLevel] = useState('level-1');
  const [code, setCode] = useState(presets.correct['level-1']);
  const [result, setResult] = useState<ValidateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setResult(null), [code, level]);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.validate(level, code));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Try it" subtitle="Change the code, or load a common mistake, and see what the grader says.">
      <Stack direction={{xs: 'column', md: 'row'}} spacing={2}>
        <Box sx={{flex: 1}}>
          <Stack direction="row" spacing={1} sx={{mb: 1, flexWrap: 'wrap', rowGap: 1}}>
            <TextField select size="small" label="Level" value={level} onChange={e => { setLevel(e.target.value); setCode(presets.correct[e.target.value]); }} sx={{minWidth: 220}}>
              {presets.levels.map(l => <MenuItem key={l.id} value={l.id}>{l.label}: {l.title}</MenuItem>)}
            </TextField>
            <TextField select size="small" label="Start from" value="" onChange={e => {
              const v = e.target.value;
              setCode(v === 'correct' ? presets.correct[level] : presets.bugs.find(b => b.bug_id === v)?.code ?? code);
            }} sx={{minWidth: 260}}>
              <MenuItem value="correct">A correct answer</MenuItem>
              {presets.bugs.filter(b => b.level === level).map(b => <MenuItem key={b.bug_id} value={b.bug_id}>Mistake: {b.gap}</MenuItem>)}
            </TextField>
            <Button variant="contained" color="secondary" startIcon={<PlayArrowIcon />} onClick={run} disabled={busy}>
              {busy ? 'Checking…' : 'Run'}
            </Button>
          </Stack>
          <CodeInput value={code} onChange={setCode} rows={18} />
        </Box>
        <Box sx={{flex: 1}}>
          {error && <Alert severity="error">{error}</Alert>}
          {result && (
            <>
              <Stack direction="row" spacing={1} alignItems="center" sx={{mb: 1}}>
                <Verdict ok={result.passed} yes="passed" no="not yet" />
                <Typography variant="body2" color="text.secondary">{result.tests_run} checks · {result.ms} ms</Typography>
              </Stack>
              {result.messages.map((m, i) => <Alert key={i} severity={result.passed ? 'success' : 'warning'} sx={{mb: 1}}>{m}</Alert>)}
            </>
          )}
          {!result && !error && <Typography color="text.secondary">The result appears here.</Typography>}
        </Box>
      </Stack>
    </Section>
  );
}
