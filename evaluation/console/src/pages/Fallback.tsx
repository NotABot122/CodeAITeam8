import {Alert, Button, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useState} from 'react';
import {api} from '../api';
import {Caveat, Loading, Section, Stat, useLoad, Verdict} from '../ui';

// Plain-language names for the scenarios in proto_fallback_eval.py (keyed by its scenario text).
const NAMES: Record<string, string> = {
  'baseline adaptive': 'Nothing goes wrong',
  'router raises on 2nd decision': 'Choosing the next step crashes',
  'router returns a problem not in the manifest': 'Next step points to a problem that does not exist',
  'saved progress is corrupted': "The student's saved progress is damaged",
  'progress save fails twice': 'Saving progress fails twice',
  'grader unavailable for 2 submissions': 'Grading is down for a moment',
  'grader unavailable for every submission': 'Grading stays down',
  'grader raises an unexpected exception once': 'Grading hits an unexpected error',
  'grader times out once': 'Grading times out once',
  'AI hint model returns ModelError': 'The AI tutor is unavailable',
  'AI hint model raises an unexpected exception': 'The AI tutor hits an unexpected error',
  'adaptive routing turned off': 'Adaptive mode switched off',
};

function PathSteps({path}: {path: string[]}) {
  const shown = path.slice(0, 8);
  return (
    <Stack direction="row" spacing={0.5} sx={{flexWrap: 'wrap', rowGap: 0.5}}>
      {shown.map((p, i) => (
        <Chip key={i} size="small" variant="outlined" color={p.startsWith('practice') ? 'secondary' : 'default'} label={p.startsWith('practice') ? 'Practice' : p.replace('level-', 'Level ')} />
      ))}
      {path.length > shown.length && <Typography variant="body2">… {path.length - shown.length} more</Typography>}
    </Stack>
  );
}

export default function Fallback() {
  const res = useLoad(api.e07);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const rerun = async () => {
    setRunning(true);
    setRunError(null);
    try {
      await api.run('e07');
      res.reload();
    } catch (e) {
      setRunError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Section
      title="When something breaks, can the student still finish?"
      subtitle="We break one part of the engine at a time and send a student through the lesson. If the adaptive part fails, the student should continue on the standard path instead of getting stuck."
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
          <Stack direction="row" spacing={2} sx={{mb: 2}}>
            <Stat label="Student finishes" value={`${res.data.passed} of ${res.data.n}`} tone={res.data.passed === res.data.n ? 'good' : 'bad'} hint="failure cases" />
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>What we broke</TableCell>
                <TableCell>Should happen</TableCell>
                <TableCell>Finished</TableCell>
                <TableCell>Path the student took</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {res.data.scenarios.map(s => (
                <TableRow key={s.scenario} sx={!s.completed ? {bgcolor: 'action.selected'} : undefined}>
                  <TableCell sx={{fontWeight: 600}}>{NAMES[s.scenario] ?? s.scenario}</TableCell>
                  <TableCell>{s.expect}</TableCell>
                  <TableCell><Verdict ok={s.completed} yes="yes" no="no" /></TableCell>
                  <TableCell>
                    <PathSteps path={s.path} />
                    {s.fallback_events.length > 0 && <Typography variant="caption" color="text.secondary">Switched to the standard path</Typography>}
                    {s.crashed && <Typography variant="body2" sx={{color: 'error.main', mt: 0.5}}>The lesson stopped with an error.</Typography>}
                    {!s.completed && !s.crashed && <Typography variant="body2" sx={{color: 'error.main', mt: 0.5}}>Stuck on the same level.</Typography>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Caveat>
            Unexpected errors in grading or in the AI tutor stop the lesson; in the student app this shows as "Something went wrong". If grading stays down, the student
            keeps retrying the same level. The engine team owns the fix.
          </Caveat>
        </>
      )}
    </Section>
  );
}
