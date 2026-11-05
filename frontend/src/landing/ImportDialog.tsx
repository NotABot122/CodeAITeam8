import UploadFileIcon from '@mui/icons-material/UploadFile';
import {Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel,
  Radio, RadioGroup, Typography} from '@mui/material';
import {useEffect, useRef, useState} from 'react';

import {ApiError, type ApiClient} from '@/api/client';
import type {ImportResult, ImportSample, StudentState} from '@/api/types';

import MatchCard from './MatchCard';

const MAX_FILE_BYTES = 32 * 1024;
const msg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong. Try again.');

/** Read a results file in the browser. Only its parsed JSON is sent; never the file name. */
export async function readResultsFile(file: File): Promise<unknown> {
  if (file.size > MAX_FILE_BYTES) throw new Error('That file is too big for a results file. Pick the .json file from your earlier lesson.');
  try { return JSON.parse(await file.text()); }
  catch { throw new Error("That file isn't valid JSON. Pick the .json file from your earlier lesson."); }
}

/**
 * "Import results from an earlier lesson": skip the readiness check with a results file, or (for demos) a
 * synthetic sample student. The server turns away files with personal details and screens any text.
 */
export default function ImportDialog({client, open, onClose, onDone}: {
  client: ApiClient; open: boolean; onClose: () => void; onDone: (state: StudentState) => void;
}) {
  const [samples, setSamples] = useState<ImportSample[] | null>(null);
  const [sample, setSample] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || samples) return;
    client.importSamples().then(r => setSamples(r.samples)).catch(() => setSamples([]));
  }, [client, open, samples]);

  const send = async (from: {sample: string} | {data: unknown}) => {
    setBusy(true); setError(null);
    try { setDone(await client.importPrevious(from)); }
    catch (e) { setError(e instanceof ApiError || e instanceof Error ? e.message : msg(e)); }
    finally { setBusy(false); }
  };
  const pickFile = async (file: File | undefined) => {
    if (!file) return;
    try { await send({data: await readResultsFile(file)}); }
    catch (e) { setError(msg(e)); }
    finally { if (fileRef.current) fileRef.current.value = ''; }
  };
  const close = () => { if (!busy) { setDone(null); setError(null); onClose(); } };

  return (
    <Dialog open={open} onClose={close} aria-labelledby="import-title" maxWidth="sm" fullWidth>
      <DialogTitle id="import-title">Use results from an earlier lesson</DialogTitle>
      <DialogContent sx={{display: 'grid', gap: 2}}>
        {done ? (
          <>
            <Alert severity="success">Your results are in. We skipped the readiness check and picked where you start.</Alert>
            {done.result.notices.map((n, i) => <Alert key={i} severity="info">{n}</Alert>)}
            {done.result.match && <MatchCard match={done.result.match} />}
          </>
        ) : (
          <>
            <Typography color="text.secondary">
              Already did a lesson like this? Bring its results file and skip the readiness check. We only use results
              per idea. Files with names or other personal details are turned away.
            </Typography>
            <Box>
              <input ref={fileRef} type="file" accept=".json,application/json" hidden aria-hidden
                onChange={e => void pickFile(e.target.files?.[0])} />
              <Button variant="outlined" startIcon={<UploadFileIcon />} disabled={busy} onClick={() => fileRef.current?.click()}>
                Choose a results file
              </Button>
            </Box>
            <Divider>or try a sample student</Divider>
            {samples === null && <Box sx={{display: 'grid', placeItems: 'center', py: 2}}><CircularProgress size={24} aria-label="Loading samples" /></Box>}
            {samples && samples.length === 0 && <Typography color="text.secondary">No sample students are set up.</Typography>}
            {samples && samples.length > 0 && (
              <RadioGroup aria-label="Sample students" value={sample} onChange={e => setSample(e.target.value)}>
                {samples.map(s => (
                  <FormControlLabel key={s.id} value={s.id} disabled={busy} control={<Radio />} sx={{alignItems: 'flex-start', mb: 1, '& .MuiRadio-root': {mt: -0.5}}}
                    label={<Box><Typography sx={{fontWeight: 700}}>{s.label}</Typography><Typography variant="body2" color="text.secondary">{s.about}</Typography></Box>} />
                ))}
              </RadioGroup>
            )}
            <Typography variant="body2" color="text.secondary">Sample students are made-up demo data.</Typography>
            {busy && <Typography role="status" color="text.secondary">Reading the results…</Typography>}
          </>
        )}
        {error && <Alert severity="warning" role="alert">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        {done ? (
          <Button variant="contained" color="secondary" onClick={() => { const s = done.state; setDone(null); onDone(s); }}>See my pathway</Button>
        ) : (
          <>
            <Button onClick={close} disabled={busy}>Cancel</Button>
            <Button variant="contained" color="secondary" disabled={busy || !sample} onClick={() => void send({sample})}>Use this sample</Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
