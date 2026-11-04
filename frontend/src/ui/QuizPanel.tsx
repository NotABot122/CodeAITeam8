import {Alert, Box, Button, FormControlLabel, Paper, Radio, RadioGroup, TextField, Typography} from '@mui/material';

import type {QuestionResult, QuizQuestion} from '@/api/types';

export type QuizAnswers = Record<string, number | string>;

export function quizReady(questions: QuizQuestion[], answers: QuizAnswers) {
  return questions.every(q => (q.type === 'predict' ? typeof answers[q.id] === 'number' : String(answers[q.id] ?? '').trim().length > 0));
}

export default function QuizPanel({questions, answers, onChange, results, disabled}: {
  questions: QuizQuestion[]; answers: QuizAnswers; onChange: (a: QuizAnswers) => void;
  results: QuestionResult[]; disabled?: boolean;
}) {
  return (
    <Box sx={{display: 'grid', gap: 2}}>
      {questions.map((q, n) => {
        const r = results.find(x => x.id === q.id);
        return (
          <Paper key={q.id} variant="outlined" component="fieldset" sx={{p: 2, m: 0, borderRadius: '12px', minWidth: 0,
            borderColor: r?.correct === true ? 'success.main' : r?.correct === false ? 'error.main' : 'divider'}}>
            <Typography component="legend" sx={{fontWeight: 700, px: 0.5}}>{n + 1}. {q.prompt}</Typography>
            {q.code && (
              <Box component="pre" sx={{m: 0, my: 1.5, p: 1.5, borderRadius: '8px', bgcolor: 'action.hover', overflowX: 'auto', fontFamily: 'var(--code-font)', fontSize: 13, lineHeight: 1.6}}>{q.code}</Box>
            )}
            {q.type === 'predict' ? (
              <RadioGroup value={typeof answers[q.id] === 'number' ? String(answers[q.id]) : ''} onChange={e => onChange({...answers, [q.id]: Number(e.target.value)})}>
                {(q.choices ?? []).map((c, i) => (
                  <FormControlLabel key={i} value={String(i)} disabled={disabled} control={<Radio />} label={<Box component="span" sx={{fontFamily: 'var(--code-font)'}}>{c}</Box>} />
                ))}
              </RadioGroup>
            ) : (
              <TextField multiline minRows={3} fullWidth disabled={disabled} label="Your answer" value={String(answers[q.id] ?? '')}
                slotProps={{htmlInput: {maxLength: 2000}}} onChange={e => onChange({...answers, [q.id]: e.target.value})} />
            )}
            {r && r.type === 'predict' && r.correct === false && r.explanation && <Alert severity="info" sx={{mt: 1.5}}>{r.explanation}</Alert>}
            {r && r.type === 'predict' && r.correct === true && <Alert severity="success" sx={{mt: 1.5}}>Right.</Alert>}
            {r && r.type === 'explain' && r.feedback && <Alert severity="info" sx={{mt: 1.5}}>{r.score !== null && `Score ${r.score} of 3. `}{r.feedback}</Alert>}
          </Paper>
        );
      })}
    </Box>
  );
}

export function SubmitQuiz({onClick, disabled, busy}: {onClick: () => void; disabled: boolean; busy: boolean}) {
  return <Button variant="contained" color="secondary" size="large" disabled={disabled || busy} onClick={onClick}>{busy ? 'Checking…' : 'Check my answers'}</Button>;
}
