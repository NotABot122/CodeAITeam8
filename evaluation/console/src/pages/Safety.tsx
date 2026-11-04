import {Alert, Box, Button, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useState} from 'react';
import {api, pct, type E08Row, type FilterResult, type Rates} from '../api';
import {Caveat, Loading, Section, Stat, useLoad} from '../ui';

function RatesRow({label, r, output}: {label: string; r: Rates | null; output?: boolean}) {
  if (!r) return null;
  return (
    <TableRow>
      <TableCell sx={{fontWeight: 600}}>{label}</TableCell>
      <TableCell>{pct(r.catch_rate)}</TableCell>
      <TableCell>{output ? '–' : pct(r.false_block_rate)}</TableCell>
    </TableRow>
  );
}

function Cell({v, detail}: {v: boolean | null | undefined; detail?: string}) {
  if (v === null || v === undefined) return <>–</>;
  return <Chip size="small" variant="outlined" color={v ? 'error' : 'success'} label={v ? `blocked${detail ? ` · ${detail.replace(/_/g, ' ')}` : ''}` : 'allowed'} />;
}

const wrong = (r: E08Row) => r.proto !== null && r.expected !== 'review' && (r.expected === 'block') !== r.proto;

export default function Safety({ai}: {ai: boolean}) {
  const res = useLoad(api.e08);
  const pre = useLoad(api.presets);
  const [onlyWrong, setOnlyWrong] = useState(true);

  return (
    <>
      <LiveFilter ai={ai}
        inputs={pre.data ? [...pre.data.theme_requests.slice(15, 22), ...pre.data.theme_requests.slice(25, 28)] : []}
        outputs={pre.data?.hint_outputs.slice(7, 13) ?? []} />
      <Section title="How well do the filters work?"
        subtitle="We ran 48 project-theme requests from students and 16 tutor hints through the engine's filters. Each one is labeled with what should happen.">
        <Loading error={res.error} loading={res.loading && !res.data} />
        {res.data && (
          <>
            <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
              <Stat label="Harmful requests stopped" value={pct(res.data.input.proto.catch_rate)} tone="good" />
              <Stat label="Harmless requests stopped" value={pct(res.data.input.proto.false_block_rate)} hint="e.g. “shooting stars”" tone="bad" />
              <Stat label="Problem tutor hints stopped" value={pct(res.data.output.proto.catch_rate)} hint="answers in words, unkind wording" tone="bad" />
            </Stack>
            <Table size="small" sx={{mb: 2}}>
              <TableHead>
                <TableRow>
                  <TableCell>Filter</TableCell>
                  <TableCell>Stops what it should</TableCell>
                  <TableCell>Stops harmless text</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <RatesRow label="Student requests: engine with AI on" r={res.data.input.proto} />
                <RatesRow label="Student requests: engine with AI off (word list only)" r={res.data.input.local} />
                <RatesRow label="Student requests: AWS Bedrock Guardrails (for comparison)" r={res.data.input.guardrail} />
                <RatesRow label="Tutor hints: engine check" r={res.data.output.proto} output />
                <RatesRow label="Tutor hints: AWS Bedrock Guardrails (for comparison)" r={res.data.output.guardrail} output />
              </TableBody>
            </Table>
            <ToggleButtonGroup size="small" exclusive value={onlyWrong ? 'wrong' : 'all'} onChange={(_, v) => v && setOnlyWrong(v === 'wrong')} sx={{mb: 1}}>
              <ToggleButton value="wrong">Where the engine gets it wrong</ToggleButton>
              <ToggleButton value="all">Everything</ToggleButton>
            </ToggleButtonGroup>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Text</TableCell>
                  <TableCell>Should be</TableCell>
                  <TableCell>Engine</TableCell>
                  <TableCell>Guardrails</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[...res.data.input_rows, ...res.data.output_rows].filter(r => !onlyWrong || wrong(r)).map(r => (
                  <TableRow key={r.id}>
                    <TableCell sx={{maxWidth: 520}}>{r.text}</TableCell>
                    <TableCell>{r.expected === 'review' ? 'teacher decides' : r.expected === 'block' ? 'blocked' : 'allowed'}</TableCell>
                    <TableCell><Cell v={r.proto} detail={r.proto ? (r.proto_cat ?? r.proto_reason ?? undefined) : undefined} /></TableCell>
                    <TableCell><Cell v={r.guardrail} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Caveat>The expected outcomes are our draft and need review by the curriculum team, especially the “teacher decides” rows.</Caveat>
          </>
        )}
      </Section>
    </>
  );
}

function LiveFilter({ai, inputs, outputs}: {ai: boolean; inputs: {id: string; text: string}[]; outputs: {id: string; text: string}[]}) {
  const [direction, setDirection] = useState<'input' | 'output'>('input');
  const [text, setText] = useState('shooting stars and meteor showers');
  const [result, setResult] = useState<FilterResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (t = text) => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.filter(t, direction));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const samples = direction === 'input' ? inputs : outputs;
  return (
    <Section title="Try it" subtitle="Type what a student might ask for, or a hint the tutor might write, and see what each filter does.">
      {!ai && <Alert severity="warning" sx={{mb: 1}}>Live AI is off, so only the word list runs.</Alert>}
      <ToggleButtonGroup size="small" exclusive value={direction} onChange={(_, v) => { if (v) { setDirection(v); setResult(null); } }} sx={{mb: 1}}>
        <ToggleButton value="input">A student asks for</ToggleButton>
        <ToggleButton value="output">The tutor writes</ToggleButton>
      </ToggleButtonGroup>
      <Stack direction="row" spacing={1}>
        <TextField fullWidth size="small" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} inputProps={{maxLength: 1000}} />
        <Button variant="contained" color="secondary" onClick={() => run()} disabled={busy || !text.trim()}>{busy ? 'Checking…' : 'Check'}</Button>
      </Stack>
      <Stack direction="row" spacing={0.5} sx={{mt: 1, flexWrap: 'wrap', rowGap: 0.5}}>
        {samples.map(s => <Chip key={s.id} size="small" label={s.text.length > 48 ? s.text.slice(0, 48) + '…' : s.text} onClick={() => { setText(s.text); run(s.text); }} />)}
      </Stack>
      {error && <Alert severity="error" sx={{mt: 1}}>{error}</Alert>}
      {result && (
        <Box sx={{mt: 2}}>
          <Table size="small">
            <TableBody>
              {result.layers.map(l => (
                <TableRow key={l.layer}>
                  <TableCell sx={{fontWeight: 600, width: 380}}>{l.layer}</TableCell>
                  <TableCell sx={{width: 120}}>{l.blocked === null ? '–' : <Chip size="small" color={l.blocked ? 'error' : 'success'} label={l.blocked ? 'blocked' : 'allowed'} />}</TableCell>
                  <TableCell>
                    {l.detail === 'ok' ? '' : l.detail.replace(/_/g, ' ')}
                    {l.note && <Typography variant="caption" color="text.secondary" sx={{display: 'block'}}>{l.note}</Typography>}
                  </TableCell>
                  <TableCell sx={{width: 90, color: 'text.secondary'}}>{l.ms === null ? '' : `${l.ms} ms`}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Alert severity="info" sx={{mt: 1}}>The student gets: <strong>{result.proto_outcome}</strong></Alert>
        </Box>
      )}
    </Section>
  );
}
