import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {Box, Paper, Typography} from '@mui/material';
import type {ReactNode} from 'react';

import type {ProjectMatch} from '@/api/types';

function Reasons({icon, title, lines}: {icon: ReactNode; title: string; lines: string[]}) {
  if (!lines.length) return null;
  return (
    <Box sx={{display: 'flex', gap: 1.25, alignItems: 'flex-start'}}>
      <Box aria-hidden sx={{mt: 0.25, color: 'secondary.main', display: 'flex'}}>{icon}</Box>
      <Box>
        <Typography sx={{fontWeight: 700}}>{title}</Typography>
        <Box component="ul" sx={{m: 0, pl: 2.5, '& li': {mt: 0.25}}}>
          {lines.map((l, i) => <Typography component="li" key={i} color="text.secondary">{l}</Typography>)}
        </Box>
      </Box>
    </Box>
  );
}

/** Why this project was suggested: interests picked the story, the readiness check picked the start. */
export default function MatchCard({match, heading = 'Why this project fits you'}: {match: ProjectMatch; heading?: string}) {
  return (
    <Paper variant="outlined" component="section" aria-label={heading} sx={{p: 2, borderRadius: '12px', borderColor: 'secondary.main', display: 'grid', gap: 1.5}}>
      <Box>
        <Typography variant="overline" color="secondary" sx={{fontWeight: 700, lineHeight: 1.4}}>{heading}</Typography>
        <Typography sx={{fontWeight: 700, fontSize: 18}}>{match.title}</Typography>
        {match.pitch && <Typography color="text.secondary">{match.pitch}</Typography>}
      </Box>
      <Reasons icon={<FavoriteBorderIcon fontSize="small" />} title="Your interests" lines={match.because} />
      <Reasons icon={<TrendingUpIcon fontSize="small" />} title="Your skills" lines={match.fit} />
    </Paper>
  );
}
