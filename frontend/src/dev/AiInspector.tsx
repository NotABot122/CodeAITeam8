import CloseIcon from '@mui/icons-material/Close';
import DeleteSweepOutlinedIcon from '@mui/icons-material/DeleteSweepOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Badge, Box, Button, Chip, Drawer, Fab, FormControlLabel,
  IconButton, Switch, TextField, Tooltip, Typography,
} from '@mui/material';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {ApiError, createHttpClient} from '@/api/client';
import type {AiCall, AiInfo} from '@/api/types';

// Dev-only AI inspector. Shows only when the server runs with --dev (health.dev). A button in the corner opens a
// side panel listing every AI model call, newest first: which feature made it, the model, the system prompt, the
// input, the tools offered, and the output, with latency and tokens. For demos of the AI adaptivity.
// When the server has a teacher token (health.devLocked, e.g. production), the panel asks for it first: the calls
// include students' code and words. The token is kept for this browser tab only, shared with the teacher page.

const POLL_OPEN_MS = 1500;
const POLL_CLOSED_MS = 5000;
const studentNow = () => { try { return localStorage.getItem('codeai.studentId'); } catch { return null; } };
const TOKEN_KEY = 'codeai.teacherToken';   // same key as the teacher page (sessionStorage)
const tokenStore = {
  get: () => { try { return sessionStorage.getItem(TOKEN_KEY) ?? ''; } catch { return ''; } },
  set: (v: string) => { try { sessionStorage.setItem(TOKEN_KEY, v); } catch { /* private mode */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ } },
};
const time = (iso: string) => new Date(iso).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});

// One colour per feature, so the same kind of call is easy to spot.
const COLORS = ['#7c3aed', '#2563eb', '#0891b2', '#059669', '#ca8a04', '#ea580c', '#dc2626', '#db2777', '#4b5563'];
const colorFor = (name: string, names: string[]) => COLORS[Math.max(0, names.indexOf(name)) % COLORS.length];

function Block({label, text, open = false}: {label: string; text: string; open?: boolean}) {
  return (
    <Box component="details" open={open} sx={{'& > summary': {cursor: 'pointer', fontWeight: 700, fontSize: 13, py: 0.5}}}>
      <summary>{label} <Typography component="span" variant="caption" color="text.secondary">({text.length.toLocaleString()} characters)</Typography></summary>
      <Box component="pre" sx={{m: 0, mt: 0.5, p: 1.25, borderRadius: '8px', bgcolor: 'action.hover', fontFamily: 'var(--code-font)', fontSize: 12,
        whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 360, overflow: 'auto'}}>{text}</Box>
    </Box>
  );
}

function CallCard({call, color, fresh}: {call: AiCall; color: string; fresh: boolean}) {
  const output = call.toolInput !== undefined && call.toolInput !== null
    ? `${call.toolName ? `Tool: ${call.toolName}\n` : ''}${JSON.stringify(call.toolInput, null, 2)}`
    : call.outputText ?? '';
  return (
    <Accordion disableGutters variant="outlined" sx={{borderLeft: `4px solid ${color}`, borderRadius: '8px !important', '&:before': {display: 'none'},
      animation: fresh ? 'aiFlash 1.4s ease-out' : 'none', '@keyframes aiFlash': {from: {boxShadow: `0 0 0 3px ${color}`}, to: {boxShadow: '0 0 0 0 transparent'}}}}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{'& .MuiAccordionSummary-content': {display: 'grid', gap: 0.5, my: 1}}}>
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap'}}>
          <Typography sx={{fontWeight: 700, color}}>{call.feature.name}</Typography>
          {!call.ok && <Chip size="small" color="error" label="model error → fallback" />}
        </Box>
        <Typography variant="caption" color="text.secondary">
          #{call.id} · {time(call.at)} · {(call.latencyMs / 1000).toFixed(1)} s
          {call.ok && call.inputTokens ? ` · ${call.inputTokens.toLocaleString()} in / ${call.outputTokens?.toLocaleString()} out tokens` : ''}
          {call.student ? ` · student ${call.student.slice(0, 8)}` : ''}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{display: 'grid', gap: 1, pt: 0}}>
        {call.feature.what && <Typography variant="body2" color="text.secondary">{call.feature.what}</Typography>}
        <Typography variant="caption" sx={{fontFamily: 'var(--code-font)'}}>model: {call.model} · max tokens {call.maxTokens}{call.requireTool ? ' · must answer with a tool' : ''}</Typography>
        <Block label="Output" text={call.ok ? output || '(empty)' : `Error: ${call.error}`} open />
        <Block label="Input sent to the model" text={call.input} />
        <Block label="System prompt (instructions)" text={call.system} />
        {call.tools.length > 0 && (
          <Block label={`Tools offered: ${call.tools.map(t => t.name).join(', ')}`}
            text={call.tools.map(t => `${t.name}: ${t.description}\n${JSON.stringify(t.schema, null, 2)}`).join('\n\n')} />
        )}
      </AccordionDetails>
    </Accordion>
  );
}

