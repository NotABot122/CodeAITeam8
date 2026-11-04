import {Alert, Box, Button, LinearProgress, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography} from '@mui/material';
import {useEffect, useMemo, useState} from 'react';
import {api, pct, type RatingItem} from '../api';
import {Caveat, Loading, Section, useLoad} from '../ui';

// Same five questions as the Hints page, with the answer options a reviewer picks from.
const SCALES: {k: 'H1' | 'H2' | 'H3' | 'H4' | 'H5'; label: string; options: {v: number; t: string}[]}[] = [
  {k: 'H1', label: 'Does it point at the real mistake?', options: [{v: 0, t: 'No'}, {v: 1, t: 'Yes'}]},
  {k: 'H2', label: 'Does it let the student work it out?', options: [{v: 0, t: 'No, it gives the answer'}, {v: 1, t: 'It names the problem'}, {v: 2, t: 'It asks a guiding question'}]},
  {k: 'H3', label: 'Is it the right amount of help for this try?', options: [{v: 0, t: 'No'}, {v: 1, t: 'Somewhat'}, {v: 2, t: 'Yes'}]},
  {k: 'H4', label: 'Is it easy to read for grades 9-12?', options: [{v: 0, t: 'No'}, {v: 1, t: 'Yes'}]},
  {k: 'H5', label: 'Is it safe and kind?', options: [{v: 0, t: 'No'}, {v: 1, t: 'Yes'}]},
];
const STORE_KEY = 'codeai.reviewer';

type Scores = Partial<Record<'H1' | 'H2' | 'H3' | 'H4' | 'H5', number>>;

export default function Rating() {
  const items = useLoad(api.ratingItems);
  const agree = useLoad(api.agreement);
  const [rater, setRater] = useState(() => localStorage.getItem(STORE_KEY) ?? '');
  const [index, setIndex] = useState(0);
  const [scores, setScores] = useState<Scores>({});
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const done = useMemo(() => new Set(items.data?.rated[rater] ?? []), [items.data, rater]);
  const list = useMemo(() => items.data?.items ?? [], [items.data]);
  const item: RatingItem | undefined = list[index];

  useEffect(() => {
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
      localStorage.setItem(STORE_KEY, rater);
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
      <Section title="Teacher review" subtitle="Rate hints without knowing who wrote them. Once teachers and the AI reviewer agree, the ratings on the Hints step can be trusted.">
        <Loading error={items.error} loading={items.loading && !items.data} />
        {items.data && (
          <>
            <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
              <TextField size="small" label="Your name or initials" value={rater} onChange={e => setRater(e.target.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 32))} />
              <Box sx={{flex: 1}}>
                <Typography variant="body2">{done.size} of {list.length} done</Typography>
                <LinearProgress variant="determinate" value={list.length ? (done.size / list.length) * 100 : 0} sx={{height: 8, borderRadius: 4}} />
              </Box>
            </Stack>
            {!rater && <Alert severity="info">Enter your name or initials to start.</Alert>}
            {item && rater && (
              <Paper variant="outlined" sx={{p: 2.5, borderRadius: '12px'}}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle2">
                    {item.level.replace('level-', 'Level ')} · try {item.attempt}{done.has(item.item_id) && ' · already rated (saving again replaces it)'}
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" disabled={index === 0} onClick={() => setIndex(index - 1)}>Previous</Button>
                    <Button size="small" disabled={index >= list.length - 1} onClick={() => setIndex(index + 1)}>Skip</Button>
                  </Stack>
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>The student's mistake</Typography>
                <Typography variant="body2">{item.student_mistake}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{mt: 1}}>What the student was told</Typography>
                <Typography variant="body2">{item.check_messages.replace(/Level \d: /g, '')}</Typography>
                <Paper variant="outlined" sx={{p: 2, my: 2, bgcolor: 'action.hover'}}>
                  <Typography variant="caption" color="text.secondary">Hint</Typography>
                  <Typography sx={{fontSize: 17}}>{item.hint}</Typography>
                </Paper>
                <Stack spacing={1.25}>
                  {SCALES.map(s => (
                    <Stack key={s.k} direction={{xs: 'column', md: 'row'}} alignItems={{md: 'center'}} spacing={1}>
                      <Typography variant="body2" sx={{width: 340}}>{s.label}</Typography>
                      <ToggleButtonGroup size="small" exclusive value={scores[s.k] ?? null} onChange={(_, v) => v !== null && setScores({...scores, [s.k]: v})}>
                        {s.options.map(o => <ToggleButton key={o.v} value={o.v}>{o.t}</ToggleButton>)}
                      </ToggleButtonGroup>
                    </Stack>
                  ))}
                  <TextField size="small" label="Comment (optional)" value={notes} onChange={e => setNotes(e.target.value)} inputProps={{maxLength: 500}} />
                </Stack>
                {error && <Alert severity="error" sx={{mt: 1}}>{error}</Alert>}
                <Button variant="contained" sx={{mt: 2}} disabled={!complete || saving} onClick={save}>{saving ? 'Saving…' : 'Save and next'}</Button>
              </Paper>
            )}
          </>
        )}
      </Section>
      <Section title="Do people and the AI reviewer agree?" subtitle="Compared on “Does it let the student work it out?”.">
        <Loading error={agree.error} loading={agree.loading && !agree.data} />
        {agree.data && (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Reviewer</TableCell>
                  <TableCell>Hints rated</TableCell>
                  <TableCell>Same as AI reviewer</TableCell>
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
                {!agree.data.raters.length && <TableRow><TableCell colSpan={5}>No reviews yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
            {agree.data.between_raters && (
              <Typography variant="body2" sx={{mt: 1}}>
                {agree.data.between_raters.raters.join(' and ')} agree on {pct(agree.data.between_raters.h2_exact)} of the {agree.data.between_raters.n} hints they both rated.
              </Typography>
            )}
            <Caveat>Two reviewers rating the same 30 hints is enough for a first check.</Caveat>
          </>
        )}
      </Section>
    </>
  );
}
