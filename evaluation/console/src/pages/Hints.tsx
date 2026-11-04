import {Alert, Box, Button, Chip, FormControlLabel, MenuItem, Paper, Stack, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography} from '@mui/material';
import {useState, type ReactNode} from 'react';
import {api, num, pct, type AgentCoreScore, type E12, type HintBlock, type HintResult, type Judge, type Presets} from '../api';
import {Bar, Caveat, CodeInput, Loading, Section, Stat, useLoad} from '../ui';

const ITEMS: {k: keyof HintBlock; label: string; max: number}[] = [
  {k: 'H1', label: 'H1 accurate', max: 1},
  {k: 'H2', label: 'H2 Socratic', max: 2},
  {k: 'H3', label: 'H3 strength fits attempt', max: 2},
  {k: 'H4', label: 'H4 grade-appropriate', max: 1},
  {k: 'H5', label: 'H5 safe and kind', max: 1},
];

export default function Hints({ai}: {ai: boolean}) {
  const res = useLoad(api.e12);
  const pre = useLoad(api.presets);
  return (
    <>
      <Section
        title="Are the hints helping students think, or giving the answer?"
        subtitle="12 seeded bugs × attempts 1-3. Proto's AIHinter writes a hint from the real check messages; the teacher-written hint is what proto shows otherwise. Both are scored on the E12 sheet by an LLM judge and by AgentCore Evaluations (custom H2 evaluator + Builtin.Harmfulness)."
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
        <Stat label="AI hints that give the answer" value={pct(a.give_away_rate_H2_0)} hint={`AgentCore: ${pct(a.agentcore_give_away_rate)}`} tone="bad" />
        <Stat label="Teacher hints that give the answer" value={pct(t.give_away_rate_H2_0)} hint={`AgentCore: ${pct(t.agentcore_give_away_rate)}`} tone="warn" />
        <Stat label="AI hint accurate" value={pct(a.H1)} hint={`teacher ${pct(t.H1)}`} tone="good" />
        <Stat label="Rejected by proto's guard" value={`${d.ai_rejected}/${d.ai_calls}`} hint={d.rejection_reasons.join(', ') || 'none'} />
        <Stat label="Latency / cost" value={`${d.ai_latency_p50_ms ?? '–'} ms`} hint={`P95 ${d.ai_latency_p95_ms ?? '–'} ms · ~$${d.ai_cost_usd_per_hint ?? '–'} per hint`} />
      </Stack>
      <Stack direction={{xs: 'column', lg: 'row'}} spacing={2}>
        <Paper variant="outlined" sx={{p: 2, flex: 1}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>E12 sheet, mean score (LLM judge)</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Item</TableCell>
                <TableCell>AI hint</TableCell>
                <TableCell>Teacher hint</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ITEMS.map(i => (
                <TableRow key={i.k}>
                  <TableCell>{i.label} (0-{i.max})</TableCell>
                  <TableCell><Bar value={a[i.k] as number | null} max={i.max} /></TableCell>
                  <TableCell><Bar value={t[i.k] as number | null} max={i.max} color="secondary" /></TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell>AgentCore H2 (0-2)</TableCell>
                <TableCell><Bar value={a.agentcore_H2_mean} max={2} /></TableCell>
                <TableCell><Bar value={t.agentcore_H2_mean} max={2} color="secondary" /></TableCell>
              </TableRow>
              <TableRow>
                <TableCell>AgentCore Harmfulness (1 = safe)</TableCell>
                <TableCell><Bar value={a.agentcore_harmfulness_mean} /></TableCell>
                <TableCell><Bar value={t.agentcore_harmfulness_mean} color="secondary" /></TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Paper>
        <Paper variant="outlined" sx={{p: 2, flex: 1}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>Does help get stronger with each attempt?</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Attempt</TableCell>
                <TableCell>AI: gives the fix</TableCell>
                <TableCell>Teacher: gives the fix</TableCell>
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
            AI hints give the fix about equally on every attempt: there is no hint ladder, the model decides the strength. Teacher hints start light and get specific. Help
            stays the same or grows from attempt 1 to 3 for {d.escalation_ai_raw.monotonic}/{d.escalation_ai_raw.bugs} bugs (AI) and {d.escalation_authored.monotonic}/
            {d.escalation_authored.bugs} (teacher).
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>
            Judge vs. AgentCore on H2: exact {pct(a.judge_vs_agentcore_H2?.exact)}, kappa {num(a.judge_vs_agentcore_H2?.kappa)}.
          </Typography>
        </Paper>
      </Stack>
      <Caveat>
        Hint model <code>{d.hint_model}</code>, judge <code>{d.judge_model}</code>. Neither judge is validated against teachers yet; that is what the Human rating tab is for. Seeded bugs
        and repeated code on attempts 2-3, not real students.
      </Caveat>
    </>
  );
}

function JudgeCard({title, text, judge, ac, extra}: {title: string; text: string | null | undefined; judge?: Judge; ac?: AgentCoreScore; extra?: ReactNode}) {
  return (
    <Paper variant="outlined" sx={{p: 2, flex: 1}}>
      <Typography variant="subtitle2">{title}</Typography>
      {extra}
      <Typography sx={{my: 1}}>{text ?? '–'}</Typography>
      {judge && !judge.error && (
        <>
          <Stack direction="row" spacing={0.5} sx={{flexWrap: 'wrap', rowGap: 0.5}}>
            {(['H1', 'H2', 'H3', 'H4', 'H5'] as const).map(k => (
              <Chip key={k} size="small" variant="outlined" label={`${k} ${judge[k]}`} color={k === 'H2' ? (judge.H2 === 0 ? 'error' : judge.H2 === 2 ? 'success' : 'warning') : 'default'} />
            ))}
            <Chip size="small" color={judge.gives_fix ? 'error' : 'success'} label={judge.gives_fix ? 'gives the fix' : 'leaves the fix to the student'} />
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>
            Judge: {judge.rationale}
          </Typography>
        </>
      )}
      {judge?.error && <Alert severity="warning">Judge: {judge.error}</Alert>}
      {ac && (
        <Box sx={{mt: 1}}>
          <Stack direction="row" spacing={0.5}>
            <Chip size="small" label={`AgentCore H2 ${ac.h2 ?? '–'} (${ac.h2_label ?? ''})`} />
            <Chip size="small" label={`Harmfulness ${ac.harmfulness ?? '–'} (${ac.harmfulness_label ?? ''})`} />
          </Stack>
          {ac.h2_explanation && (
            <Typography variant="caption" color="text.secondary" sx={{display: 'block', mt: 0.5}}>
              {ac.h2_explanation.slice(0, 300)}
            </Typography>
          )}
        </Box>
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
    <Section title="Try it: a hint for this student, scored live" subtitle="Pick a seeded bug or edit the code. The console grades it with proto, asks proto's AI tutor for a hint, and scores both the AI and the teacher hint. About 5 s; 15 s with AgentCore.">
      {!ai && <Alert severity="warning" sx={{mb: 1}}>Bedrock is off. Set AWS credentials and restart console_server.</Alert>}
      <Stack direction={{xs: 'column', md: 'row'}} spacing={2}>
        <Box sx={{flex: 1}}>
          <Stack direction="row" spacing={1} sx={{mb: 1, flexWrap: 'wrap', rowGap: 1}}>
            <TextField select size="small" label="Seeded bug" value={bugId} onChange={e => load(e.target.value)} sx={{minWidth: 220}}>
              {presets.bugs.map(b => (
                <MenuItem key={b.bug_id} value={b.bug_id}>{b.bug_id}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="Attempt" value={attempt} onChange={e => setAttempt(Number(e.target.value))} sx={{width: 110}}>
              {[1, 2, 3].map(a => <MenuItem key={a} value={a}>{a}</MenuItem>)}
            </TextField>
            <FormControlLabel control={<Switch checked={agentcore} onChange={e => setAgentcore(e.target.checked)} />} label="AgentCore scores" />
            <Button variant="contained" color="secondary" onClick={run} disabled={busy || !ai}>
              {busy ? 'Asking the tutor…' : 'Get hint'}
            </Button>
          </Stack>
          <TextField fullWidth size="small" label="Actual mistake (for the judge only, never sent to the tutor)" value={gap} onChange={e => setGap(e.target.value)} sx={{mb: 1}} />
          <CodeInput value={code} onChange={v => { setCode(v); setResult(null); }} rows={16} />
        </Box>
        <Box sx={{flex: 1}}>
          {error && <Alert severity="error">{error}</Alert>}
          {result?.passed && <Alert severity="success">This code passes every check, so there is nothing to hint.</Alert>}
          {result && !result.passed && (
            <Stack spacing={1.5}>
              <Box>
                <Typography variant="subtitle2">Check messages the student sees</Typography>
                {result.messages.map((m, i) => (
                  <Typography key={i} variant="body2" sx={{fontFamily: 'var(--code-font)'}}>• {m}</Typography>
                ))}
              </Box>
              <JudgeCard
                title="AI tutor hint (proto AIHinter)"
                text={result.ai?.raw}
                judge={result.ai?.judge}
                ac={result.agentcore?.ai}
                extra={
                  <Stack direction="row" spacing={0.5} sx={{mt: 0.5}}>
                    <Chip size="small" color={result.ai?.served ? 'primary' : 'warning'} label={result.ai?.served ? 'shown to student' : `rejected: ${result.ai?.rejected}`} />
                    <Chip size="small" variant="outlined" label={`${result.ai?.latency_ms ?? '–'} ms · ${result.ai?.tokens_in ?? '–'}/${result.ai?.tokens_out ?? '–'} tokens`} />
                  </Stack>
                }
              />
              <JudgeCard title={`Teacher-written hint for attempt ${attempt}`} text={result.authored?.text} judge={result.authored?.judge} ac={result.agentcore?.authored} />
            </Stack>
          )}
          {!result && !error && <Typography color="text.secondary">The hint and its scores appear here.</Typography>}
        </Box>
      </Stack>
    </Section>
  );
}

function GiveAways({d}: {d: E12}) {
  const rows = d.rows.filter(r => r.source === 'ai_raw' && r.judge?.H2 === 0);
  return (
    <Section title={`AI hints rated "gives the answer" (${rows.length}/${d.ai_calls})`} subtitle="Proto's output guard blocks code blocks, def lines and full SQL; these state the fix in words, so they reach the student.">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Bug</TableCell>
            <TableCell>Attempt</TableCell>
            <TableCell>Hint</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i}>
              <TableCell sx={{whiteSpace: 'nowrap'}}>{r.bug_id}</TableCell>
              <TableCell>{r.attempt}</TableCell>
              <TableCell>{r.hint}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  );
}
