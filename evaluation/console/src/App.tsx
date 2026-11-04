import CheckIcon from '@mui/icons-material/Check';
import ListAltIcon from '@mui/icons-material/ListAlt';
import PriorityHighIcon from '@mui/icons-material/PriorityHigh';
import RemoveIcon from '@mui/icons-material/Remove';
import {Alert, Box, Container, Typography} from '@mui/material';
import {useEffect, useState} from 'react';
import {api, type Health, type OverviewItem, type Status, type TabId} from './api';
import Fallback from './pages/Fallback';
import Hints from './pages/Hints';
import Overview from './pages/Overview';
import Rating from './pages/Rating';
import Safety from './pages/Safety';
import Validation from './pages/Validation';

// Same layout as the student UI (frontend/src/App.tsx): purple header, then a left-to-right path.
// Each step is one question the customer asked; its circle shows the answer so far.
const STEPS: {id: TabId; title: string; item?: string}[] = [
  {id: 'validation', title: 'Grading', item: 'validation_agreement'},
  {id: 'fallback', title: 'When things fail', item: 'fallback'},
  {id: 'safety', title: 'Safety filters', item: 'filtering'},
  {id: 'hints', title: 'Hints', item: 'content_signoff'},
  {id: 'rating', title: 'Teacher review'},
];

function tabFromHash(): TabId {
  const h = window.location.hash.replace('#', '') as TabId;
  return h === 'overview' || STEPS.some(s => s.id === h) ? h : 'overview';
}

const RING: Record<Status, string> = {met: 'success.main', partial: 'warning.main', not_met: 'error.main', not_tested: 'divider'};

function Step({n, title, status, active, onClick}: {n: number | 'summary'; title: string; status?: Status; active: boolean; onClick: () => void}) {
  const color = status ? RING[status] : 'divider';
  const icon = status === 'met' ? <CheckIcon fontSize="small" /> : status === 'not_met' ? <PriorityHighIcon fontSize="small" /> : status === 'partial' ? <RemoveIcon fontSize="small" /> : n === 'summary' ? <ListAltIcon fontSize="small" /> : n;
  return (
    <Box component="button" onClick={onClick} aria-current={active ? 'page' : undefined}
      sx={{all: 'unset', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', width: 112, textAlign: 'center', '&:focus-visible .circle': {outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2}}}>
      <Box className="circle" aria-hidden
        sx={{width: 40, height: 40, borderRadius: '50%', display: 'grid', placeItems: 'center', fontWeight: 700, border: 2, borderColor: active ? 'primary.main' : color,
          bgcolor: active ? 'primary.main' : 'background.paper', color: active ? 'primary.contrastText' : status && status !== 'not_tested' ? color : 'text.secondary',
          boxShadow: active ? '0 0 0 4px rgba(76,66,207,.18)' : 'none'}}>
        {icon}
      </Box>
      <Typography variant="caption" sx={{mt: 0.5, lineHeight: 1.2, fontWeight: active ? 700 : 400}}>{title}</Typography>
    </Box>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabId>(tabFromHash);
  const [health, setHealth] = useState<Health | null>(null);
  const [items, setItems] = useState<OverviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e: Error) => setError(e.message));
    api.overview().then(o => setItems(o.items)).catch(() => undefined);
    const onHash = () => setTab(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (t: TabId) => {
    window.location.hash = t;
    setTab(t);
    window.scrollTo({top: 0});
  };
  const statusOf = (id?: string) => items.find(i => i.id === id)?.status;

  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="xl" sx={{display: 'flex', alignItems: 'center', gap: 2, py: 1.25}}>
          <Typography component="h1" variant="h5" sx={{flex: 1, display: 'flex', gap: 1.5, alignItems: 'baseline', flexWrap: 'wrap', cursor: 'pointer'}} onClick={() => go('overview')}>
            CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Is the adaptive lesson ready?</Typography>
          </Typography>
          {health && (
            <Typography variant="body2" sx={{opacity: 0.9}}>
              {health.ai ? 'Live AI on' : 'Live AI off'}
            </Typography>
          )}
        </Container>
      </Box>
      <Container maxWidth="xl" sx={{py: 2}}>
        <Box component="nav" aria-label="Evaluation steps" sx={{display: 'flex', alignItems: 'flex-start', gap: 0.5, overflowX: 'auto', py: 1, mb: 1}}>
          <Step n="summary" title="Summary" active={tab === 'overview'} onClick={() => go('overview')} />
          {STEPS.map((s, i) => (
            <Box key={s.id} sx={{display: 'flex', alignItems: 'flex-start'}}>
              <Box aria-hidden sx={{width: 20, height: 2, bgcolor: 'divider', mt: '19px', flex: 'none'}} />
              <Step n={i + 1} title={s.title} status={statusOf(s.item)} active={tab === s.id} onClick={() => go(s.id)} />
            </Box>
          ))}
        </Box>
        {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
        {tab === 'overview' && <Overview items={items} onOpen={go} />}
        {tab === 'validation' && <Validation />}
        {tab === 'fallback' && <Fallback />}
        {tab === 'safety' && <Safety ai={health?.ai ?? false} />}
        {tab === 'hints' && <Hints ai={health?.ai ?? false} />}
        {tab === 'rating' && <Rating />}
      </Container>
    </Box>
  );
}
