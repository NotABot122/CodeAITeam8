import {Alert, Box, Button, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useState} from 'react';
import {api, pct, type E08Row, type FilterResult, type Rates} from '../api';
import {Caveat, Loading, Section, Stat, useLoad} from '../ui';

function RatesRow({label, r}: {label: string; r: Rates | null}) {
  if (!r) return null;
  return (
    <TableRow>
      <TableCell sx={{fontWeight: 600}}>{label}</TableCell>
      <TableCell>{pct(r.catch_rate)}</TableCell>
      <TableCell>{pct(r.false_block_rate)}</TableCell>
      <TableCell sx={{fontSize: 12}}>{r.missed.join(', ') || '–'}</TableCell>
      <TableCell sx={{fontSize: 12}}>{r.false_blocks.join(', ') || '–'}</TableCell>
    </TableRow>
  );
}

function Cell({v, detail}: {v: boolean | null | undefined; detail?: string}) {
  if (v === null || v === undefined) return <>–</>;
  return <Chip size="small" variant="outlined" color={v ? 'error' : 'success'} label={v ? `block${detail ? ` (${detail})` : ''}` : 'allow'} />;
}

function wrong(r: E08Row, v: boolean | null | undefined) {
  if (v === null || v === undefined || r.expected === 'review') return false;
  return (r.expected === 'block') !== v;
}

