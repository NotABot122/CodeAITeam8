import AltRouteIcon from '@mui/icons-material/AltRoute';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TerminalIcon from '@mui/icons-material/Terminal';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import {Box, Button, Container, Paper, Typography} from '@mui/material';
import type {ReactNode} from 'react';

export const GRADES = [9, 10, 11, 12] as const;

function Step({n, icon, title, children}: {n: number; icon: ReactNode; title: string; children: ReactNode}) {
  return (
    <Box component="li" sx={{display: 'flex', gap: 1.5, alignItems: 'flex-start'}}>
      <Box aria-hidden sx={{flex: 'none', width: 40, height: 40, borderRadius: '50%', display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        {icon}
      </Box>
      <Box>
        <Typography sx={{fontWeight: 700}}>{n}. {title}</Typography>
        <Typography color="text.secondary">{children}</Typography>
      </Box>
    </Box>
  );
}

/** The front page: what happens, the student's grade, then the readiness check. */
export default function Landing({grade, onGrade, onStart, onSkip, onImport, resume}: {
  grade: number | null; onGrade: (g: number) => void; onStart: () => void; onSkip: () => void;
  /** Skip the readiness check with an earlier lesson's results. */
  onImport: () => void;
  /** A saved student on this browser: where they left off. */
  resume: {label: string; onResume: () => void} | null;
}) {
  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="md" sx={{py: 1.25, display: 'flex', alignItems: 'baseline', gap: 1.5, flexWrap: 'wrap'}}>
          <Typography component="p" variant="h5" sx={{flex: 1}}>CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Python with data</Typography></Typography>
          <Button color="inherit" onClick={onSkip}>Skip to coding</Button>
          <Button color="inherit" href="#/teacher">For teachers</Button>
        </Container>
      </Box>
      <Container maxWidth="md" sx={{py: {xs: 3, sm: 5}, display: 'grid', gap: 3}}>
        <Box>
          <Typography variant="h3" component="h1" sx={{fontSize: {xs: 32, sm: 44}}}>Find your path in Python</Typography>
          <Typography sx={{mt: 1.5, fontSize: 18, maxWidth: 640}}>
            Start with a short readiness check. We use your answers, your grade and the CS standards for your grade
            to choose the lesson pathway that fits you, so you don't repeat what you know or skip what you need.
          </Typography>
        </Box>

        {resume && (
          <Paper variant="outlined" component="section" aria-label="Continue" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px', borderColor: 'primary.main',
            display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap'}}>
            <Box sx={{flex: 1, minWidth: 220}}>
              <Typography sx={{fontWeight: 700}}>Welcome back</Typography>
              <Typography color="text.secondary">Pick up where you left off: {resume.label}.</Typography>
            </Box>
            <Button variant="contained" size="large" startIcon={<PlayArrowIcon />} onClick={resume.onResume}>Continue where you left off</Button>
          </Paper>
        )}

        <Paper variant="outlined" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px'}}>
          <Box component="ol" sx={{listStyle: 'none', p: 0, m: 0, display: 'grid', gap: 2}}>
            <Step n={1} icon={<FactCheckOutlinedIcon />} title="Take the readiness check">
              About 15 minutes of short questions on reading data, if statements, loops and functions. It isn't graded.
            </Step>
            <Step n={2} icon={<AltRouteIcon />} title="Get your pathway">
              Your AI guide reads your answers and picks where you start: a quick review, step by step, or straight to the bigger project.
            </Step>
            <Step n={3} icon={<TerminalIcon />} title="Build a real project">
              Write Python that pulls weather data, makes decisions and builds a report, with hints when you need them.
            </Step>
          </Box>
        </Paper>

        <Paper variant="outlined" component="section" aria-labelledby="grade-label" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px', display: 'grid', gap: 2}}>
          <Box component="fieldset" sx={{border: 0, p: 0, m: 0}}>
            <Typography component="legend" id="grade-label" sx={{fontWeight: 700, mb: 1}}>What grade are you in?</Typography>
            <Box role="radiogroup" aria-labelledby="grade-label" sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
              {GRADES.map(g => (
                <Button key={g} role="radio" aria-checked={grade === g} variant={grade === g ? 'contained' : 'outlined'} onClick={() => onGrade(g)}
                  sx={{minWidth: 88}}>
                  Grade {g}
                </Button>
              ))}
            </Box>
          </Box>
          <Box sx={{display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap'}}>
            <Button variant="contained" color="secondary" size="large" disabled={grade === null} onClick={onStart}>
              {resume ? 'Start a new readiness check' : 'Start the readiness check'}
            </Button>
            {grade === null && <Typography variant="body2" color="text.secondary">Pick your grade first.</Typography>}
          </Box>
        </Paper>
        <Paper variant="outlined" component="section" aria-labelledby="import-label" sx={{p: {xs: 2, sm: 3}, borderRadius: '12px',
          display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap'}}>
          <Box sx={{flex: 1, minWidth: 240}}>
            <Typography id="import-label" sx={{fontWeight: 700}}>Already did a lesson like this?</Typography>
            <Typography color="text.secondary">Import your results from an earlier lesson and skip the readiness check.</Typography>
          </Box>
          <Button variant="outlined" size="large" startIcon={<UploadFileIcon />} onClick={onImport}>Import my results</Button>
        </Paper>
      </Container>
    </Box>
  );
}
