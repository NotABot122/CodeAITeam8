import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import TranslateIcon from '@mui/icons-material/Translate';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {Alert, Box, Typography} from '@mui/material';

import type {Outcome} from '@/api/types';

const HEADLINE: Record<Outcome['status'], string> = {
  passed: 'Nice work, that passes.',
  failed: 'Not quite yet.',
  timeout: 'Your code took too long to finish.',
  syntax_error: "Python couldn't read your code.",
  import_error: "Your code couldn't be loaded.",
  ungraded: "We couldn't check this one.",
  // Hint requests don't come through Results; these keep the record complete.
  hint: 'Here is a hint.',
  no_hints: 'No hints left for this one.',
  complete: "You've finished the project.",
};

/** A hint, after a failed run or on request. `note` is an extra line under it. */
export function HintCard({hint, source, note}: {hint: string; source: Outcome['hintSource']; note?: string}) {
  return (
    <Box sx={{display: 'flex', gap: 1.25, p: 1.5, borderRadius: '10px', border: 1, borderColor: 'primary.main', bgcolor: 'action.hover'}}>
      <LightbulbOutlinedIcon color="primary" />
      <Box>
        <Typography variant="caption" sx={{fontWeight: 700, color: 'primary.main'}}>
          {source === 'ai' ? 'Hint from your AI tutor' : 'Hint'}
        </Typography>
        <Typography>{hint}</Typography>
        {note && <Typography variant="caption" color="text.secondary" component="p" sx={{mt: 0.5}}>{note}</Typography>}
      </Box>
    </Box>
  );
}

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
      {outcome.explanation && (
        <Box sx={{display: 'flex', gap: 1.25, p: 1.5, borderRadius: '10px', border: 1, borderColor: 'divider', bgcolor: 'background.paper'}}>
          <TranslateIcon color="action" />
          <Box>
            <Typography variant="caption" sx={{fontWeight: 700}}>
              What this error means{outcome.explanation.line ? ` (line ${outcome.explanation.line})` : ''}
            </Typography>
            <Typography>{outcome.explanation.text}</Typography>
          </Box>
        </Box>
      )}
      {outcome.mistake && (
        <Box sx={{display: 'flex', gap: 1.25, p: 1.5, borderRadius: '10px', border: 1, borderColor: 'secondary.main', bgcolor: 'action.hover'}}>
          <ManageSearchIcon color="secondary" />
          <Box>
            <Typography variant="caption" sx={{fontWeight: 700, color: 'secondary.main'}}>Where to look</Typography>
            <Typography>{outcome.mistake.tip}</Typography>
          </Box>
        </Box>
      )}
      {outcome.hint && <HintCard hint={outcome.hint} source={outcome.hintSource} />}
      {!outcome.passed && !outcome.hint && !outcome.explanation && !outcome.mistake && ['failed', 'timeout'].includes(outcome.status) && (
        <Typography variant="body2" color="text.secondary">Read the messages above and try again. The Hint button is there if you want it.</Typography>
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
