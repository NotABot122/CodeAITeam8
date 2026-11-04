import {Alert, Box, Button, LinearProgress, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useEffect, useMemo, useState} from 'react';
import {api, pct, type RatingItem} from '../api';
import {Caveat, Loading, Section, useLoad} from '../ui';

const SCALES: {k: 'H1' | 'H2' | 'H3' | 'H4' | 'H5'; label: string; options: {v: number; t: string}[]}[] = [
  {k: 'H1', label: 'H1 Accurate: does the hint describe the student’s actual mistake?', options: [{v: 0, t: '0 no'}, {v: 1, t: '1 yes'}]},
  {k: 'H2', label: 'H2 Socratic', options: [{v: 0, t: '0 gives the answer'}, {v: 1, t: '1 names the issue'}, {v: 2, t: '2 guiding question'}]},
  {k: 'H3', label: 'H3 Strength fits the attempt number', options: [{v: 0, t: '0 off'}, {v: 1, t: '1 somewhat'}, {v: 2, t: '2 fits'}]},
  {k: 'H4', label: 'H4 Readable for grades 9-12', options: [{v: 0, t: '0 no'}, {v: 1, t: '1 yes'}]},
  {k: 'H5', label: 'H5 Safe and kind', options: [{v: 0, t: '0 no'}, {v: 1, t: '1 yes'}]},
];

type Scores = Partial<Record<'H1' | 'H2' | 'H3' | 'H4' | 'H5', number>>;

export default function Rating() {
  const items = useLoad(api.ratingItems);
  const agree = useLoad(api.agreement);
  const [rater, setRater] = useState(() => localStorage.getItem('e12-rater') ?? '');
  const [index, setIndex] = useState(0);
  const [scores, setScores] = useState<Scores>({});
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const done = useMemo(() => new Set(items.data?.rated[rater] ?? []), [items.data, rater]);
  const list = items.data?.items ?? [];
  const item: RatingItem | undefined = list[index];

  useEffect(() => {
    // Jump to the first item this rater has not rated yet.
    if (!list.length) return;
    const next = list.findIndex(i => !done.has(i.item_id));
    setIndex(next === -1 ? 0 : next);
  }, [rater, list, done]);

  const complete = SCALES.every(s => scores[s.k] !== undefined);

  const save = async () => {
    if (!item) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveRating({rater, item_id: item.item_id, ...scores, notes});
      localStorage.setItem('e12-rater', rater);
      setScores({});
      setNotes('');
      items.reload();
      agree.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Section
        title="Human rating: validate the judge"
        subtitle="Teachers or team members rate hints blind (no source, no judge score). The judge's numbers on the Hints tab only count once they agree with people. Ratings are saved to annotation/E12_proto_hint_ratings.jsonl."
      >
        <Loading error={items.error} loading={items.loading && !items.data} />
        {items.data && (
          <>
            <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
              <TextField size="small" label="Your rater id" value={rater} onChange={e => setRater(e.target.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 32))} helperText="letters, digits, - or _" />
              <Box sx={{flex: 1}}>
                <Typography variant="body2">
                  {done.size}/{list.length} rated by {rater || '…'}
                </Typography>
                <LinearProgress variant="determinate" value={list.length ? (done.size / list.length) * 100 : 0} sx={{height: 8, borderRadius: 4}} />
              </Box>
            </Stack>
            {item && rater && (
              <Paper variant="outlined" sx={{p: 2}}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="subtitle2">
                    {item.item_id} · {item.level} · attempt {item.attempt} {done.has(item.item_id) && '(already rated; saving again replaces it)'}
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" disabled={index === 0} onClick={() => setIndex(index - 1)}>Previous</Button>
                    <Button size="small" disabled={index >= list.length - 1} onClick={() => setIndex(index + 1)}>Next</Button>
                  </Stack>
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>Check messages the student saw</Typography>
                <Typography variant="body2" sx={{fontFamily: 'var(--code-font)'}}>{item.check_messages}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>The student's actual mistake</Typography>
                <Typography variant="body2">{item.student_mistake}</Typography>
                <Paper variant="outlined" sx={{p: 2, my: 2, bgcolor: 'action.hover'}}>
                  <Typography variant="caption" color="text.secondary">Hint</Typography>
                  <Typography sx={{fontSize: 17}}>{item.hint}</Typography>
                </Paper>
                <Stack spacing={1}>
                  {SCALES.map(s => (
                    <Stack key={s.k} direction={{xs: 'column', md: 'row'}} alignItems={{md: 'center'}} spacing={1}>
                      <Typography variant="body2" sx={{width: 380}}>{s.label}</Typography>
                      <ToggleButtonGroup size="small" exclusive value={scores[s.k] ?? null} onChange={(_, v) => v !== null && setScores({...scores, [s.k]: v})}>
                        {s.options.map(o => (
                          <ToggleButton key={o.v} value={o.v}>{o.t}</ToggleButton>
                        ))}
                      </ToggleButtonGroup>
                    </Stack>
                  ))}
                  <TextField size="small" label="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)} inputProps={{maxLength: 500}} />
                </Stack>
                {error && <Alert severity="error" sx={{mt: 1}}>{error}</Alert>}
                <Button variant="contained" sx={{mt: 2}} disabled={!complete || saving} onClick={save}>
                  {saving ? 'Saving…' : 'Save and next'}
                </Button>
              </Paper>
            )}
            {!rater && <Alert severity="info">Enter a rater id to start.</Alert>}
          </>
        )}
      </Section>
      <Section title="Agreement so far" subtitle="Human H2 vs. the LLM judge on the same item; and between the first two raters.">
        <Loading error={agree.error} loading={agree.loading && !agree.data} />
        {agree.data && (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Rater</TableCell>
                  <TableCell>Items</TableCell>
                  <TableCell>H2 exact vs. judge</TableCell>
                  <TableCell>AI hints giving the answer</TableCell>
                  <TableCell>Teacher hints giving the answer</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {agree.data.raters.map(r => (
                  <TableRow key={r.rater}>
                    <TableCell>{r.rater}</TableCell>
                    <TableCell>{r.n}</TableCell>
                    <TableCell>{pct(r.h2_exact_vs_judge)}</TableCell>
                    <TableCell>{pct(r.give_away_ai)}</TableCell>
                    <TableCell>{pct(r.give_away_teacher)}</TableCell>
                  </TableRow>
                ))}
                {!agree.data.raters.length && (
                  <TableRow>
                    <TableCell colSpan={5}>No ratings yet.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
            {agree.data.between_raters && (
              <Typography variant="body2" sx={{mt: 1}}>
                Between {agree.data.between_raters.raters.join(' and ')}: H2 exact {pct(agree.data.between_raters.h2_exact)} on {agree.data.between_raters.n} common items.
              </Typography>
            )}
            <Caveat>The E12 protocol asks for two independent raters on 30 hints. Report kappa only when both have rated the same items.</Caveat>
          </>
        )}
      </Section>
    </>
  );
}
