import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {Alert, Box, Typography} from '@mui/material';

import type {Outcome} from '@/api/types';
import RubberDuck from './RubberDuck';

const HEADLINE: Record<Outcome['status'], string> = {
  passed: 'Nice work, that passes.',
  failed: 'Not quite yet.',
  timeout: 'Your code took too long to finish.',
  syntax_error: "Python couldn't read your code.",
  import_error: "Your code couldn't be loaded.",
  ungraded: "We couldn't check this one.",
};

export default function Results({outcome}: {outcome: Outcome}) {
  return (
    <Box role="status" aria-live="polite" sx={{display: 'grid', gap: 1.5}}>
      <Alert icon={outcome.passed ? <CheckCircleIcon /> : <ErrorOutlineIcon />} severity={outcome.passed ? 'success' : outcome.status === 'ungraded' ? 'warning' : 'error'}>
        <Typography sx={{fontWeight: 700}}>{HEADLINE[outcome.status]}</Typography>
        {outcome.messages.length > 0 && (
          <Box component="ul" sx={{m: 0, mt: 0.5, pl: 2.5}}>
            {outcome.messages.map((m, i) => <li key={i}>{m}</li>)}
          </Box>
        )}
      </Alert>
      {outcome.hint && (
        <Box sx={{display: 'flex', gap: 1.25, p: 1.5, borderRadius: '10px', border: 1, borderColor: 'primary.main', bgcolor: 'action.hover'}}>
          <RubberDuck title="Ducky, your helper" />
          <Box>
            <Typography variant="caption" sx={{fontWeight: 700, color: 'primary.dark'}}>
              {outcome.hintSource === 'ai' ? 'Hint from Ducky, your AI tutor' : 'Hint from Ducky'}
            </Typography>
            <Typography>{outcome.hint}</Typography>
          </Box>
        </Box>
      )}
      {outcome.stageChanges.map(c => (
        <Box key={c.concept} sx={{display: 'flex', gap: 1, alignItems: 'center', color: c.newStage > c.oldStage ? 'success.main' : 'text.secondary'}}>
          <TrendingUpIcon fontSize="small" />
          <Typography variant="body2">
            {c.conceptName}: {c.oldStageName} → <strong>{c.newStageName}</strong>
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
