import {describe, expect, it} from 'vitest';

import {
  answerResultSchema,
  diagnosticQuestionSchema,
  growthReportSchema,
  nextStepSchema,
  skillTreeSchema,
  telemetryBatchSchema,
} from '../schema';

import {
  MOCK_DIAGNOSTIC,
  MOCK_GROWTH,
  MOCK_NEXT_STEPS,
  MOCK_SKILL_TREE,
} from './data';
import {createMockClient} from './mockClient';

// The mock is the working contract until the backend exists, so it must
// satisfy the same schemas the HTTP client enforces.
describe('mock data matches the contract', () => {
  it('skill tree', () => {
    expect(skillTreeSchema.safeParse(MOCK_SKILL_TREE).success).toBe(true);
  });

  it('has a node under two categories', () => {
    expect(MOCK_SKILL_TREE.nodes.some(n => n.categories.length > 1)).toBe(true);
  });

  it('only requires nodes that exist', () => {
    const ids = new Set(MOCK_SKILL_TREE.nodes.map(n => n.id));
    for (const n of MOCK_SKILL_TREE.nodes) {
      for (const p of n.requires) expect(ids.has(p)).toBe(true);
    }
    for (const id of MOCK_SKILL_TREE.targetNodeIds) expect(ids.has(id)).toBe(true);
  });

  it('diagnostic questions', () => {
    for (const q of MOCK_DIAGNOSTIC) {
      expect(diagnosticQuestionSchema.safeParse(q).success).toBe(true);
    }
  });

  it('every stance has a next step', () => {
    for (const step of MOCK_NEXT_STEPS) {
      expect(nextStepSchema.safeParse(step).success).toBe(true);
    }
    expect(new Set(MOCK_NEXT_STEPS.map(s => s.stance)).size).toBe(4);
  });

  it('growth report', () => {
    expect(growthReportSchema.safeParse(MOCK_GROWTH).success).toBe(true);
  });
});

describe('mock client', () => {
  it('queues a follow-up after the first open-ended answer', async () => {
    const result = await createMockClient().submitAnswer({
      questionId: 3,
      choiceId: '',
      text: 'a box for a value',
      latencyMs: 5000,
    });
    expect(answerResultSchema.safeParse(result).success).toBe(true);
    expect(result.followUp?.followUpTo).toBe(3);
  });

  it('grades a wrong choice as incorrect', async () => {
    const result = await createMockClient().submitAnswer({
      questionId: 1,
      choiceId: 'a',
      latencyMs: 1000,
    });
    expect(result.isCorrect).toBe(false);
  });

  it('returns a hint on the second error in a session', async () => {
    const client = createMockClient();
    const batch = {
      sessionId: 's',
      lessonId: 'l',
      events: [{type: 'error' as const, at: new Date().toISOString(), errorType: 'SyntaxError'}],
    };
    expect(telemetryBatchSchema.safeParse(batch).success).toBe(true);
    expect((await client.sendTelemetry(batch)).hints).toHaveLength(0);
    expect((await client.sendTelemetry(batch)).hints).toHaveLength(1);
  });
});
