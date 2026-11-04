import {Box, Button, Paper, Stack, Typography} from '@mui/material';
import {api, type Status, type TabId} from '../api';
import {Loading, Section, StatusChip, useLoad} from '../ui';

const ORDER: Status[] = ['not_met', 'partial', 'met', 'not_tested'];

export default function Overview({onOpen}: {onOpen: (t: TabId) => void}) {
  const {data, error, loading} = useLoad(api.overview);
  if (!data) return <Loading error={error} loading={loading} />;
  const counts = ORDER.map(s => ({s, n: data.items.filter(i => i.status === s).length}));

  return (
    <>
      <Section
        title="Customer requirements vs. evidence"
        subtitle={
          <>
            Requirements are quoted from the CodeAI Vision document (MVP success criteria, Definition of Done, business constraints). Each row links to the test that produced the
            evidence. Engine under test: <code>proto-branch</code> (also merged into <code>frontend</code>), unchanged.
          </>
        }
      >
        <Stack direction="row" spacing={1} sx={{mb: 2}}>
          {counts.map(c => (
            <Stack key={c.s} direction="row" spacing={0.5} alignItems="center">
              <StatusChip status={c.s} />
              <Typography variant="body2">× {c.n}</Typography>
            </Stack>
          ))}
        </Stack>
        <Stack spacing={1.5}>
          {data.items.map(item => (
            <Paper key={item.id} variant="outlined" sx={{p: 2}}>
              <Stack direction={{xs: 'column', md: 'row'}} spacing={2} alignItems={{md: 'center'}}>
                <Box sx={{width: 110}}>
                  <StatusChip status={item.status} />
                </Box>
                <Box sx={{flex: 1}}>
                  <Typography sx={{fontWeight: 600}}>{item.requirement}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {item.source}
                  </Typography>
                  {item.metric && (
                    <Typography variant="body2" sx={{mt: 0.75, fontFamily: 'var(--code-font)'}}>
                      {item.metric}
                    </Typography>
                  )}
                  <Typography variant="body2" color="text.secondary" sx={{mt: 0.5}}>
                    {item.evidence}
                  </Typography>
                  {item.caveat && (
                    <Typography variant="body2" sx={{mt: 0.5, color: 'warning.main'}}>
                      {item.caveat}
                    </Typography>
                  )}
                </Box>
                <Button variant="outlined" onClick={() => onOpen(item.tab)}>
                  Show evidence
                </Button>
              </Stack>
            </Paper>
          ))}
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{display: 'block', mt: 2}}>
          Built from results/*.json at {new Date(data.generated_at).toLocaleString()}. Synthetic inputs and a draft key; no real students.
        </Typography>
      </Section>
    </>
  );
}
