import {Alert, Box, CircularProgress, Container, Tab, Tabs, Typography} from '@mui/material';
import {useEffect, useMemo, useState} from 'react';

import {createHttpClient, type ApiClient} from '@/api/client';
import {createMockClient} from '@/api/mock/mockClient';
import type {DiagnosticQuestion, SkillTree as SkillTreeData} from '@/api/types';

import DiagnosticPlayer from './features/diagnostic/DiagnosticPlayer';
import SkillTree from './features/skilltree/SkillTree';
import StanceRouter from './features/stance/StanceRouter';

const API_BASE_URL: string | undefined = import.meta.env.VITE_API_BASE_URL;

type Loaded<T> =
  | {status: 'loading'}
  | {status: 'error'; message: string}
  | {status: 'ready'; value: T};

function useLoaded<T>(load: () => Promise<T>): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>({status: 'loading'});
  useEffect(() => {
    let cancelled = false;
    load().then(
      value => !cancelled && setState({status: 'ready', value}),
      (e: unknown) =>
        !cancelled &&
        setState({
          status: 'error',
          message: e instanceof Error ? e.message : 'Request failed.',
        })
    );
    return () => {
      cancelled = true;
    };
  }, [load]);
  return state;
}

function Async<T>({state, children}: {state: Loaded<T>; children: (value: T) => React.ReactNode}) {
  if (state.status === 'loading') return <CircularProgress aria-label="Loading" />;
  if (state.status === 'error') return <Alert severity="error">{state.message}</Alert>;
  return <>{children(state.value)}</>;
}

export default function App() {
  const client: ApiClient = useMemo(
    () => (API_BASE_URL ? createHttpClient(API_BASE_URL) : createMockClient()),
    []
  );
  const [tab, setTab] = useState(0);
  const tree = useLoaded<SkillTreeData>(useMemo(() => () => client.getSkillTree(), [client]));
  const diagnostic = useLoaded<DiagnosticQuestion[]>(
    useMemo(() => () => client.getDiagnostic(), [client])
  );

  return (
    <Container maxWidth="lg" sx={{py: 3}}>
      <Typography variant="h4" component="h1" sx={{mb: 1}}>
        CodeAI
      </Typography>
      {!API_BASE_URL && (
        <Alert severity="info" sx={{mb: 2}}>
          Using mock data. Set VITE_API_BASE_URL to use the backend.
        </Alert>
      )}
      <Tabs value={tab} onChange={(_, v: number) => setTab(v)} sx={{mb: 3}}>
        <Tab label="Skill tree" />
        <Tab label="Diagnostic" />
        <Tab label="Next step" />
      </Tabs>
      <Box role="tabpanel">
        {tab === 0 && <Async state={tree}>{value => <SkillTree tree={value} />}</Async>}
        {tab === 1 && (
          <Async state={diagnostic}>
            {value => <DiagnosticPlayer client={client} questions={value} />}
          </Async>
        )}
        {tab === 2 && <StanceRouter client={client} />}
      </Box>
    </Container>
  );
}
