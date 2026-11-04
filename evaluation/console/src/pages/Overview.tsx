import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import {Box, Button, CircularProgress, Paper, Typography} from '@mui/material';
import type {OverviewItem, TabId} from '../api';
import {StatusChip} from '../ui';

// One card per customer requirement. Wording comes from console_server.overview().
export default function Overview({items, onOpen}: {items: OverviewItem[]; onOpen: (t: TabId) => void}) {
  if (!items.length) return <Box sx={{display: 'grid', placeItems: 'center', minHeight: '40vh'}}><CircularProgress aria-label="Loading" /></Box>;
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      <Typography variant="body2" color="text.secondary">
        Each card is a requirement from the CodeAI Vision document, with what we measured and what is still missing. Open a card to see the evidence and try it live.
      </Typography>
      {items.map(item => (
        <Paper key={item.id} variant="outlined" sx={{p: 2.5, borderRadius: '12px', display: 'flex', gap: 2, alignItems: {md: 'center'}, flexDirection: {xs: 'column', md: 'row'}}}>
          <Box sx={{width: 110, flex: 'none'}}>
            <StatusChip status={item.status} />
          </Box>
          <Box sx={{flex: 1}}>
            <Typography sx={{fontWeight: 600}}>{item.requirement}</Typography>
            {item.metric && <Typography variant="body2" sx={{mt: 0.5}}>{item.metric}</Typography>}
            {item.caveat && <Typography variant="body2" sx={{mt: 0.5, color: 'warning.main'}}>{item.caveat}</Typography>}
          </Box>
          <Button variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => onOpen(item.tab)} sx={{flex: 'none'}}>
            See evidence
          </Button>
        </Paper>
      ))}
    </Box>
  );
}
