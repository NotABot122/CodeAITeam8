import {Alert, Box, Button, Chip, MenuItem, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useEffect, useState} from 'react';
import {api, num, pct, type Presets, type ValidateResult} from '../api';
import {Caveat, CodeInput, Loading, Section, Stat, useLoad, Verdict} from '../ui';

export default function Validation() {
  const res = useLoad(api.e01);
  const pre = useLoad(api.presets);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'disagree'>('all');

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
        title="Does the validation service agree with a human key?"
        subtitle="Proto validates code with automated checks per level plus a static loop rule on Level 3. Hand-written submissions (valid variants and requirement violations) run through proto's own grader; pass/fail is compared with a draft human key."
        action={
          <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={rerun} disabled={running}>
            {running ? 'Running…' : 'Re-run benchmark'}
          </Button>
        }
      >
        {runError && <Alert severity="error">{runError}</Alert>}
        <Loading error={res.error} loading={res.loading && !res.data} />
        {res.data && (
          <>
            <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
              <Stat label="Agreement" value={pct(res.data.agreement)} hint={`${res.data.n_scored} scored submissions`} tone={res.data.agreement >= 0.95 ? 'good' : 'warn'} />
              <Stat label="Cohen's kappa" value={num(res.data.cohens_kappa)} />
              <Stat label="False pass" value={res.data.false_pass.length} hint="broken requirement accepted" tone={res.data.false_pass.length ? 'bad' : 'good'} />
              <Stat label="False fail" value={res.data.false_fail.length} hint="valid code rejected" tone={res.data.false_fail.length ? 'bad' : 'good'} />
              <Stat label="For a teacher" value={res.data.n_review} hint="marked review, not scored" />
            </Stack>
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)} sx={{mb: 1}}>
              <ToggleButton value="all">All</ToggleButton>
              <ToggleButton value="disagree">Disagreements and review</ToggleButton>
            </ToggleButtonGroup>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Key</TableCell>
                  <TableCell>Grader</TableCell>
                  <TableCell>Why (key)</TableCell>
                  <TableCell>First message the student sees</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {res.data.rows
                  .filter(r => filter === 'all' || r.key === 'review' || r.key !== r.grader)
                  .map(r => {
                    const disagree = r.key !== 'review' && r.key !== r.grader;
                    return (
                      <TableRow key={r.id} sx={disagree ? {bgcolor: 'error.main', '& td': {color: 'error.contrastText'}} : undefined}>
                        <TableCell sx={{whiteSpace: 'nowrap'}}>{r.id}</TableCell>
                        <TableCell>{r.key === 'review' ? <Chip size="small" label="review" /> : r.key}</TableCell>
                        <TableCell>{r.grader}</TableCell>
                        <TableCell>{r.why}</TableCell>
                        <TableCell>{r.first_message}</TableCell>
                      </TableRow>
                    );
                  })}
              </TableBody>
            </Table>
            <Caveat>
              The key is a draft written from the level instructions; a teacher needs to confirm it. Pass/fail is only part of the requirement: proto's mastery stage comes from attempt
              and hint counts, so two passing submissions get the same stage whatever their quality. Rubric scoring is not built yet.
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
    <Section title="Try it: grade any submission live" subtitle="Edit the code (or load a seeded bug) and run proto's grader on it. Useful to show a false pass on stage.">
      <Stack direction={{xs: 'column', md: 'row'}} spacing={2}>
        <Box sx={{flex: 1}}>
          <Stack direction="row" spacing={1} sx={{mb: 1}}>
            <TextField select size="small" label="Level" value={level} onChange={e => { setLevel(e.target.value); setCode(presets.correct[e.target.value]); }} sx={{minWidth: 200}}>
              {presets.levels.map(l => (
                <MenuItem key={l.id} value={l.id}>
                  {l.label}: {l.title}
                </MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="Load" value="" onChange={e => {
              const v = e.target.value;
              if (v === 'correct') setCode(presets.correct[level]);
              else setCode(presets.bugs.find(b => b.bug_id === v)?.code ?? code);
            }} sx={{minWidth: 220}}>
              <MenuItem value="correct">Correct solution</MenuItem>
              {presets.bugs.filter(b => b.level === level).map(b => (
                <MenuItem key={b.bug_id} value={b.bug_id}>Bug: {b.bug_id}</MenuItem>
              ))}
            </TextField>
            <Button variant="contained" color="secondary" onClick={run} disabled={busy}>
              {busy ? 'Grading…' : 'Grade'}
            </Button>
          </Stack>
          <CodeInput value={code} onChange={setCode} rows={18} />
        </Box>
        <Box sx={{flex: 1}}>
          {error && <Alert severity="error">{error}</Alert>}
          {result && (
            <>
              <Stack direction="row" spacing={1} alignItems="center" sx={{mb: 1}}>
                <Verdict ok={result.passed} yes="passed" no={result.status} />
                <Typography variant="body2" color="text.secondary">
                  {result.tests_run} checks, {result.ms} ms
                </Typography>
              </Stack>
              {result.messages.map((m, i) => (
                <Alert key={i} severity={result.passed ? 'success' : 'warning'} sx={{mb: 1}}>
                  {m}
                </Alert>
              ))}
            </>
          )}
          {!result && !error && <Typography color="text.secondary">Results appear here.</Typography>}
        </Box>
      </Stack>
    </Section>
  );
}