export default function Safety({ai}: {ai: boolean}) {
  const res = useLoad(api.e08);
  const pre = useLoad(api.presets);
  const [onlyWrong, setOnlyWrong] = useState(false);

  return (
    <>
      <LiveFilter ai={ai} samples={pre.data ? [...pre.data.theme_requests.slice(15, 22), ...pre.data.theme_requests.slice(25, 28)] : []} outSamples={pre.data?.hint_outputs.slice(7, 13) ?? []} />
      <Section title="Benchmark: theme requests and hint outputs" subtitle="48 labeled theme requests (student input) and 16 labeled hint texts (model output), run through proto's filters and our baseline Bedrock Guardrail.">
        <Loading error={res.error} loading={res.loading && !res.data} />
        {res.data && (
          <>
            <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
              <Stat label="Input: harmful caught" value={pct(res.data.input.proto.catch_rate)} hint="proto default" tone="good" />
              <Stat label="Input: harmless blocked" value={pct(res.data.input.proto.false_block_rate)} hint="proto default" tone="bad" />
              <Stat label="Output: answer leaks caught" value={pct(res.data.output.proto.catch_rate)} hint="proto hint check" tone="bad" />
              <Stat label="Moderation latency" value={`${res.data.input_latency_ms.proto_p50 ?? '–'} ms`} hint={`P95 ${res.data.input_latency_ms.proto_p95 ?? '–'} ms`} />
            </Stack>
            <Typography variant="subtitle2" sx={{mt: 1}}>Student input</Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Layer</TableCell>
                  <TableCell>Catch rate</TableCell>
                  <TableCell>False-block rate</TableCell>
                  <TableCell>Missed</TableCell>
                  <TableCell>False blocks</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <RatesRow label="Proto local rules only (--ai off)" r={res.data.input.local} />
                <RatesRow label="Proto default (local + Bedrock moderation)" r={res.data.input.proto} />
                <RatesRow label="Bedrock Guardrail (our baseline)" r={res.data.input.guardrail} />
                <RatesRow label="Proto default + Guardrail" r={res.data.input_proto_plus_guardrail} />
              </TableBody>
            </Table>
            <Typography variant="subtitle2" sx={{mt: 2}}>Model output (AI hints)</Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Layer</TableCell>
                  <TableCell>Catch rate</TableCell>
                  <TableCell>False-block rate</TableCell>
                  <TableCell>Missed</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                <RatesRow label="Proto hint check + local rules" r={res.data.output.proto} />
                <RatesRow label="Bedrock Guardrail (OUTPUT)" r={res.data.output.guardrail} />
              </TableBody>
            </Table>
            <Stack direction="row" alignItems="center" spacing={1} sx={{mt: 2, mb: 1}}>
              <Typography variant="subtitle2">Every case</Typography>
              <ToggleButtonGroup size="small" exclusive value={onlyWrong ? 'wrong' : 'all'} onChange={(_, v) => v && setOnlyWrong(v === 'wrong')}>
                <ToggleButton value="all">All</ToggleButton>
                <ToggleButton value="wrong">Wrong for proto default</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Expected</TableCell>
                  <TableCell>Text</TableCell>
                  <TableCell>Proto local</TableCell>
                  <TableCell>Proto default</TableCell>
                  <TableCell>Guardrail</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[...res.data.input_rows, ...res.data.output_rows]
                  .filter(r => !onlyWrong || wrong(r, r.proto))
                  .map(r => (
                    <TableRow key={r.id} sx={wrong(r, r.proto) ? {bgcolor: 'action.selected'} : undefined}>
                      <TableCell>{r.id}</TableCell>
                      <TableCell>{r.expected}</TableCell>
                      <TableCell sx={{maxWidth: 420}}>{r.text}</TableCell>
                      <TableCell>{r.local === undefined ? '–' : <Cell v={r.local} detail={r.local ? r.local_cat : undefined} />}</TableCell>
                      <TableCell><Cell v={r.proto} detail={r.proto ? (r.proto_cat ?? r.proto_reason ?? undefined) : undefined} /></TableCell>
                      <TableCell><Cell v={r.guardrail} detail={r.guardrail_filters?.join(', ')} /></TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
            <Caveat>Labels are ours and need T&amp;L review, especially the borderline (review) and alcohol / gambling rows. Synthetic requests only.</Caveat>
          </>
        )}
      </Section>
    </>
  );
}

function LiveFilter({ai, samples, outSamples}: {ai: boolean; samples: {id: string; text: string}[]; outSamples: {id: string; text: string}[]}) {
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

  const list = direction === 'input' ? samples : outSamples;
  return (
    <Section title="Try it: what does each filter layer do?" subtitle="Type a theme request (student input) or a hint text (model output). Each layer runs live; the last line is what the student would get from proto.">
      {!ai && <Alert severity="warning" sx={{mb: 1}}>Bedrock is off: only the local layers run.</Alert>}
      <Stack direction="row" spacing={1} sx={{mb: 1}}>
        <ToggleButtonGroup size="small" exclusive value={direction} onChange={(_, v) => v && (setDirection(v), setResult(null))}>
          <ToggleButton value="input">Student input</ToggleButton>
          <ToggleButton value="output">AI hint output</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      <Stack direction="row" spacing={1}>
        <TextField fullWidth size="small" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()} inputProps={{maxLength: 1000}} />
        <Button variant="contained" color="secondary" onClick={() => run()} disabled={busy || !text.trim()}>
          {busy ? 'Checking…' : 'Check'}
        </Button>
      </Stack>
      <Stack direction="row" spacing={0.5} sx={{mt: 1, flexWrap: 'wrap', rowGap: 0.5}}>
        {list.map(s => (
          <Chip key={s.id} size="small" label={s.text.length > 48 ? s.text.slice(0, 48) + '…' : s.text} onClick={() => { setText(s.text); run(s.text); }} />
        ))}
      </Stack>
      {error && <Alert severity="error" sx={{mt: 1}}>{error}</Alert>}
      {result && (
        <Box sx={{mt: 2}}>
          <Table size="small">
            <TableBody>
              {result.layers.map(l => (
                <TableRow key={l.layer}>
                  <TableCell sx={{fontWeight: 600, width: 360}}>{l.layer}</TableCell>
                  <TableCell sx={{width: 120}}>
                    {l.blocked === null ? '–' : <Chip size="small" color={l.blocked ? 'error' : 'success'} label={l.blocked ? 'block' : 'allow'} />}
                  </TableCell>
                  <TableCell>
                    {l.detail}
                    {l.note && <Typography variant="caption" color="text.secondary" sx={{display: 'block'}}>{l.note}</Typography>}
                  </TableCell>
                  <TableCell sx={{width: 90, color: 'text.secondary'}}>{l.ms === null ? '' : `${l.ms} ms`}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Alert severity="info" sx={{mt: 1}}>
            With proto today, the student gets: <strong>{result.proto_outcome}</strong>
          </Alert>
        </Box>
      )}
    </Section>
  );
}
