import {useCallback, useEffect, useMemo, useRef} from 'react';

import type {ApiClient} from '@/api/client';
import type {Hint} from '@/api/types';

import {BurstAggregator, TelemetryBuffer} from './buffer';

const FLUSH_INTERVAL_MS = 3000;
const MAX_BATCH = 25;

interface UseTelemetryOptions {
  client: ApiClient;
  sessionId: string;
  lessonId: string;
  /** Called with any hints the backend returns for a batch. */
  onHints: (hints: Hint[]) => void;
}

/**
 * Batches editor activity and sends it on a timer, when a batch fills, when
 * the tab is hidden, and on unmount. Recording never waits on the network.
 */
export function useTelemetry({client, sessionId, lessonId, onHints}: UseTelemetryOptions) {
  const buffer = useMemo(() => new TelemetryBuffer(MAX_BATCH), []);
  const bursts = useMemo(() => new BurstAggregator(), []);
  const latest = useRef({client, sessionId, lessonId, onHints});
  latest.current = {client, sessionId, lessonId, onHints};

  const flush = useCallback(async () => {
    const burst = bursts.close();
    if (burst) buffer.add(burst);
    const events = buffer.drain();
    if (events.length === 0) return;
    const {client, sessionId, lessonId, onHints} = latest.current;
    try {
      const ack = await client.sendTelemetry({sessionId, lessonId, events});
      if (ack.hints.length > 0) onHints(ack.hints);
    } catch {
      buffer.restore(events);
    }
  }, [buffer, bursts]);

  useEffect(() => {
    const timer = setInterval(flush, FLUSH_INTERVAL_MS);
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') void flush();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
      void flush();
    };
  }, [flush]);

  const add = useCallback(
    (event: Parameters<TelemetryBuffer['add']>[0]) => {
      if (buffer.add(event)) void flush();
    },
    [buffer, flush]
  );

  return useMemo(
    () => ({
      recordKeystroke: () => {
        const finished = bursts.keystroke(Date.now());
        if (finished) add(finished);
      },
      recordRun: (ok: boolean) =>
        add({type: 'run', at: new Date().toISOString(), ok}),
      recordError: (errorType: string, line?: number) =>
        add({type: 'error', at: new Date().toISOString(), errorType, line}),
      recordIdle: (durationMs: number) =>
        add({type: 'idle', at: new Date().toISOString(), durationMs}),
      flush,
    }),
    [add, bursts, flush]
  );
}
