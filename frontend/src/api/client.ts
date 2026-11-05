import type {AnswerResult, QuestNext, QuestOptions, QuestStart} from '@/quest/types';
import type {BlocksResult, ChooseResult, CourseView, Health, PathwayResult, ProjectChoices, StartResult, StudentState, SubmitResult, ThemeResult} from './types';

export class ApiError extends Error {
  constructor(message: string, readonly code: string, readonly status: number) {
    super(message);
  }
}

export interface ApiClient {
  health(): Promise<Health>;
  newStudent(): Promise<StudentState>;
  questOptions(): Promise<QuestOptions>;
  /** `interests`: optional words about what the student is into; the server screens them. */
  questStart(buddy: string | null, goal: string | null, interests?: string | null): Promise<QuestStart>;
  questNext(id: string): Promise<QuestNext>;
  questAnswer(id: string, response: unknown, elapsedMs: number | null): Promise<AnswerResult>;
  questFinish(id: string): Promise<unknown>;
  getState(id: string): Promise<StudentState>;
  getCourse(id: string): Promise<CourseView>;
  submit(id: string, code: string): Promise<SubmitResult>;
  /** The projects the student can learn the first topic in, and whether the choice is still open. */
  projectChoices(id: string): Promise<ProjectChoices>;
  /** Pick a project (before it's started). Placement and pathway follow the choice. */
  chooseProject(id: string, project: string): Promise<ChooseResult>;
  /** After the readiness check: the Strands Decider 2B picks and starts a lesson pathway (once per student). */
  pathway(id: string, grade: number): Promise<PathwayResult>;
  /** The next hint for the current problem. Not a submission; it does count as a hint used. */
  hint(id: string, code?: string): Promise<SubmitResult>;
  answer(id: string, answers: Record<string, number | string>): Promise<SubmitResult>;
  startNext(id: string, option: number, theme?: string): Promise<StartResult>;
  buildTheme(id: string, request: string): Promise<ThemeResult>;
  resetTheme(id: string): Promise<StudentState>;
  /** Python -> block workspace. Parses only; the code isn't run or saved. */
  toBlocks(code: string): Promise<BlocksResult>;
}

export function createHttpClient(base = ''): ApiClient {
  async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError("Can't reach the server. Check your connection and try again.", 'network', 0);
    }
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      /* non-JSON error page */
    }
    if (!res.ok) {
      const err = (data as {error?: {code?: string; message?: string}} | null)?.error;
      throw new ApiError(err?.message ?? 'Something went wrong. Try again.', err?.code ?? 'error', res.status);
    }
    return data as T;
  }
  const s = (id: string) => `/api/students/${encodeURIComponent(id)}`;
  return {
    health: () => call('GET', '/api/health'),
    newStudent: () => call('POST', '/api/students'),
    questOptions: () => call('GET', '/api/quest/options'),
    questStart: (buddy, goal, interests) => call('POST', '/api/quest', interests ? {buddy, goal, interests} : {buddy, goal}),
    questNext: id => call('GET', `/api/quest/${encodeURIComponent(id)}/next`),
    questAnswer: (id, response, elapsedMs) => call('POST', `/api/quest/${encodeURIComponent(id)}/answer`, {response, elapsedMs}),
    questFinish: id => call('POST', `/api/quest/${encodeURIComponent(id)}/finish`, {}),
    getState: id => call('GET', s(id)),
    getCourse: id => call('GET', `${s(id)}/course`),
    submit: (id, code) => call('POST', `${s(id)}/submit`, {code}),
    projectChoices: id => call('GET', `${s(id)}/projects`),
    chooseProject: (id, project) => call('POST', `${s(id)}/project`, {project}),
    pathway: (id, grade) => call('POST', `${s(id)}/pathway`, {grade}),
    hint: (id, code) => call('POST', `${s(id)}/hint`, {code}),
    answer: (id, answers) => call('POST', `${s(id)}/answer`, {answers}),
    startNext: (id, option, theme) => call('POST', `${s(id)}/next`, {option, theme}),
    buildTheme: (id, request) => call('POST', `${s(id)}/theme`, {request}),
    resetTheme: id => call('POST', `${s(id)}/theme/reset`, {}),
    toBlocks: code => call('POST', '/api/blocks', {code}),
  };
}
