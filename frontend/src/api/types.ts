import {z} from 'zod';

import {
  answerResultSchema,
  answerSubmissionSchema,
  categorySchema,
  diagnosticQuestionSchema,
  growthReportSchema,
  hintSchema,
  masterySchema,
  multipleChoiceQuestionSchema,
  nextStepSchema,
  nodeStateSchema,
  openEndedQuestionSchema,
  skillNodeSchema,
  skillTreeSchema,
  stanceSchema,
  telemetryAckSchema,
  telemetryBatchSchema,
  telemetryEventSchema,
} from './schema';

export type NodeState = z.infer<typeof nodeStateSchema>;
export type Mastery = z.infer<typeof masterySchema>;
export type Category = z.infer<typeof categorySchema>;
export type SkillNode = z.infer<typeof skillNodeSchema>;
export type SkillTree = z.infer<typeof skillTreeSchema>;
export type MultipleChoiceQuestion = z.infer<
  typeof multipleChoiceQuestionSchema
>;
export type OpenEndedQuestion = z.infer<typeof openEndedQuestionSchema>;
export type DiagnosticQuestion = z.infer<typeof diagnosticQuestionSchema>;
export type AnswerSubmission = z.infer<typeof answerSubmissionSchema>;
export type AnswerResult = z.infer<typeof answerResultSchema>;
export type Stance = z.infer<typeof stanceSchema>;
export type NextStep = z.infer<typeof nextStepSchema>;
export type TelemetryEvent = z.infer<typeof telemetryEventSchema>;
export type TelemetryBatch = z.infer<typeof telemetryBatchSchema>;
export type TelemetryAck = z.infer<typeof telemetryAckSchema>;
export type Hint = z.infer<typeof hintSchema>;
export type GrowthReport = z.infer<typeof growthReportSchema>;
