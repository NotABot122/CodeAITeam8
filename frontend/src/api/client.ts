import {z} from 'zod';

import {
  answerResultSchema,
  growthReportSchema,
  diagnosticQuestionSchema,
  nextStepSchema,
  skillTreeSchema,
  telemetryAckSchema,
} from './schema';
import type {
  AnswerResult,
  AnswerSubmission,
  DiagnosticQuestion,
  GrowthReport,
  NextStep,
  SkillTree,
  TelemetryAck,
  TelemetryBatch,
} from './types';

export interface ApiClient {
  getSkillTree(): Promise<SkillTree>;
  getDiagnostic(): Promise<DiagnosticQuestion[]>;
  submitAnswer(answer: AnswerSubmission): Promise<AnswerResult>;
  getNextStep(): Promise<NextStep>;
  sendTelemetry(batch: TelemetryBatch): Promise<TelemetryAck>;
  getGrowthReport(): Promise<GrowthReport>;
}

async function request<T>(
  schema: z.ZodType<T>,
  url: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {'Content-Type': 'application/json', ...init?.headers},
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${url} failed: ${response.status}`);
  }
  // A response that does not match the contract fails here, at the boundary,
  // not somewhere inside a component.
  return schema.parse(await response.json());
}

/** Talks to the Rails backend. Paths other than skill_tree are proposed. */
export function createHttpClient(baseUrl: string): ApiClient {
  const base = `${baseUrl}/api/v1/student`;
  const post = (body: unknown): RequestInit => ({
    method: 'POST',
    body: JSON.stringify(body),
  });
  return {
    getSkillTree: () => request(skillTreeSchema, `${base}/skill_tree`),
    getDiagnostic: () =>
      request(z.array(diagnosticQuestionSchema), `${base}/diagnostic`),
    submitAnswer: answer =>
      request(answerResultSchema, `${base}/answers`, post(answer)),
    getNextStep: () => request(nextStepSchema, `${base}/next_step`),
    sendTelemetry: batch =>
      request(telemetryAckSchema, `${base}/telemetry`, post(batch)),
    getGrowthReport: () => request(growthReportSchema, `${base}/growth_report`),
  };
}
