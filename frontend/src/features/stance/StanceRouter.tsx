import {Alert, Button, Chip, Paper, Stack, Typography} from '@mui/material';
import {useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {NextStep, Stance} from '@/api/types';

import DiagnosticPlayer from '../diagnostic/DiagnosticPlayer';
import LessonView from '../lesson/LessonView';

const STANCE_LABEL: {[stance in Stance]: string} = {
  STANCE_REINFORCE: 'Reinforce',
  STANCE_ADVANCE: 'Advance',
  STANCE_BRIDGE: 'Bridge',
  STANCE_PROJECT_SYNTHESIS: 'Project',
};

function StepBody({client, step}: {client: ApiClient; step: NextStep}) {
  switch (step.stance) {
    case 'STANCE_REINFORCE':
      return <DiagnosticPlayer client={client} questions={[step.question]} />;
    case 'STANCE_ADVANCE':
      return (
        <LessonView
          client={client}
          lessonId={step.lesson.id}
          title={step.lesson.title}
          instructions={step.lesson.instructions}
          starterCode={step.lesson.starterCode}
        />
      );
    case 'STANCE_BRIDGE':
      return (
        <LessonView
          client={client}
          lessonId={step.challenge.id}
          title={step.challenge.title}
          instructions={step.challenge.prompt}
          starterCode=""
        />
      );
    case 'STANCE_PROJECT_SYNTHESIS':
      return (
        <Paper variant="outlined" sx={{p: 2, maxWidth: 640}}>
          <Typography variant="h6">{step.project.title}</Typography>
          <Typography variant="body2">{step.project.brief}</Typography>
          <Typography variant="caption" color="text.secondary">
            The project studio is not built yet.
          </Typography>
        </Paper>
      );
  }
}

/** Asks the backend what to do next and shows the screen for its stance. */
export default function StanceRouter({client}: {client: ApiClient}) {
  const [step, setStep] = useState<NextStep>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  // A new key remounts the body, so each step starts with fresh state.
  const [count, setCount] = useState(0);

  const load = async () => {
    setLoading(true);
    setError(undefined);
    try {
      setStep(await client.getNextStep());
      setCount(c => c + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the next step.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} sx={{alignItems: 'center'}}>
        <Button variant="contained" onClick={load} disabled={loading}>
          {step ? 'Next step' : 'Start'}
        </Button>
        {step && (
          <>
            <Chip label={STANCE_LABEL[step.stance]} color="primary" size="small" />
            <Typography variant="body2" color="text.secondary">
              {step.rationale}
            </Typography>
          </>
        )}
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {step && <StepBody key={count} client={client} step={step} />}
    </Stack>
  );
}
