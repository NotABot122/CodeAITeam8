import type {TelemetryEvent} from '@/api/types';

/** Oldest events are dropped past this, so a long outage cannot grow memory without bound. */
const MAX_HELD_EVENTS = 500;

/** Events waiting to be sent in the next batch. */
export class TelemetryBuffer {
  private events: TelemetryEvent[] = [];

  constructor(private readonly maxBatch: number) {}

  get size(): number {
    return this.events.length;
  }

  /** Adds an event; true once a batch is full and should be sent. */
  add(event: TelemetryEvent): boolean {
    this.events.push(event);
    if (this.events.length > MAX_HELD_EVENTS) {
      this.events.splice(0, this.events.length - MAX_HELD_EVENTS);
    }
    return this.events.length >= this.maxBatch;
  }

  /** Removes and returns everything held, oldest first. */
  drain(): TelemetryEvent[] {
    return this.events.splice(0, this.events.length);
  }

  /** Puts back events whose send failed, ahead of anything newer. */
  restore(events: TelemetryEvent[]): void {
    this.events = [...events, ...this.events].slice(-MAX_HELD_EVENTS);
  }
}

/**
 * Folds keystrokes into bursts: a run of keystrokes with no gap longer than
 * `gapMs`. A burst is a count and a duration, never the text typed.
 */
export class BurstAggregator {
  private count = 0;
  private startMs = 0;
  private lastMs = 0;

  constructor(private readonly gapMs = 1500) {}

  /** Records a keystroke; returns the previous burst if this one starts a new one. */
  keystroke(nowMs: number): TelemetryEvent | undefined {
    let finished: TelemetryEvent | undefined;
    if (this.count > 0 && nowMs - this.lastMs > this.gapMs) {
      finished = this.close();
    }
    if (this.count === 0) this.startMs = nowMs;
    this.count += 1;
    this.lastMs = nowMs;
    return finished;
  }

  /** Ends the burst in progress, if any. */
  close(): TelemetryEvent | undefined {
    if (this.count === 0) return undefined;
    const event: TelemetryEvent = {
      type: 'typing_burst',
      at: new Date(this.startMs).toISOString(),
      keystrokes: this.count,
      durationMs: this.lastMs - this.startMs,
    };
    this.count = 0;
    return event;
  }
}
