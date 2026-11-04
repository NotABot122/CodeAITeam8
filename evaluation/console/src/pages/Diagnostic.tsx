import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {Alert, Box, Button, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography} from '@mui/material';
import {useState} from 'react';
import {api, pct, type DiagCondition, type DiagLesson} from '../api';
import {Bar, Caveat, Loading, Section, Stat, useLoad, Verdict} from '../ui';

const CONDS: DiagCondition[] = ['no_diagnostic', 'diagnostic_today', 'diagnostic_proposed', 'oracle'];
const SHORT: Record<DiagCondition, string> = {
  no_diagnostic: 'No diagnostic',
  diagnostic_today: 'Diagnostic today',
  diagnostic_proposed: 'Proposed handoff',
  oracle: 'Perfect knowledge',
};
const BANDS = [
  {k: 'low', label: 'Students who start low'},
  {k: 'middle', label: 'Students in the middle'},
  {k: 'high', label: 'Students who start high'},
] as const;

// Plain-language detail per check; the raw detail from the server stays available on hover.
function explain(id: string, passed: boolean, raw: string): string {
  switch (id) {
    case 'same_student':
      return passed ? 'The app opens the same student.' : 'The diagnostic gives students an id the student app does not accept, so the app starts a new student and the result is lost.';
    case 'stages_carried':
      return passed ? 'Confident results from the diagnostic become the starting level for each concept.' : 'The lesson starts every concept at zero.';
    case 'practice_carried':
    case 'message_matches':
      return raw;
    case 'same_grade':
      return passed ? 'Same grade band.' : 'The diagnostic is written for grades 3-5; the lesson, tutor and filters for high school.';
    case 'fails_safe':
      return passed ? 'The lesson starts at Level 1.' : 'The lesson does not start.';
    case 'no_overwrite':
      return passed ? 'A lesson already in progress is left alone.' : 'Progress was reset.';
    default:
      return raw;
  }
}

export default function Diagnostic() {
  const res = useLoad(api.diag);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const rerun = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await api.run('diag');
      res.reload();
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Section
      title="Can any student start at their own level?"
      subtitle="Simulated students with a known level take the real diagnostic, are handed to the real lesson, and work through it. We compare four ways of starting the lesson with the same students."
      action={
        <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={rerun} disabled={running}>
          {running ? 'Running… (about a minute)' : 'Run again'}
        </Button>
      }
    >
      {runError && <Alert severity="error">{runError}</Alert>}
      <Loading error={res.error} loading={res.loading && !res.data} />
      {res.data && <Body d={res.data} />}
    </Section>
  );
}

function Body({d}: {d: DiagLesson}) {
  const s = d.summary;
  const low = (c: DiagCondition) => s[c].by_band.low?.failed_on_levels ?? null;
  const maxFail = Math.max(...CONDS.flatMap(c => BANDS.map(b => s[c].by_band[b.k]?.failed_on_levels ?? 0)), 1);
  const passed = d.checks.filter(c => c.passed).length;
  return (
    <>
      <Stack direction="row" spacing={2} sx={{mb: 2, flexWrap: 'wrap', rowGap: 2}}>
        <Stat label="Gaps practiced before their level" value={pct(s.diagnostic_today.gaps_practiced_first)} hint={`proposed handoff: ${pct(s.diagnostic_proposed.gaps_practiced_first)}`} tone="bad" />
        <Stat label="Failed tries, students who start low" value={`${low('no_diagnostic')} → ${low('diagnostic_today')}`} hint={`no diagnostic → today; proposed: ${low('diagnostic_proposed')}`} tone="warn" />
        <Stat label="Handoff checks passed" value={`${passed} of ${d.checks.length}`} tone={passed === d.checks.length ? 'good' : 'bad'} />
        {s.diagnostic_accuracy && <Stat label="Diagnostic finds the real gaps" value={pct(s.diagnostic_accuracy.gap_found)} hint={`right level ${pct(s.diagnostic_accuracy.exact)}, within one ${pct(s.diagnostic_accuracy.within_one)}`} />}
      </Stack>

      <Stack direction={{xs: 'column', lg: 'row'}} spacing={2}>
        <Paper variant="outlined" sx={{p: 2, flex: 1, borderRadius: '12px'}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>Failed tries on levels, by where the student starts</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell />
                {CONDS.map(c => <TableCell key={c}>{SHORT[c]}</TableCell>)}
              </TableRow>
            </TableHead>
            <TableBody>
              {BANDS.map(b => (
                <TableRow key={b.k}>
                  <TableCell>{b.label}{s.no_diagnostic.by_band[b.k] && <Typography variant="caption" color="text.secondary"> ({s.no_diagnostic.by_band[b.k].n})</Typography>}</TableCell>
                  {CONDS.map(c => (
                    <TableCell key={c}>
                      <Bar value={s[c].by_band[b.k]?.failed_on_levels ?? null} max={maxFail} label={String(s[c].by_band[b.k]?.failed_on_levels ?? '–')} color={c === 'diagnostic_today' ? 'warning' : c === 'diagnostic_proposed' ? 'success' : 'primary'} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Typography variant="body2" color="text.secondary" sx={{mt: 1.5}}>
            Everyone finishes in every condition; the difference is how much the student struggles on the way. Students who start low gain the most from a good handoff.
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{p: 2, flex: 1, borderRadius: '12px'}}>
          <Typography variant="subtitle2" sx={{mb: 1}}>What changes between the conditions</Typography>
          <Box component="ul" sx={{m: 0, pl: 2.5, '& li': {mb: 0.75}}}>
            <li><strong>No diagnostic:</strong> every student starts at Level 1 with nothing known.</li>
            <li><strong>Diagnostic today:</strong> confident results set the starting level per concept, and the lesson may start with one practice problem.</li>
            <li><strong>Proposed handoff:</strong> today's handoff, plus a practice problem before each level the diagnostic found a gap in.</li>
            <li><strong>Perfect knowledge:</strong> the proposed handoff fed with each student's true level. The best a diagnostic could do.</li>
          </Box>
        </Paper>
      </Stack>

      <Typography variant="subtitle2" sx={{mt: 2.5, mb: 1}}>The handoff, checked on today's code</Typography>
      <Table size="small">
        <TableBody>
          {d.checks.map(c => (
            <TableRow key={c.id} sx={!c.passed ? {bgcolor: 'action.selected'} : undefined}>
              <TableCell sx={{width: 90}}><Verdict ok={c.passed} /></TableCell>
              <TableCell sx={{fontWeight: 600, width: 420}}>{c.requirement}</TableCell>
              <TableCell title={c.detail}>{explain(c.id, c.passed, c.detail)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Caveat>
        {d.students} simulated students; how fast they learn is our assumption, so compare the conditions rather than read the numbers as real. The proposed handoff only uses
        parts that already exist. The engine and diagnostic teams decide how to build it.
      </Caveat>
    </>
  );
}
