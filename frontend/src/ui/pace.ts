// Pacing: how long a question should take to read and answer, whether the student is rushing,
// and a countdown for the Check button once they are.
//
// Expected time = reading time (high school reading speed, about 240 words a minute = 4 words a second)
// + a little per answer choice or card to look it over + more per line of code + a couple of seconds to
// decide. So short questions get a short timer and long ones a longer one.
// Rushing = answering in under 20% of that time (at least 1.5 s). Two rushed answers in the last three (one for a whole quiz
// page) turns "slow mode" on: the student sees a message and the Check button waits for the expected time.
// Three answers in a row that weren't rushed turn it off again, so careful students aren't held back.
// Only time on the question itself is measured (from when it appears to Check). The feedback screen and its Next
// button are never timed, and the readiness check ignores clicks on a question for its first 0.8 s so a quick click
// carried over from Next can't answer it (QuestApp.tsx SETTLE_MS).
import {useCallback, useEffect, useRef, useState} from 'react';

const WORDS_PER_SECOND = 4;
const PER_CHOICE_S = 0.75;
const PER_CODE_LINE_S = 1.5;
const DECIDE_S = 2;
export const RUSH_FRACTION = 0.2;   // was 0.4, which caught careful fast readers too often
const MIN_S = 3;
const MAX_S = 40;

const words = (text: string | undefined | null) => (text ?? '').split(/\s+/).filter(Boolean).length;
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

/** Seconds a student should spend on one question. */
export function expectedSeconds(q: {prompt: string; choices?: string[]; code?: string | null; typed?: boolean}): number {
  const choices = q.choices ?? [];
  const codeLines = (q.code ?? '').split('\n').filter(l => l.trim()).length;
  const read = (words(q.prompt) + choices.reduce((n, c) => n + words(c), 0) + words(q.code)) / WORDS_PER_SECOND;
  const look = choices.length * PER_CHOICE_S + codeLines * PER_CODE_LINE_S;
  // A typed answer takes its own time to write, so only the reading counts here.
  return Math.round(clamp(read + look + (q.typed ? 0 : DECIDE_S), MIN_S, MAX_S));
}

/** Seconds for a page of questions answered together (a lesson quiz), capped at two minutes. */
export function expectedPageSeconds(qs: {prompt: string; choices?: string[]; code?: string | null; typed?: boolean}[]): number {
  return Math.round(clamp(qs.reduce((n, q) => n + expectedSeconds(q), 0), MIN_S, 120));
}

export function isRushed(elapsedMs: number, expectedS: number): boolean {
  return elapsedMs < Math.max(1500, expectedS * 1000 * RUSH_FRACTION);
}

/**
 * Slow mode for a run of questions. `record` after each answer; `slow` says whether the timer applies now.
 * `turnOnAfter` rushed answers among the last three turn it on; `calmToClear` unrushed answers in a row turn it off.
 */
export function usePace(turnOnAfter = 2, calmToClear = 3) {
  const recent = useRef<boolean[]>([]);
  const calm = useRef(0);
  const slowRef = useRef(false);
  const [slow, setSlow] = useState(false);
  const [justSlowed, setJustSlowed] = useState(false);

  const record = useCallback((elapsedMs: number, expectedS: number) => {
    const rushed = isRushed(elapsedMs, expectedS);
    recent.current = [...recent.current, rushed].slice(-3);
    calm.current = rushed ? 0 : calm.current + 1;
    if (!slowRef.current && recent.current.filter(Boolean).length >= turnOnAfter) {
      slowRef.current = true; setSlow(true); setJustSlowed(true);
    } else if (slowRef.current && calm.current >= calmToClear) {
      slowRef.current = false; recent.current = []; setSlow(false); setJustSlowed(false);
    }
    return rushed;
  }, [turnOnAfter, calmToClear]);

  return {slow, justSlowed, record, dismiss: () => setJustSlowed(false)};
}

/** Seconds left before the button unlocks: counts down from `seconds` after `since` (ms timestamp). 0 when off. */
export function useCountdown(active: boolean, seconds: number, since: number): number {
  const left = () => (active ? Math.max(0, Math.ceil(seconds - (Date.now() - since) / 1000)) : 0);
  const [remaining, setRemaining] = useState(left);
  useEffect(() => {
    setRemaining(left());
    if (!active) return;
    const id = window.setInterval(() => {
      const r = left();
      setRemaining(r);
      if (r <= 0) window.clearInterval(id);
    }, 250);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, seconds, since]);
  return remaining;
}

export const SLOW_DOWN_MESSAGE =
  "Whoa, that was fast! Take a moment to read each question and every answer before you choose. " +
  "The Check button will be ready after a short wait, about as long as it takes to read the question.";
