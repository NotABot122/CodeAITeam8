import {Alert, Box, Button, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useState} from 'react';
import {api} from '../api';
import {Caveat, Loading, Section, Stat, useLoad, Verdict} from '../ui';

function PathSteps({path}: {path: string[]}) {
  const shown = path.slice(0, 8);
  return (
    <Stack direction="row" spacing={0.5} sx={{flexWrap: 'wrap', rowGap: 0.5}}>
      {shown.map((p, i) => (
        <Chip key={i} size="small" variant="outlined" color={p.startsWith('practice') ? 'secondary' : 'default'} label={p.replace('level-', 'L').replace('practice-', 'P:')} />
      ))}
      {path.length > shown.length && <Typography variant="body2">… +{path.length - shown.length}</Typography>}
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
      title="When something fails, does the student still finish?"
      subtitle="Requirement: when validation or routing fails, the student falls back to a working non-adaptive path rather than a broken one. Each scenario injects one fault into proto's Engine and a scripted student submits a correct file up to 12 times. No model calls, so this runs live in a few seconds."
      action={
        <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={rerun} disabled={running}>
          {running ? 'Injecting faults…' : 'Run all scenarios'}
        </Button>
      }
    >
      {runError && <Alert severity="error">{runError}</Alert>}
      <Loading error={res.error} loading={res.loading && !res.data} />
      {res.data && (
        <>
          <Stack direction="row" spacing={2} sx={{mb: 2}}>
            <Stat label="Scenarios passed" value={`${res.data.passed}/${res.data.n}`} tone={res.data.passed === res.data.n ? 'good' : 'bad'} hint="student finishes the project" />
            <Stat label="Routing failures" value={`${res.data.scenarios.filter(s => s.requirement.startsWith('routing') && s.completed).length}/${res.data.scenarios.filter(s => s.requirement.startsWith('routing')).length}`} hint="handled by fallback" />
            <Stat label="Validation failures" value={`${res.data.scenarios.filter(s => s.requirement.startsWith('validation') && s.completed).length}/${res.data.scenarios.filter(s => s.requirement.startsWith('validation')).length}`} hint="handled" />
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Scenario</TableCell>
                <TableCell>Failure type</TableCell>
                <TableCell>Expected</TableCell>
                <TableCell>Finished</TableCell>
                <TableCell>Path the student took</TableCell>
                <TableCell>Logged</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {res.data.scenarios.map(s => (
                <TableRow key={s.scenario}>
                  <TableCell sx={{fontWeight: 600}}>{s.scenario}</TableCell>
                  <TableCell>{s.requirement}</TableCell>
                  <TableCell>{s.expect}</TableCell>
                  <TableCell>
                    <Verdict ok={s.completed} yes="yes" no="no" />
                  </TableCell>
                  <TableCell>
                    <PathSteps path={s.path} />
                    {s.crashed && (
                      <Typography variant="body2" sx={{color: 'error.main', mt: 0.5, fontFamily: 'var(--code-font)'}}>
                        {s.crashed}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Box sx={{fontFamily: 'var(--code-font)', fontSize: 12}}>{s.fallback_events.join(', ') || '–'}</Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Caveat>
            An unexpected exception in the grader or the AI hint call escapes <code>Engine.submit</code>; through the student web API this shows as a 500 error and the submission is
            lost. A grader that stays unavailable keeps the student on the same level with no fallback. Fixes belong to the engine owners; this page only reports.
          </Caveat>
        </>
      )}
    </Section>
  );
}
