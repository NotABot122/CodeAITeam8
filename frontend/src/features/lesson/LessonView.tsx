// Lesson screen. The editor is a plain textarea for now: swapping in
// CodeMirror or Monaco only has to call the same four recorders.

import {Alert, Button, Paper, Stack, TextField, Typography} from '@mui/material';
import {useState} from 'react';

import type {ApiClient} from '@/api/client';
import type {Hint} from '@/api/types';

import {useTelemetry} from '../telemetry/useTelemetry';

interface LessonViewProps {
  client: ApiClient;
  lessonId: string;
  title: string;
  instructions: string;
  starterCode: string;
}

const SESSION_ID = crypto.randomUUID();

export default function LessonView({
  client,
  lessonId,
  title,
  instructions,
  starterCode,
}: LessonViewProps) {
  const [code, setCode] = useState(starterCode);
  const [hints, setHints] = useState<Hint[]>([]);
  const telemetry = useTelemetry({
    client,
    sessionId: SESSION_ID,
    lessonId,
    onHints: next =>
      setHints(prev => [
        ...prev,
        ...next.filter(h => !prev.some(p => p.id === h.id)),
      ]),
  });

  return (
    <Stack spacing={2} sx={{maxWidth: 720}}>
      <Typography variant="h6">{title}</Typography>
      <Typography variant="body2">{instructions}</Typography>
      <TextField
        multiline
        minRows={8}
        value={code}
        onChange={e => setCode(e.target.value)}
        onKeyDown={telemetry.recordKeystroke}
        slotProps={{
          htmlInput: {
            'aria-label': 'Code editor',
            spellCheck: false,
            style: {fontFamily: 'monospace'},
          },
        }}
      />
      {/* Stand-ins until the real runner exists; they emit what it will. */}
      <Stack direction="row" spacing={1}>
        <Button variant="contained" onClick={() => telemetry.recordRun(true)}>
          Run (simulated)
        </Button>
        <Button
          variant="outlined"
          onClick={() => {
            telemetry.recordRun(false);
            telemetry.recordError('SyntaxError', 2);
          }}
        >
          Simulate error
        </Button>
      </Stack>
      {hints.map(hint => (
        <Paper key={hint.id} variant="outlined" sx={{p: 2}}>
          <Typography variant="caption" color="text.secondary">
            Hint
          </Typography>
          <Typography variant="body2">{hint.text}</Typography>
        </Paper>
      ))}
      {hints.length === 0 && (
        <Alert severity="info" icon={false}>
          Hints appear here when the tutor notices you are stuck.
        </Alert>
      )}
    </Stack>
  );
}
