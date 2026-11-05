import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import {Alert, Box, ButtonBase, Chip, Typography} from '@mui/material';

import type {ProjectChoice} from '@/api/types';

/** Pick the story to learn the first topic's skills in. Every project teaches the same four skills. */
export default function ProjectPicker({choices, locked, busy, onPick, onCustom}: {
  choices: ProjectChoice[]; locked: boolean; busy: boolean; onPick: (project: string) => void;
  /** "Make it yours": opens the theme dialog. Left out, the card isn't shown. */
  onCustom?: () => void;
}) {
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      {locked && <Alert severity="info">You've started this project, so it stays your project until you finish it.</Alert>}
      <Box role="radiogroup" aria-label="Your project" sx={{display: 'grid', gap: 1.25, gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'}}}>
        {choices.map(c => (
          <ButtonBase key={c.project} role="radio" aria-checked={c.current} disabled={busy || (locked && !c.current)}
            onClick={() => !c.current && onPick(c.project)}
            sx={{display: 'block', textAlign: 'left', p: 1.75, borderRadius: '12px', border: 2,
              borderColor: c.current ? 'primary.main' : 'divider', bgcolor: c.current ? 'action.selected' : 'background.paper',
              opacity: locked && !c.current ? 0.55 : 1, '&:hover': {borderColor: 'primary.light'},
              '&.Mui-focusVisible': {outline: '2px solid #1aa6a6', outlineOffset: 2}}}>
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap'}}>
              {c.current && <CheckCircleIcon color="primary" fontSize="small" aria-hidden />}
              <Typography sx={{fontWeight: 700}}>{c.title}</Typography>
              {c.suggested && <Chip label="Best match for you" size="small" color="secondary" variant="outlined" />}
            </Box>
            <Typography variant="body2" color="text.secondary">{c.pitch}</Typography>
          </ButtonBase>
        ))}
        {onCustom && (
          <ButtonBase onClick={onCustom} disabled={busy || locked} aria-label="Make it yours: build this project around a theme you pick"
            sx={{display: 'block', textAlign: 'left', p: 1.75, borderRadius: '12px', border: 2, borderStyle: 'dashed', borderColor: 'secondary.main',
              bgcolor: 'background.paper', opacity: locked ? 0.55 : 1, '&:hover': {bgcolor: 'action.hover'},
              '&.Mui-focusVisible': {outline: '2px solid #1aa6a6', outlineOffset: 2}}}>
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.5}}>
              <AutoAwesomeIcon color="secondary" fontSize="small" aria-hidden />
              <Typography sx={{fontWeight: 700}}>Make it yours</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">Tell your AI guide what you're into, and it builds this same project around it.</Typography>
          </ButtonBase>
        )}
      </Box>
      <Typography variant="body2" color="text.secondary">
        Every project teaches the same skills: reading data, if statements, loops and functions. Only the story is different.
      </Typography>
    </Box>
  );
}
