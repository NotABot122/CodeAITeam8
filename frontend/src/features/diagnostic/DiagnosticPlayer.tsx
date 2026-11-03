// Plays diagnostic questions one at a time. The backend can answer a
// submission with a follow-up probe, which is queued right after the current
// question.
//
// Adapted from code-dot-org/code-dot-org
//   apps/src/adaptive/views/steps/QuestionsStep.tsx (Apache-2.0).
// Changed: no retry-until-correct (a diagnostic needs the first answer, so a
// lucky guess stays visible), no Quiz components or Redux, answers go to the
// ApiClient, and follow-up probes extend the queue.

import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {useEffect, useRef, useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {DiagnosticQuestion} from '@/api/types';

/** Choice id sent when the student types their own answer. */
export const OTHER_CHOICE_ID = 'other';

interface DiagnosticPlayerProps {
  client: ApiClient;
  questions: DiagnosticQuestion[];
  onComplete?: () => void;
}

export default function DiagnosticPlayer({
  client,
  questions,
  onComplete,
}: DiagnosticPlayerProps) {
  const [queue, setQueue] = useState(questions);
  const [index, setIndex] = useState(0);
  const [choiceId, setChoiceId] = useState('');
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [done, setDone] = useState(false);
  const shownAt = useRef(Date.now());
  const headingRef = useRef<HTMLHeadingElement>(null);
  const question = queue[index];

  useEffect(() => {
    shownAt.current = Date.now();
    headingRef.current?.focus();
  }, [index]);

  if (done) {
    return <Alert severity="success">Diagnostic complete. Nice work.</Alert>;
  }
  if (!question) return null;

  const isOpenEnded = question.type === 'openEnded';
  const usingOther = choiceId === OTHER_CHOICE_ID;
  const canSubmit = isOpenEnded
    ? text.trim() !== ''
    : choiceId !== '' && (!usingOther || text.trim() !== '');

  const submit = async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const result = await client.submitAnswer({
        questionId: question.id,
        choiceId: isOpenEnded ? '' : choiceId,
        text: isOpenEnded || usingOther ? text : undefined,
        latencyMs: Date.now() - shownAt.current,
      });
      const next = [...queue];
      if (result.followUp) next.splice(index + 1, 0, result.followUp);
      setQueue(next);
      setChoiceId('');
      setText('');
      if (index + 1 >= next.length) {
        setDone(true);
        onComplete?.();
      } else {
        setIndex(index + 1);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save your answer.');
    } finally {
      setSubmitting(false);
    }
  };

  const isLast = index + 1 >= queue.length;

  return (
    <Stack spacing={2} sx={{maxWidth: 640}}>
      <Typography variant="caption" color="text.secondary">
        Question {index + 1} of {queue.length}
        {question.type === 'openEnded' && question.followUpTo
          ? ' (follow-up)'
          : ''}
      </Typography>
      <Typography variant="h6" tabIndex={-1} ref={headingRef}>
        {question.prompt}
      </Typography>

      {question.type === 'multipleChoice' ? (
        <FormControl>
          <RadioGroup
            value={choiceId}
            onChange={e => setChoiceId(e.target.value)}
            aria-label={question.prompt}
          >
            {question.choices.map(choice => (
              <FormControlLabel
                key={choice.id}
                value={choice.id}
                control={<Radio />}
                label={choice.text}
              />
            ))}
            {question.allowOther && (
              <FormControlLabel
                value={OTHER_CHOICE_ID}
                control={<Radio />}
                label="Other"
              />
            )}
          </RadioGroup>
          {question.allowOther && usingOther && (
            <TextField
              size="small"
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder={question.allowOther.placeholder}
              slotProps={{htmlInput: {'aria-label': 'Your answer'}}}
            />
          )}
        </FormControl>
      ) : (
        <TextField
          multiline
          minRows={4}
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={question.placeholder}
          slotProps={{htmlInput: {'aria-label': 'Your answer'}}}
        />
      )}

      {error && <Alert severity="error">{error}</Alert>}
      <Box>
        <Button
          variant="contained"
          disabled={!canSubmit || submitting}
          onClick={submit}
        >
          {isLast ? 'Submit' : 'Next'}
        </Button>
      </Box>
    </Stack>
  );
}
