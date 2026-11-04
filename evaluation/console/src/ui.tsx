import {Alert, Box, Chip, CircularProgress, LinearProgress, Paper, Stack, Typography} from '@mui/material';
import {useCallback, useEffect, useState, type ReactNode} from 'react';
import type {Status} from './api';

export const STATUS_LABEL: Record<Status, string> = {
  met: 'Met',
  partial: 'Partly met',
  not_met: 'Not met',
  not_tested: 'Not tested',
};

export function StatusChip({status}: {status: Status}) {
  const color = status === 'met' ? 'success' : status === 'partial' ? 'warning' : status === 'not_met' ? 'error' : 'default';
  return <Chip size="small" color={color} label={STATUS_LABEL[status]} sx={{fontWeight: 600}} />;
}

export function Verdict({ok, yes = 'pass', no = 'fail'}: {ok: boolean | null; yes?: string; no?: string}) {
  if (ok === null) return <Chip size="small" label="n/a" variant="outlined" />;
  return <Chip size="small" color={ok ? 'success' : 'error'} variant="outlined" label={ok ? yes : no} />;
}

export function Section({title, subtitle, action, children}: {title: string; subtitle?: ReactNode; action?: ReactNode; children: ReactNode}) {
  return (
    <Paper variant="outlined" sx={{p: 2.5, mb: 2.5}}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2} sx={{mb: 1.5}}>
        <Box>
          <Typography variant="h6">{title}</Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{mt: 0.5}}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Stack>
      {children}
    </Paper>
  );
}

export function Stat({label, value, hint, tone}: {label: string; value: ReactNode; hint?: ReactNode; tone?: 'good' | 'bad' | 'warn'}) {
  const color = tone === 'good' ? 'success.main' : tone === 'bad' ? 'error.main' : tone === 'warn' ? 'warning.main' : 'text.primary';
  return (
    <Paper variant="outlined" sx={{p: 2, flex: 1, minWidth: 160}}>
      <Typography variant="caption" color="text.secondary" sx={{textTransform: 'uppercase', letterSpacing: 0.6}}>
        {label}
      </Typography>
      <Typography variant="h5" sx={{color, mt: 0.5}}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="body2" color="text.secondary" sx={{mt: 0.5}}>
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

/** Horizontal bar for a 0..max value; plain MUI so no chart library is needed. */
export function Bar({value, max = 1, label, color = 'primary'}: {value: number | null | undefined; max?: number; label?: string; color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning'}) {
  const v = value ?? 0;
  return (
    <Stack direction="row" alignItems="center" spacing={1} sx={{minWidth: 140}}>
      <LinearProgress variant="determinate" value={Math.max(0, Math.min(100, (v / max) * 100))} color={color} sx={{flex: 1, height: 8, borderRadius: 4}} />
      <Typography variant="body2" sx={{width: 48, textAlign: 'right', fontVariantNumeric: 'tabular-nums'}}>
        {label ?? (value === null || value === undefined ? '–' : v.toFixed(2))}
      </Typography>
    </Stack>
  );
}

export function Code({children, maxHeight = 260}: {children: string; maxHeight?: number}) {
  return (
    <Box component="pre" sx={{m: 0, p: 1.5, bgcolor: 'action.hover', borderRadius: 1, fontFamily: 'var(--code-font)', fontSize: 13, overflow: 'auto', maxHeight, whiteSpace: 'pre'}}>
      {children}
    </Box>
  );
}

export function CodeInput({value, onChange, rows = 14}: {value: string; onChange: (v: string) => void; rows?: number}) {
  return (
    <Box
      component="textarea"
      value={value}
      spellCheck={false}
      rows={rows}
      onChange={e => onChange((e.target as HTMLTextAreaElement).value)}
      onKeyDown={e => {
        if (e.key === 'Tab' && !e.shiftKey) {
          e.preventDefault();
          const t = e.target as HTMLTextAreaElement;
          const s = t.selectionStart;
          const next = value.slice(0, s) + '    ' + value.slice(t.selectionEnd);
          onChange(next);
          requestAnimationFrame(() => (t.selectionStart = t.selectionEnd = s + 4));
        }
      }}
      sx={{width: '100%', p: 1.5, fontFamily: 'var(--code-font)', fontSize: 13, lineHeight: 1.5, border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'background.default', color: 'text.primary', resize: 'vertical'}}
      aria-label="Student code"
    />
  );
}

/** Loads data on mount; `reload` re-fetches. */
export function useLoad<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(reload, [reload]);
  return {data, error, loading, reload};
}

export function Loading({error, loading}: {error: string | null; loading: boolean}) {
  if (error) return <Alert severity="error">{error}</Alert>;
  if (loading)
    return (
      <Box sx={{display: 'flex', justifyContent: 'center', p: 4}}>
        <CircularProgress />
      </Box>
    );
  return null;
}

export function Caveat({children}: {children: ReactNode}) {
  return (
    <Alert severity="info" variant="outlined" sx={{mt: 1.5}}>
      {children}
    </Alert>
  );
}
