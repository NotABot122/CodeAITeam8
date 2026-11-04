import {Box, Typography} from '@mui/material';

import type {StudentState} from '@/api/types';

const COLORS = ['#9a9ab0', '#e8a200', '#4c42cf', '#1a7f4b'];

export default function ConceptMeters({state, highlight}: {state: StudentState; highlight: string[]}) {
  return (
    <Box component="section" aria-label="What you're learning">
      <Typography variant="overline" sx={{color: 'text.secondary', fontWeight: 700}}>What you're learning</Typography>
      {state.concepts.map(c => (
        <Box key={c.id} sx={{mt: 1.25, p: 1, borderRadius: 1, bgcolor: highlight.includes(c.id) ? 'action.hover' : 'transparent'}}>
          <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
            <Typography variant="body2" sx={{fontWeight: 600}}>{c.name}</Typography>
            <Typography variant="caption" sx={{color: COLORS[c.stage], fontWeight: 700}}>{c.stageName}</Typography>
          </Box>
          <Box role="meter" aria-label={`${c.name}: ${c.stageName}`} aria-valuemin={0} aria-valuemax={state.maxStage} aria-valuenow={c.stage}
            sx={{display: 'flex', gap: 0.5, mt: 0.5}}>
            {Array.from({length: state.maxStage}, (_, i) => (
              <Box key={i} sx={{flex: 1, height: 6, borderRadius: 3, bgcolor: i < c.stage ? COLORS[c.stage] : 'divider'}} />
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}
