import {Alert, AppBar, Box, Chip, Container, Tab, Tabs, Toolbar, Typography} from '@mui/material';
import {useEffect, useState} from 'react';
import {api, type Health, type TabId} from './api';
import Fallback from './pages/Fallback';
import Hints from './pages/Hints';
import Overview from './pages/Overview';
import Rating from './pages/Rating';
import Safety from './pages/Safety';
import Validation from './pages/Validation';

const TABS: {id: TabId; label: string}[] = [
  {id: 'overview', label: 'Requirements'},
  {id: 'validation', label: 'Validation (E01)'},
  {id: 'fallback', label: 'Fallback (E07)'},
  {id: 'safety', label: 'Content filtering (E08)'},
  {id: 'hints', label: 'Hints (E12)'},
  {id: 'rating', label: 'Human rating'},
];

function tabFromHash(): TabId {
  const h = window.location.hash.replace('#', '') as TabId;
  return TABS.some(t => t.id === h) ? h : 'overview';
}

export default function App() {
  const [tab, setTab] = useState<TabId>(tabFromHash);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e: Error) => setHealthError(e.message));
    const onHash = () => setTab(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (t: TabId) => {
    window.location.hash = t;
    setTab(t);
  };

  return (
    <Box sx={{minHeight: '100vh'}}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{borderBottom: 1, borderColor: 'divider'}}>
        <Toolbar sx={{gap: 2}}>
          <Typography variant="h6" sx={{color: 'primary.main'}}>
            CodeAI Evaluation Console
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{flex: 1}}>
            Is the adaptive engine ready? Evidence for each customer requirement, live.
          </Typography>
          {health && <Chip size="small" color={health.ai ? 'success' : 'default'} label={health.ai ? 'Bedrock connected' : `Bedrock off (${health.ai_reason})`} />}
        </Toolbar>
        <Tabs value={tab} onChange={(_, v: TabId) => go(v)} variant="scrollable" sx={{px: 2}}>
          {TABS.map(t => (
            <Tab key={t.id} value={t.id} label={t.label} />
          ))}
        </Tabs>
      </AppBar>
      <Container maxWidth="xl" sx={{py: 3}}>
        {healthError && (
          <Alert severity="error" sx={{mb: 2}}>
            {healthError} Start it with <code>python -m evaluation.harness.console_server</code>.
          </Alert>
        )}
        {tab === 'overview' && <Overview onOpen={go} />}
        {tab === 'validation' && <Validation />}
        {tab === 'fallback' && <Fallback />}
        {tab === 'safety' && <Safety ai={health?.ai ?? false} />}
        {tab === 'hints' && <Hints ai={health?.ai ?? false} />}
        {tab === 'rating' && <Rating />}
      </Container>
    </Box>
  );
}
