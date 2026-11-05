import {Alert, Box, Button, Chip, CircularProgress, Container, Dialog, DialogContent, DialogTitle, Paper, Tab, Tabs, TextField, Typography} from '@mui/material';
import {useCallback, useEffect, useState} from 'react';

import type {Check, ConceptReport, ContentCheck, Detail, Overview, Row} from './types';

const KEY = 'codeai.teacherToken';
const tokenStore = {
  get: () => { try { return sessionStorage.getItem(KEY) ?? ''; } catch { return ''; } },
  set: (v: string) => { try { sessionStorage.setItem(KEY, v); } catch { /* private mode */ } },
  clear: () => { try { sessionStorage.removeItem(KEY); } catch { /* private mode */ } },
};
const COLORS = ['#9a9ab0', '#e8a200', '#d6456a', '#1a7f4b'];

async function api<T>(path: string, token: string): Promise<T> {
  let res: Response;
  try { res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}${path}`, {headers: {'X-Teacher-Token': token}}); }
  catch { throw Object.assign(new Error("Can't reach the server."), {status: 0}); }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(body?.error?.message ?? 'Something went wrong.'), {status: res.status});
  return body as T;
}

const ago = (iso: string | null) => {
  if (!iso) return 'never';
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};
const STATUS: Record<Row['status'], string> = {quest: 'In the quest', working: 'Coding', finished: 'Finished project', new: 'Not started'};

function StageDots({stage}: {stage: number}) {
  return (
    <Box role="img" aria-label={`Stage ${stage} of 3`} sx={{display: 'flex', gap: 0.4}}>
      {[1, 2, 3].map(i => <Box key={i} sx={{width: 14, height: 6, borderRadius: 3, bgcolor: i <= stage ? COLORS[stage] : 'divider'}} />)}
    </Box>
  );
}

function Distribution({overview}: {overview: Overview}) {
  const total = Math.max(1, overview.summary.total);
  return (
    <Paper variant="outlined" sx={{p: 2, borderRadius: '12px'}}>
      <Typography sx={{fontWeight: 700, mb: 1}}>Where the class stands, by idea</Typography>
      <Box sx={{display: 'grid', gap: 1}}>
        {overview.concepts.map(c => (
          <Box key={c.id} sx={{display: 'grid', gridTemplateColumns: {xs: '110px 1fr', sm: '150px 1fr'}, alignItems: 'center', gap: 1}}>
            <Typography variant="body2">{c.name}</Typography>
            <Box role="img" aria-label={c.counts.map((n, i) => `${n} at ${overview.stageNames[i]}`).join(', ')} sx={{display: 'flex', height: 14, borderRadius: 7, overflow: 'hidden', bgcolor: 'divider'}}>
              {c.counts.map((n, i) => n > 0 && <Box key={i} title={`${overview.stageNames[i]}: ${n}`} sx={{width: `${(n / total) * 100}%`, bgcolor: COLORS[i]}} />)}
            </Box>
          </Box>
        ))}
      </Box>
      <Box sx={{display: 'flex', gap: 2, mt: 1.5, flexWrap: 'wrap'}}>
        {overview.stageNames.map((n, i) => (
          <Box key={n} sx={{display: 'flex', alignItems: 'center', gap: 0.5}}><Box sx={{width: 10, height: 10, borderRadius: '50%', bgcolor: COLORS[i]}} /><Typography variant="caption">{n}</Typography></Box>
        ))}
      </Box>
    </Paper>
  );
}

function ReportConcept({c}: {c: ConceptReport}) {
  return (
    <Paper variant="outlined" sx={{p: 1.5, borderRadius: '10px'}}>
      <Box sx={{display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap'}}>
        <Typography sx={{fontWeight: 700}}>{c.zone}</Typography>
        <Chip size="small" label={c.stage_name} sx={{bgcolor: COLORS[c.stage], color: '#fff'}} />
        <Typography variant="body2" color="text.secondary">confidence {Math.round(c.confidence * 100)}%{c.borderline ? ', borderline' : ''}, {c.questions_asked} questions</Typography>
      </Box>
      {c.mistakes.length > 0 && <Typography variant="body2" sx={{mt: 0.5}}>Mistakes seen: {c.mistakes.join(', ')}</Typography>}
      {c.explain?.text && (
        <Box sx={{mt: 1, p: 1, borderLeft: 3, borderColor: 'primary.main', bgcolor: 'action.hover'}}>
          <Typography variant="caption" color="text.secondary">In the child's own words</Typography>
          <Typography sx={{whiteSpace: 'pre-wrap'}}>{c.explain.text}</Typography>
        </Box>
      )}
      {c.explain && c.explain.flags.length > 0 && <Alert severity="warning" sx={{mt: 1}}>Held back by the content filter: {c.explain.flags.join(', ')}</Alert>}
    </Paper>
  );
}

function DetailView({id, token, onClose}: {id: string; token: string; onClose: () => void}) {
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<Detail>(`/api/teacher/students/${encodeURIComponent(id)}`, token).then(setD, e => setErr(e.message)); }, [id, token]);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" aria-labelledby="detail-title">
      <DialogTitle id="detail-title">Student {id}</DialogTitle>
      <DialogContent sx={{display: 'grid', gap: 2}}>
        {err && <Alert severity="error">{err}</Alert>}
        {!d && !err && <CircularProgress aria-label="Loading" />}
        {d && (
          <>
            <Typography variant="body2" color="text.secondary">Last active {ago(d.lastActive)}</Typography>
            <Box sx={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 1}}>
              {d.concepts.map(c => (
                <Paper key={c.id} variant="outlined" sx={{p: 1, borderRadius: '10px'}}>
                  <Typography variant="body2" sx={{fontWeight: 600}}>{c.name}</Typography>
                  <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}><StageDots stage={c.stage} /><Typography variant="caption" sx={{color: COLORS[c.stage], fontWeight: 700}}>{c.stageName}</Typography></Box>
                </Paper>
              ))}
            </Box>
            {d.nextStep && <Alert severity="info">Recommended next: {d.nextStep}</Alert>}
            <Typography sx={{fontWeight: 700}}>Projects</Typography>
            {d.projects.length === 0 && <Typography color="text.secondary">No coding yet.</Typography>}
            {d.projects.map(p => (
              <Paper key={p.id} variant="outlined" sx={{p: 1.5, borderRadius: '10px'}}>
                <Box sx={{display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap'}}>
                  <Typography sx={{fontWeight: 700}}>{p.title}</Typography>
                  <Chip size="small" label={p.complete ? 'Finished' : `On ${p.current}`} color={p.complete ? 'success' : 'default'} />
                  {p.needsHelp && <Chip size="small" color="warning" label={p.needsHelp} />}
                </Box>
                <Typography variant="body2" sx={{mt: 0.5}}>Passed {p.passed.length}. Tries: {Object.entries(p.attempts).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}. Hints: {Object.entries(p.hintsSeen).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}.</Typography>
                {p.route.length > 0 && <Typography variant="caption" color="text.secondary">Path: {p.route.map(r => `${r.selected ?? 'finish'} (${r.reason})`).join(' → ')}</Typography>}
              </Paper>
            ))}
            {d.quest && (
              <>
                <Typography sx={{fontWeight: 700}}>Readiness quest {d.quest.finished ? '' : '(not finished)'}</Typography>
                <Typography variant="body2">Goal: {d.quest.goal.label}. About {d.quest.minutes_estimate} minutes{d.quest.within_target_minutes ? '' : ' (over the target)'}. {d.quest.ai.used ? `AI read the typed answers (${d.quest.ai.model_id}).` : 'No AI used.'} {d.quest.fixed_order_fallback.used ? `Fixed-order fallback: ${d.quest.fixed_order_fallback.reason}.` : ''}</Typography>
                <Alert severity="info">{d.quest.teacher_note}</Alert>
                {d.quest.content_filter.follow_up && <Alert severity="warning">{d.quest.content_filter.follow_up}</Alert>}
                <Box sx={{display: 'grid', gap: 1}}>{d.quest.concepts.map(c => <ReportConcept key={c.concept} c={c} />)}</Box>
              </>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ContentCheckView({token}: {token: string}) {
  const [res, setRes] = useState<ContentCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = () => { setBusy(true); setErr(null); api<ContentCheck>('/api/teacher/content-check', token).then(setRes, e => setErr(e.message)).finally(() => setBusy(false)); };
  const row = (name: string, c: Check) => (
    <Paper key={name} variant="outlined" sx={{p: 1.5, borderRadius: '10px'}}>
      <Box sx={{display: 'flex', gap: 1, alignItems: 'center'}}><Typography sx={{fontWeight: 700}}>{name}</Typography><Chip size="small" color={c.passed ? 'success' : 'error'} label={c.passed ? 'Passed' : 'Failed'} /></Box>
      {c.problems.map((p, i) => <Typography key={i} variant="body2" color="error">• {p}</Typography>)}
      {c.notices.map((p, i) => <Typography key={i} variant="body2" color="text.secondary">Note: {p}</Typography>)}
    </Paper>
  );
  return (
    <Box sx={{display: 'grid', gap: 1.5}}>
      <Typography color="text.secondary">Checks every lesson's tests, answers and quizzes, and the readiness quest's questions and skill tree. Run it after editing content.</Typography>
      <Box><Button variant="contained" onClick={run} disabled={busy}>{busy ? 'Checking…' : 'Run content check'}</Button></Box>
      {err && <Alert severity="error">{err}</Alert>}
      {res && <>{row('Readiness quest', res.quest)}{res.projects.map(p => row(p.project ?? '', p))}</>}
    </Box>
  );
}

export default function TeacherApp({onExit}: {onExit: () => void}) {
  const [token, setToken] = useState(tokenStore.get());
  const [draft, setDraft] = useState('');
  const [tab, setTab] = useState(0);
  const [data, setData] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'help'>('all');

  const load = useCallback(() => {
    if (!token) return;
    api<Overview>('/api/teacher/overview', token).then(d => { setData(d); setErr(null); }, e => {
      if (e.status === 403) { tokenStore.clear(); setToken(''); setErr(e.message); } else setErr(e.message);
    });
  }, [token]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const rows = (data?.students ?? []).filter(r => filter === 'all' || r.needsHelp);
  return (
    <Box sx={{minHeight: '100vh', bgcolor: 'background.default'}}>
      <Box component="header" sx={{bgcolor: 'primary.main', color: 'primary.contrastText'}}>
        <Container maxWidth="lg" sx={{py: 1.25, display: 'flex', alignItems: 'baseline', gap: 1.5}}>
          <Typography component="h1" variant="h5" sx={{flex: 1}}>CodeAI <Typography component="span" sx={{opacity: 0.85, fontWeight: 400}}>Teacher view</Typography></Typography>
          {token && <Button color="inherit" onClick={() => { tokenStore.clear(); setToken(''); setData(null); }}>Sign out</Button>}
          <Button color="inherit" onClick={onExit}>Student site</Button>
        </Container>
      </Box>
      <Container maxWidth="lg" sx={{py: 3, display: 'grid', gap: 2}}>
        {!token ? (
          <Paper variant="outlined" sx={{p: 3, borderRadius: '12px', maxWidth: 460, display: 'grid', gap: 2}}>
            <Typography variant="h5" component="h2">Teacher sign-in</Typography>
            <Typography color="text.secondary">This page shows stages, mistakes and what children typed, so it needs the teacher token set on the server.</Typography>
            {err && <Alert severity="error">{err}</Alert>}
            <TextField type="password" label="Teacher token" value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && draft) { tokenStore.set(draft); setToken(draft); } }} />
            <Box><Button variant="contained" disabled={!draft} onClick={() => { tokenStore.set(draft); setToken(draft); }}>Open</Button></Box>
          </Paper>
        ) : (
          <>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} aria-label="Teacher sections"><Tab label="Students" /><Tab label="Content check" /></Tabs>
            {err && <Alert severity="error">{err}</Alert>}
            {tab === 1 && <ContentCheckView token={token} />}
            {tab === 0 && !data && !err && <CircularProgress aria-label="Loading" />}
            {tab === 0 && data && (
              <>
                <Box sx={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 1}}>
                  {([['Students', data.summary.total], ['In the quest', data.summary.quest], ['Coding', data.summary.working], ['Finished', data.summary.finished], ['Need help', data.summary.needHelp]] as const).map(([k, v]) => (
                    <Paper key={k} variant="outlined" sx={{p: 1.5, borderRadius: '10px'}}><Typography variant="h4" component="p" sx={{color: k === 'Need help' && v > 0 ? 'warning.main' : undefined}}>{v}</Typography><Typography variant="body2" color="text.secondary">{k}</Typography></Paper>
                  ))}
                </Box>
                <Distribution overview={data} />
                <Box sx={{display: 'flex', gap: 1}}>
                  <Chip label="Everyone" color={filter === 'all' ? 'primary' : 'default'} onClick={() => setFilter('all')} />
                  <Chip label="Needs help" color={filter === 'help' ? 'warning' : 'default'} onClick={() => setFilter('help')} />
                </Box>
                {data.truncated && <Alert severity="info">Showing the first {data.students.length} students.</Alert>}
                <Box sx={{overflowX: 'auto'}}>
                  <Box component="table" sx={{width: '100%', borderCollapse: 'collapse', '& th, & td': {textAlign: 'left', p: 1, borderBottom: 1, borderColor: 'divider', fontSize: 14, whiteSpace: 'nowrap'}}}>
                    <thead><tr><th>Student</th><th>Status</th><th>Where</th><th>Tries</th><th>Ideas</th><th>Last active</th><th>Flag</th></tr></thead>
                    <tbody>
                      {rows.map(r => (
                        <tr key={r.studentId}>
                          <td><Button size="small" onClick={() => setOpen(r.studentId)} sx={{fontFamily: 'var(--code-font)'}}>{r.studentId.slice(0, 12)}…</Button></td>
                          <td>{STATUS[r.status]}</td>
                          <td>{r.status === 'quest' ? 'Readiness quest' : r.current ?? r.project}</td>
                          <td>{r.attempts}</td>
                          <td><Box sx={{display: 'flex', gap: 0.75}}>{Object.entries(r.stages).map(([k, s]) => <Box key={k} title={`${k.replace('_', ' ')}: ${data.stageNames[s]}`}><StageDots stage={s} /></Box>)}</Box></td>
                          <td>{ago(r.lastActive)}</td>
                          <td>{r.needsHelp ? <Chip size="small" color="warning" label={r.needsHelp} /> : ''}</td>
                        </tr>
                      ))}
                      {rows.length === 0 && <tr><td colSpan={7}>Nobody here yet.</td></tr>}
                    </tbody>
                  </Box>
                </Box>
              </>
            )}
          </>
        )}
      </Container>
      {open && token && <DetailView id={open} token={token} onClose={() => setOpen(null)} />}
    </Box>
  );
}