export default function AiInspector() {
  const client = useMemo(() => createHttpClient(import.meta.env.VITE_API_BASE_URL ?? ''), []);
  const [enabled, setEnabled] = useState(false);
  const [info, setInfo] = useState<AiInfo | null>(null);
  const [open, setOpen] = useState(false);
  const [calls, setCalls] = useState<AiCall[]>([]);
  const [seen, setSeen] = useState(0);
  const [mine, setMine] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [token, setToken] = useState(tokenStore.get);
  const [tokenInput, setTokenInput] = useState('');
  const last = useRef(0);
  const freshUntil = useRef<Record<number, number>>({});
  const ready = enabled && (!locked || !!token);

  useEffect(() => {
    client.health().then(h => {
      if (!h.dev) return;
      setEnabled(true);
      setLocked(!!h.devLocked);
    }).catch(() => undefined);
  }, [client]);

  const rejected = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 403) {
      tokenStore.clear();
      setToken('');
      setError('That teacher token was not accepted.');
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (!ready) return;
    client.devAiInfo(token || undefined).then(setInfo).catch(e => { if (!rejected(e)) setInfo(null); });
  }, [client, ready, token, rejected]);

  const poll = useCallback(async () => {
    try {
      const {calls: more} = await client.devAiCalls(last.current, token || undefined);
      if (more.length) {
        last.current = more[more.length - 1].id;
        const until = Date.now() + 1500;
        more.forEach(c => { freshUntil.current[c.id] = until; });
        setCalls(prev => [...prev, ...more].slice(-300));
      }
      setError(null);
    } catch (e) { if (!rejected(e)) setError(e instanceof Error ? e.message : 'Could not load AI calls.'); }
  }, [client, token, rejected]);

  useEffect(() => {
    if (!ready) return;
    void poll();
    const id = window.setInterval(() => void poll(), open ? POLL_OPEN_MS : POLL_CLOSED_MS);
    return () => window.clearInterval(id);
  }, [ready, open, poll]);

  const unlock = () => {
    const value = tokenInput.trim();
    if (!value) return;
    tokenStore.set(value);
    setToken(value);
    setTokenInput('');
    setError(null);
  };

  useEffect(() => { if (open) setSeen(last.current); }, [open, calls.length]);

  if (!enabled) return null;
  const me = studentNow();
  const shown = [...calls].reverse().filter(c => !mine || (me && c.student === me));
  const names = (info?.features ?? []).map(f => f.name);
  const unseen = calls.filter(c => c.id > seen).length;

  return (
    <>
      <Tooltip title="AI inspector (dev only): every AI call, its input and output" placement="left">
        <Badge badgeContent={open ? 0 : unseen} color="error" max={99} overlap="circular"
          sx={{position: 'fixed', left: 16, bottom: 16, zIndex: t => t.zIndex.drawer + 1}}>
          <Fab size="medium" color="primary" aria-label="Open the AI inspector" onClick={() => setOpen(true)}>
            <PsychologyOutlinedIcon />
          </Fab>
        </Badge>
      </Tooltip>
      <Drawer anchor="right" open={open} onClose={() => setOpen(false)} variant="persistent"
        slotProps={{paper: {sx: {width: {xs: '100vw', sm: 560}, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5, boxShadow: 6}}}}>
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <PsychologyOutlinedIcon color="primary" />
          <Typography variant="h6" component="h2" sx={{flex: 1}}>AI inspector <Typography component="span" variant="caption" color="text.secondary">dev only</Typography></Typography>
          <Tooltip title="Clear the list"><IconButton aria-label="Clear the list" disabled={!ready} onClick={() => { void client.devAiClear(token || undefined).catch(rejected); setCalls([]); }}><DeleteSweepOutlinedIcon /></IconButton></Tooltip>
          <IconButton aria-label="Close the AI inspector" onClick={() => setOpen(false)}><CloseIcon /></IconButton>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Every call our app makes to Amazon Bedrock, live: which part of the adaptive system made it, exactly what the model was given, and what it answered.
          Each one has a rule-based or teacher-written fallback.
        </Typography>
        {!ready && (
          <Box component="form" onSubmit={e => { e.preventDefault(); unlock(); }} sx={{display: 'grid', gap: 1}}>
            <Alert severity="info">These calls include students' code and what they typed, so teachers only: enter the teacher token.</Alert>
            {error && <Alert severity="warning">{error}</Alert>}
            <Box sx={{display: 'flex', gap: 1}}>
              <TextField size="small" type="password" label="Teacher token" value={tokenInput} autoComplete="off"
                onChange={e => setTokenInput(e.target.value)} sx={{flex: 1}} />
              <Button type="submit" variant="contained" disabled={!tokenInput.trim()}>Unlock</Button>
            </Box>
          </Box>
        )}
        {info && (
          <Typography variant="caption" sx={{fontFamily: 'var(--code-font)'}}>
            {info.ai ? `AI on · model ${info.model} (${info.modelSource === 'CODEAI_MODEL_ID' ? 'set by CODEAI_MODEL_ID' : 'team default'}) · safety: ${info.safety ?? 'local rules'}` : `AI is off${info.aiReason ? ` (${info.aiReason})` : ''}: the app is using its rules and teacher-written content.`}
          </Typography>
        )}
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap'}}>
          <FormControlLabel control={<Switch size="small" checked={mine} onChange={e => setMine(e.target.checked)} disabled={!me} />}
            label={<Typography variant="body2">This student only</Typography>} />
          <Typography variant="caption" color="text.secondary" sx={{ml: 'auto'}}>{shown.length} call{shown.length === 1 ? '' : 's'}</Typography>
        </Box>
        {info && (
          <Box component="details" sx={{'& > summary': {cursor: 'pointer', fontSize: 13, fontWeight: 600}}}>
            <summary>The AI features</summary>
            <Box component="ul" sx={{m: 0, mt: 1, pl: 2.5, display: 'grid', gap: 0.5}}>
              {info.features.map(f => {
                // The model this feature really used last, else the configured one.
                const used = [...calls].reverse().find(c => c.feature.name === f.name)?.model;
                const model = used ?? f.model;
                return (
                  <li key={f.name}>
                    <Typography variant="body2"><Box component="span" sx={{fontWeight: 700, color: colorFor(f.name, names)}}>{f.name}</Box>: {f.what}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{fontFamily: 'var(--code-font)'}}>
                      model: {model ?? 'none (AI is off: rules and teacher-written content)'}{model ? (used ? ' · seen in a call' : ' · configured') : ''}
                    </Typography>
                  </li>
                );
              })}
            </Box>
          </Box>
        )}
        {ready && error && <Alert severity="warning">{error}</Alert>}
        {ready && <Box sx={{flex: 1, overflowY: 'auto', display: 'grid', gap: 1, alignContent: 'start', pr: 0.5}}>
          {shown.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{py: 4, textAlign: 'center'}}>
              No AI calls yet. Run code that fails, ask Ducky for a hint, finish the readiness check, or use "Make it yours".
            </Typography>
          )}
          {shown.map(c => <CallCard key={c.id} call={c} color={colorFor(c.feature.name, names)} fresh={(freshUntil.current[c.id] ?? 0) > Date.now()} />)}
        </Box>}
      </Drawer>
    </>
  );
}
