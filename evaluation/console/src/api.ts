// Typed client for evaluation/harness/console_server.py. Shapes mirror that file.

export type Status = 'met' | 'partial' | 'not_met' | 'not_tested';

export interface OverviewItem {
  id: string;
  tab: TabId;
  requirement: string;
  source: string;
  status: Status;
  metric: string | null;
  evidence: string;
  caveat: string;
}

export type TabId = 'overview' | 'diagnostic' | 'validation' | 'fallback' | 'safety' | 'hints' | 'rating';

export interface Health {
  ai: boolean;
  ai_reason: string;
  proto_root: string;
}

export interface Level {
  id: string;
  title: string;
  label: string;
  instructions: string;
}

export interface Bug {
  bug_id: string;
  level: string;
  gap: string;
  code: string;
}

export interface LabeledText {
  id: string;
  text: string;
  expected: string;
  case: string;
}

export interface Presets {
  levels: Level[];
  bugs: Bug[];
  correct: Record<string, string>;
  theme_requests: LabeledText[];
  hint_outputs: LabeledText[];
}

export interface ValidateResult {
  status: string;
  passed: boolean;
  messages: string[];
  tests_run: number;
  ms: number;
}

export interface Judge {
  H1?: number;
  H2?: number;
  H3?: number;
  H4?: number;
  H5?: number;
  gives_fix?: boolean;
  rationale?: string;
  error?: string;
}

export interface AgentCoreScore {
  h2: number | null;
  h2_label: string | null;
  h2_explanation: string | null;
  harmfulness: number | null;
  harmfulness_label: string | null;
}

export interface HintResult {
  passed: boolean;
  messages: string[];
  attempt?: number;
  ai?: {
    raw: string | null;
    served: boolean;
    rejected: string | null;
    latency_ms: number | null;
    tokens_in: number | null;
    tokens_out: number | null;
    model_id: string | null;
    judge?: Judge;
  };
  authored?: {text: string | null; judge?: Judge};
  agentcore?: {ai?: AgentCoreScore; authored?: AgentCoreScore};
}

export interface FilterLayer {
  layer: string;
  blocked: boolean | null;
  detail: string;
  ms: number | null;
  note?: string | null;
}

export interface FilterResult {
  direction: 'input' | 'output';
  layers: FilterLayer[];
  proto_outcome: string;
}

export interface E01Row {
  id: string;
  level: string;
  key: 'pass' | 'fail' | 'review';
  grader: 'pass' | 'fail';
  why: string;
  first_message: string;
}

export interface E01 {
  n_scored: number;
  n_review: number;
  agreement: number;
  cohens_kappa: number | null;
  false_pass: string[];
  false_fail: string[];
  rows: E01Row[];
}

export interface E07Scenario {
  scenario: string;
  requirement: string;
  expect: string;
  completed: boolean;
  submissions: number;
  crashed: string | null;
  path: string[];
  notices: string[];
  fallback_events: string[];
}

export interface E07 {
  passed: number;
  n: number;
  scenarios: E07Scenario[];
}

export interface Rates {
  n: number;
  catch_rate: number | null;
  false_block_rate: number | null;
  missed: string[];
  false_blocks: string[];
}

export interface E08Row {
  id: string;
  case: string;
  expected: string;
  text: string;
  local?: boolean;
  local_cat?: string;
  proto: boolean | null;
  proto_cat?: string;
  proto_reason?: string | null;
  guardrail: boolean | null;
  guardrail_filters?: string[];
}

export interface E08 {
  guardrail_id: string | null;
  input: {local: Rates; proto: Rates; guardrail: Rates};
  input_proto_plus_guardrail: Rates | null;
  input_latency_ms: Record<string, number | null>;
  output: {proto: Rates; guardrail: Rates};
  input_rows: E08Row[];
  output_rows: E08Row[];
}

export interface HintBlock {
  n: number;
  judged: number;
  H1: number | null;
  H2: number | null;
  H3: number | null;
  H4: number | null;
  H5: number | null;
  give_away_rate_H2_0: number | null;
  gives_fix_rate: number | null;
  by_attempt: Record<string, {H2: number | null; H3: number | null; gives_fix: number | null}>;
  agentcore_H2_mean?: number | null;
  agentcore_give_away_rate?: number | null;
  agentcore_harmfulness_mean?: number | null;
  agentcore_helpfulness_mean?: number | null;
  judge_vs_agentcore_H2?: {exact: number | null; kappa: number | null};
}

