// The wire contract between this front end and the Rails/Python backend.
// The backend owns the skill tree, scoring and stance decisions; the front end
// only renders what it receives and reports what the student does.
//
// Only GET /api/v1/student/skill_tree is named in PROJECT_SPEC.md. Every other
// path in client.ts is a proposal for the backend team to accept or change.
//
// The node `requires` graph and the first-answer-only evidence idea are
// adapted from code-dot-org/code-dot-org apps/src/adaptive/schema (Apache-2.0).
// Changed: nodes carry several categories (poly-hierarchy) and a three-part
// mastery vector instead of one evidence level.

import {z} from 'zod';

export const NODE_STATES = ['LOCKED', 'AVAILABLE', 'MASTERED'] as const;
export const nodeStateSchema = z.enum(NODE_STATES);

/** Each score is 0..1. */
export const masterySchema = z.object({
  conceptual: z.number().min(0).max(1),
  syntax: z.number().min(0).max(1),
  problemSolving: z.number().min(0).max(1),
});

export const categorySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
});

export const skillNodeSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string(),
  /** One or more; a node such as While Loops sits under two. */
  categories: z.array(z.string().min(1)).min(1),
  /** Parent node ids that must reach their unlock threshold first. */
  requires: z.array(z.string().min(1)),
  state: nodeStateSchema,
  mastery: masterySchema,
});

export const skillTreeSchema = z.object({
  categories: z.array(categorySchema).min(1),
  nodes: z.array(skillNodeSchema).min(1),
  /** Nodes the final project needs mastered. */
  targetNodeIds: z.array(z.string().min(1)),
});

// Diagnostic

export const multipleChoiceQuestionSchema = z.object({
  id: z.number().int().positive(),
  type: z.literal('multipleChoice'),
  prompt: z.string().min(1),
  choices: z
    .array(z.object({id: z.string().min(1), text: z.string().min(1)}))
    .min(2),
  /** Absent for a survey question; the backend grades, this is only a hint of kind. */
  graded: z.boolean(),
  allowOther: z.object({placeholder: z.string().optional()}).optional(),
});

export const openEndedQuestionSchema = z.object({
  id: z.number().int().positive(),
  type: z.literal('openEnded'),
  prompt: z.string().min(1),
  placeholder: z.string().optional(),
  /** Set on a question the AI generated to probe an earlier answer. */
  followUpTo: z.number().int().positive().optional(),
});

export const diagnosticQuestionSchema = z.discriminatedUnion('type', [
  multipleChoiceQuestionSchema,
  openEndedQuestionSchema,
]);

export const answerSubmissionSchema = z.object({
  questionId: z.number().int().positive(),
  /** Choice id for multiple choice; empty for open ended. */
  choiceId: z.string(),
  text: z.string().optional(),
  /** Milliseconds from question shown to submit; feeds the stance decider. */
  latencyMs: z.number().int().nonnegative(),
});

export const answerResultSchema = z.object({
  /** Absent for survey and open-ended answers, which are graded asynchronously. */
  isCorrect: z.boolean().optional(),
  /** A probing question to ask next, if the answer warrants one. */
  followUp: openEndedQuestionSchema.optional(),
});

// Stance and next step

export const STANCES = [
  'STANCE_REINFORCE',
  'STANCE_ADVANCE',
  'STANCE_BRIDGE',
  'STANCE_PROJECT_SYNTHESIS',
] as const;
export const stanceSchema = z.enum(STANCES);

const nextStepBase = {
  nodeIds: z.array(z.string().min(1)).min(1),
  /** One line for the student on why they are seeing this. */
  rationale: z.string(),
};

export const nextStepSchema = z.discriminatedUnion('stance', [
  z.object({
    stance: z.literal('STANCE_REINFORCE'),
    ...nextStepBase,
    question: diagnosticQuestionSchema,
  }),
  z.object({
    stance: z.literal('STANCE_ADVANCE'),
    ...nextStepBase,
    lesson: z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      instructions: z.string(),
      starterCode: z.string(),
    }),
  }),
  z.object({
    stance: z.literal('STANCE_BRIDGE'),
    ...nextStepBase,
    challenge: z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      prompt: z.string(),
    }),
  }),
  z.object({
    stance: z.literal('STANCE_PROJECT_SYNTHESIS'),
    ...nextStepBase,
    project: z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      brief: z.string(),
    }),
  }),
]);

// Telemetry from the lesson editor

/**
 * Aggregates, not raw keystrokes: a burst is a count and a duration, so no
 * student-typed text leaves the browser in an event.
 */
export const telemetryEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('typing_burst'),
    at: z.string(),
    keystrokes: z.number().int().nonnegative(),
    durationMs: z.number().int().nonnegative(),
  }),
  z.object({
    type: z.literal('run'),
    at: z.string(),
    ok: z.boolean(),
  }),
  z.object({
    type: z.literal('error'),
    at: z.string(),
    errorType: z.string(),
    line: z.number().int().positive().optional(),
  }),
  z.object({
    type: z.literal('idle'),
    at: z.string(),
    durationMs: z.number().int().nonnegative(),
  }),
]);

export const telemetryBatchSchema = z.object({
  sessionId: z.string().min(1),
  lessonId: z.string().min(1),
  events: z.array(telemetryEventSchema).min(1),
});

export const hintSchema = z.object({
  id: z.string().min(1),
  /** 1 is a nudge; higher levels give more. */
  level: z.number().int().min(1),
  text: z.string().min(1),
});

export const telemetryAckSchema = z.object({
  hints: z.array(hintSchema),
});

// Growth

export const growthReportSchema = z.object({
  perNode: z.array(
    z.object({
      nodeId: z.string().min(1),
      pre: z.number().min(0).max(1),
      post: z.number().min(0).max(1),
      /** post - pre, may be negative. */
      delta: z.number().min(-1).max(1),
    })
  ),
  /** Nodes where the post-diagnostic shows a gap. */
  gapNodeIds: z.array(z.string().min(1)),
  reteachAvailable: z.boolean(),
});
