import CheckIcon from '@mui/icons-material/Check';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {Alert, Box, Button, Chip, CircularProgress, Paper, Typography} from '@mui/material';
import {useEffect, useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {CourseView} from '@/api/types';
import SkillTree from './SkillTree';

export function CourseBody({view}: {view: CourseView}) {
  return (
    <Box sx={{display: 'grid', gap: 2.5, gridTemplateColumns: {xs: '1fr', md: 'minmax(0, 7fr) minmax(0, 5fr)'}, alignItems: 'start'}}>
      <Box sx={{gridRow: {md: '1 / span 1'}}}>
        <Typography sx={{fontWeight: 700, mb: 1}}>Your skill tree</Typography>
        <SkillTree concepts={view.concepts} />
      </Box>
      <Box sx={{display: 'grid', gap: 2.5}}>
      <Box>
        <Typography variant="overline" color="text.secondary" sx={{fontWeight: 700}}>Right now</Typography>
        <Typography variant="h5" component="p">{view.now.project}{view.now.isReview ? ' (review)' : ''}{view.now.complete ? ' · finished' : ''}</Typography>
        {view.quest.status === 'applied' && (
          <Typography color="text.secondary" sx={{mt: 0.5}}>
            The readiness quest set your starting spot{view.quest.seeded.length > 0 ? `, and showed you already know ${view.quest.seeded.join(', ')}` : ''}.
          </Typography>
        )}
      </Box>

      <Box component="ol" aria-label="Course topics" sx={{listStyle: 'none', p: 0, m: 0, display: 'grid', gap: 1.5}}>
        {view.topics.map((t, i) => (
          <Paper component="li" key={t.id} variant="outlined" sx={{p: 2, borderRadius: '12px', display: 'flex', gap: 2, alignItems: 'center',
            borderColor: t.status === 'current' ? 'primary.main' : 'divider', opacity: t.status === 'upcoming' ? 0.8 : 1}}>
            <Box aria-hidden sx={{width: 40, height: 40, borderRadius: '50%', flex: 'none', display: 'grid', placeItems: 'center', fontWeight: 700,
              border: 2, borderColor: t.status === 'done' ? 'success.main' : t.status === 'current' ? 'primary.main' : 'divider',
              bgcolor: t.status === 'done' ? 'success.main' : 'background.paper', color: t.status === 'done' ? 'background.paper' : 'text.primary'}}>
              {t.status === 'done' ? <CheckIcon fontSize="small" /> : t.status === 'current' ? <PlayArrowIcon fontSize="small" /> : i + 1}
            </Box>
            <Box sx={{flex: 1, minWidth: 0}}>
              <Typography sx={{fontWeight: 700}}>{t.title}</Typography>
              <Typography variant="body2" color="text.secondary">{t.concepts.join(' · ')}</Typography>
            </Box>
            <Chip size="small" label={t.status === 'done' ? 'Done' : t.status === 'current' ? 'You are here' : 'Up next'}
              color={t.status === 'done' ? 'success' : t.status === 'current' ? 'primary' : 'default'} variant={t.status === 'upcoming' ? 'outlined' : 'filled'} />
          </Paper>
        ))}
      </Box>

      {view.reviewsDone.length > 0 && (
        <Box>
          <Typography sx={{fontWeight: 700, mb: 0.5}}>Reviews you've finished</Typography>
          <Box sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>{view.reviewsDone.map((r, i) => <Chip key={i} size="small" label={r} variant="outlined" color="success" />)}</Box>
        </Box>
      )}

      {view.nextStep && <Alert severity="info">{view.nextStep}</Alert>}
      </Box>
    </Box>
  );
}

export default function CoursePage({client, studentId, onBack}: {client: ApiClient; studentId: string; onBack: () => void}) {
  const [view, setView] = useState<CourseView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { client.getCourse(studentId).then(setView, e => setErr(e instanceof Error ? e.message : 'Something went wrong.')); }, [client, studentId]);
  return (
    <Box sx={{display: 'grid', gap: 2, maxWidth: 1280, mx: 'auto', py: 1}}>
      <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
        <Typography variant="h4" component="h2" sx={{flex: 1}}>My course</Typography>
        <Button variant="contained" onClick={onBack}>Back to my lesson</Button>
      </Box>
      {err && <Alert severity="error">{err}</Alert>}
      {!view && !err && <CircularProgress aria-label="Loading" />}
      {view && <CourseBody view={view} />}
    </Box>
  );
}
