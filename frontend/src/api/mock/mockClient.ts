import type {ApiClient} from '../client';
import type {AnswerResult, Hint} from '../types';

import {
  MOCK_DIAGNOSTIC,
  MOCK_GROWTH,
  MOCK_NEXT_STEPS,
  MOCK_SKILL_TREE,
} from './data';

const LATENCY_MS = 120;
const delay = <T>(value: T): Promise<T> =>
  new Promise(resolve => setTimeout(() => resolve(value), LATENCY_MS));

const CORRECT_CHOICES: {[questionId: number]: string} = {1: 'b', 2: 'b', 11: 'b'};

const MOCK_HINT: Hint = {
  id: 'mock-hint-1',
  level: 1,
  text: 'You have hit the same error twice. What does the error message say about the line number?',
};

/** In-memory stand-in for the backend; deterministic so tests and demos repeat. */
export function createMockClient(): ApiClient {
  let nextStepIndex = 0;
  let errorCount = 0;
  return {
    getSkillTree: () => delay(structuredClone(MOCK_SKILL_TREE)),
    getDiagnostic: () => delay(structuredClone(MOCK_DIAGNOSTIC)),
    submitAnswer: async answer => {
      const result: AnswerResult = {};
      const correct = CORRECT_CHOICES[answer.questionId];
      if (correct) result.isCorrect = answer.choiceId === correct;
      // An open-ended first answer draws one probing follow-up.
      if (answer.questionId === 3) {
        result.followUp = {
          id: 4,
          type: 'openEnded',
          followUpTo: 3,
          prompt:
            'Suppose a variable holds 5 and you run `x = x * 2`. What does the variable hold afterwards, and why?',
        };
      }
      return delay(result);
    },
    getNextStep: () => {
      const step = MOCK_NEXT_STEPS[nextStepIndex % MOCK_NEXT_STEPS.length];
      nextStepIndex += 1;
      return delay(structuredClone(step));
    },
    sendTelemetry: batch => {
      errorCount += batch.events.filter(e => e.type === 'error').length;
      // The second error in a session draws a hint.
      return delay({hints: errorCount >= 2 ? [MOCK_HINT] : []});
    },
    getGrowthReport: () => delay(structuredClone(MOCK_GROWTH)),
  };
}