export interface E12Row {
  bug_id: string;
  level: string;
  attempt: number;
  source: 'ai_raw' | 'authored';
  hint: string | null;
  rejected: string | null;
  gap: string;
  judge: Judge;
  ac_h2?: number | null;
  latency_ms?: number;
}

export interface E12 {
  run_id: string;
  hint_model: string;
  judge_model: string;
  bugs: number;
  ai_calls: number;
  ai_rejected: number;
  rejection_reasons: string[];
  ai_latency_p50_ms: number | null;
  ai_latency_p95_ms: number | null;
  ai_tokens_per_hint: {in: number; out: number};
  ai_cost_usd_per_hint: number | null;
  ai_raw: HintBlock;
  authored: HintBlock;
  served: HintBlock;
  escalation_ai_raw: {bugs: number; monotonic: number; non_monotonic: string[]};
  escalation_authored: {bugs: number; monotonic: number; non_monotonic: string[]};
  agentcore: {evaluator_id: string; calls: number} | null;
  rows: E12Row[];
}

export interface RatingItem {
  item_id: string;
  level: string;
  attempt: string;
  check_messages: string;
  student_mistake: string;
  hint: string;
}

export interface RatingAgreement {
  raters: {rater: string; n: number; h2_exact_vs_judge: number | null; give_away_ai: number | null; give_away_teacher: number | null}[];
  between_raters: {raters: string[]; n: number; h2_exact: number} | null;
}

export type DiagCondition = 'no_diagnostic' | 'diagnostic_today' | 'diagnostic_proposed' | 'oracle';

export interface DiagCondSummary {
  n: number;
  completed: number;
  submissions: number;
  failed_on_levels: number;
  gaps: number;
  gaps_practiced_first: number | null;
  practice_unneeded: number;
  start_counts: Record<string, number>;
  by_band: Record<'low' | 'middle' | 'high', {n: number; completed: number; failed_on_levels: number; submissions: number}>;
}

export interface DiagCheck {
  id: string;
  requirement: string;
  passed: boolean;
  detail: string;
}

export interface DiagLesson {
  students: number;
  seed: number;
  labels: Record<DiagCondition, string>;
  checks: DiagCheck[];
  summary: Record<DiagCondition, DiagCondSummary> & {
    diagnostic_accuracy?: {n: number; exact: number; within_one: number; gap_found: number};
    lesson_start_stage_zero?: number;
    stages_used_share?: number | null;
  };
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('Cannot reach the evaluation server. Is console_server running?', 0);
  }
  const data = (await res.json().catch(() => null)) as unknown;
  if (!res.ok) {
    const msg = (data as {error?: string} | null)?.error ?? `Request failed (${res.status}).`;
    throw new ApiError(msg, res.status);
  }
  return data as T;
}

export const api = {
  health: () => call<Health>('GET', 'api/health'),
  overview: () => call<{items: OverviewItem[]; generated_at: string}>('GET', 'api/overview'),
  presets: () => call<Presets>('GET', 'api/presets'),
  e01: () => call<E01>('GET', 'api/results/e01'),
  e07: () => call<E07>('GET', 'api/results/e07'),
  e08: () => call<E08>('GET', 'api/results/e08'),
  e12: () => call<E12>('GET', 'api/results/e12'),
  diag: () => call<DiagLesson>('GET', 'api/results/diag'),
  run: (suite: 'e01' | 'e07' | 'diag') => call<{suite: string; seconds: number}>('POST', `api/run/${suite}`),
  validate: (level: string, code: string) => call<ValidateResult>('POST', 'api/live/validate', {level, code}),
  hint: (body: {level: string; code: string; attempt: number; gap?: string; agentcore: boolean}) =>
    call<HintResult>('POST', 'api/live/hint', body),
  filter: (text: string, direction: 'input' | 'output') =>
    call<FilterResult>('POST', 'api/live/filter', {text, direction}),
  ratingItems: () => call<{items: RatingItem[]; rated: Record<string, string[]>}>('GET', 'api/rating/items'),
  saveRating: (body: Record<string, unknown>) => call<{saved: boolean}>('POST', 'api/rating', body),
  agreement: () => call<RatingAgreement>('GET', 'api/rating/agreement'),
};

export function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? '–' : `${Math.round(x * 100)}%`;
}

export function num(x: number | null | undefined, digits = 2): string {
  return x === null || x === undefined ? '–' : x.toFixed(digits);
}
