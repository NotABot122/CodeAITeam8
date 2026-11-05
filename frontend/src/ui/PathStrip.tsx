import CheckIcon from '@mui/icons-material/Check';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import FitnessCenterIcon from '@mui/icons-material/FitnessCenter';
import {Box, Typography} from '@mui/material';

import type {PathNode} from '@/api/types';

// A simple left-to-right path (not a hex map): levels as circles, an assigned practice problem as a small
// pill sitting after the level it supports. Circle states follow CodeAI: locked / current (pulse) / done.
function Circle({node}: {node: PathNode}) {
  const done = node.status === 'done';
  const current = node.status === 'current';
  const paused = node.status === 'paused';
  return (
    <Box
      aria-hidden
      sx={{
        width: 38, height: 38, borderRadius: '50%', display: 'grid', placeItems: 'center', fontWeight: 700, flex: 'none',
        border: 2,
        borderColor: done ? 'success.main' : current || paused ? 'primary.main' : 'divider',
        borderStyle: paused ? 'dashed' : 'solid',
        bgcolor: done ? 'success.main' : 'background.paper',
        color: done ? 'background.paper' : current || paused ? 'primary.dark' : 'text.disabled',
        '@keyframes pulse': {'0%': {boxShadow: '0 0 0 0 rgba(76,66,207,.45)'}, '100%': {boxShadow: '0 0 0 12px rgba(76,66,207,0)'}},
        animation: current ? 'pulse 1.6s ease-out infinite' : 'none',
        '@media (prefers-reduced-motion: reduce)': {animation: 'none'},
      }}
    >
      {done ? <CheckIcon fontSize="small" /> : node.status === 'todo' ? <LockOutlinedIcon fontSize="small" /> : node.number}
    </Box>
  );
}

export default function PathStrip({path}: {path: PathNode[]}) {
  const levels = path.filter(n => n.kind === 'level');
  return (
    <Box component="nav" aria-label="Your path" sx={{minWidth: 0, display: 'flex', alignItems: 'flex-start', gap: 0.5, overflowX: 'auto', py: 1}}>
      {levels.map((level, i) => {
        const practice = path.filter(p => p.kind === 'practice' && p.afterLevelId === level.id);
        return (
          <Box key={level.id} sx={{display: 'flex', alignItems: 'flex-start'}}>
            <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 84, textAlign: 'center'}}>
              <Box role="img" aria-label={`Level ${level.number}: ${level.title}, ${level.status === 'todo' ? 'not started' : level.status === 'done' ? 'done' : level.status === 'paused' ? 'paused, you come back to it after the practice' : 'in progress'}`} sx={{position: 'relative'}}>
                <Circle node={level} />
                {practice.map(p => (
                  <Box key={p.id} role="img" title={`Practice: ${p.title}`} aria-label={`Practice: ${p.title}, ${p.status === 'done' ? 'done' : 'in progress'}`}
                    sx={{position: 'absolute', top: -4, right: -8, width: 20, height: 20, borderRadius: '50%', display: 'grid', placeItems: 'center', border: 2, borderColor: 'background.default',
                      bgcolor: p.status === 'done' ? 'success.main' : 'secondary.main', color: '#fff'}}>
                    {p.status === 'done' ? <CheckIcon sx={{fontSize: 12}} /> : <FitnessCenterIcon sx={{fontSize: 12}} />}
                  </Box>
                ))}
              </Box>
              <Typography variant="caption" sx={{mt: 0.5, lineHeight: 1.2, color: level.status === 'todo' ? 'text.disabled' : 'text.primary', fontWeight: level.status === 'current' ? 700 : 400}}>
                {level.title}
              </Typography>
              {level.status === 'paused' && <Typography variant="caption" color="primary" sx={{lineHeight: 1.2, fontStyle: 'italic'}}>Back after practice</Typography>}
            </Box>
            {i < levels.length - 1 && <Box aria-hidden sx={{width: 14, height: 2, bgcolor: 'divider', mt: '18px', flex: 'none'}} />}
          </Box>
        );
      })}
    </Box>
  );
}
