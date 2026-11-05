// Shapes returned by webapi/ (a thin JSON layer over engine.session). Keep in sync with webapi/service.py.
export type Stage = 0 | 1 | 2 | 3;
/** paused: the level the student left for an inserted practice; they come back to it next. */
export type NodeStatus = 'done' | 'current' | 'paused' | 'todo';

export interface PathNode {
  id: string;
  kind: 'level' | 'practice';
  title: string;
  number: number | null;
  status: NodeStatus;
  concepts: string[];
  afterLevelId: string | null;
}

export interface ConceptProgress {
  id: string;
  name: string;
  stage: Stage;
  stageName: string;
  inProject: boolean;
}

export interface QuizQuestion {
  id: string;
  type: 'predict' | 'explain';
  prompt: string;
  code?: string;
  choices?: string[];
}

export interface NextOption {
  kind: 'revision' | 'next_topic' | 'new_theme' | 'all_done';
  label: string;
  project: string | null;
  concept: string | null;
  topic: string | null;
}

export interface NextStep {kind: string; reason: string; options: NextOption[]}

export interface ProblemView {
  id: string;
  kind: 'level' | 'practice';
  format: 'code' | 'quiz';
  questions: QuizQuestion[] | null;
  title: string;
  number: number | null;
  label: string;
  instructions: string;
  concepts: string[];
  hintCount: number;
  hintsSeen: number;
  attempts: number;
  /** The functions this problem's answer should use. [] means it needs none; null means no bank was written. */
  functions: FunctionInfo[] | null;
  /** Why this practice problem is here: after a passed level, after repeated tries, or planned by the readiness check. */
  inserted: 'after_level' | 'struggle' | 'planned' | null;
  /** The level the student goes back to after this practice (only for 'struggle'). */
  returnTo: {id: string; title: string} | null;
  /** Adaptive support for code problems (engine/support.py): how much help this problem gets right now. */
  support?: SupportView;
}

/** Help fades as the student's level rises: full -> guided -> light -> minimal. Being stuck adds a level of help. */
export interface SupportView {
  level: 'full' | 'guided' | 'light' | 'minimal' | 'legacy';
  autoHintAfter: number | null;
  functionBank: 'full' | 'names' | 'hidden';
  errorDetail: 'full' | 'brief';
  nameMistake: boolean;
  stuck: boolean;
  /** An outline of the function to write, offered until the student has started it. */
  outline: {name: string; text: string} | null;
  suggestBlocks: boolean;
}

export interface FunctionInfo {
  call: string;
  summary: string;
  example: string | null;
}

/** The lesson pathway the Strands Decider 2B picked after the readiness check (student view: no stances or scores). */
export interface PathwayView {
  id: string;
  title: string;
  summary: string;
  message: string;
  decidedBy: 'ai' | 'rules';
  grade: number | null;
  standards: {id: string; skill: string}[];
  steps: {title: string; status: 'done' | 'current' | 'todo'}[];
}
export interface PathwayResult {pathway: PathwayView; state: StudentState}

/** Projects with the same skills and different stories; the student's interests suggest one (engine/matching.py). */
export interface ProjectChoice {project: string; title: string; pitch: string; suggested: boolean; current: boolean; custom?: boolean}
/** Why a project was suggested (engine/matching.py). Plain sentences; never stages or scores. */
export interface ProjectMatch {
  project: string; title: string; pitch: string;
  /** Interests: the goal they picked and the words they typed. */
  because: string[];
  /** Skills: what the check is confident about and what they warm up on first. */
  fit: string[];
  /** What they typed, when no ready-made story matched it: an idea for "Make it yours". */
  themeIdea: string | null;
}
export interface ProjectChoices {choices: ProjectChoice[]; locked: boolean; topic: string; match?: ProjectMatch | null}

/** A synthetic sample student for demos (no real data). */
export interface ImportSample {id: string; label: string; about: string}
/** POST /api/import: the readiness check's closing screen for the imported results, and the new student's state. */
export interface ImportResult {
  result: {student_id: string; notices: string[]; match?: ProjectMatch | null; next_stop?: {activity: {id: string; title: string} | null; project?: string}};
  state: StudentState;
}
export interface ChooseResult extends ProjectChoices {state: StudentState}

export interface StudentState {
  studentId: string;
  project: {id: string; title: string; topic: string};
  complete: boolean;
  onFallback: boolean;
  notices: string[];
  problem: ProblemView | null;
  code: string;
  path: PathNode[];
  concepts: ConceptProgress[];
  diagnostic: 'none' | 'in_progress' | 'finished' | 'applied';
  nextStep: NextStep | null;
  themed: boolean;
  aiAvailable: boolean;
  pathway: PathwayView | null;
  /** When "Make it yours" applies: now (first topic), later (it's ahead on the pathway), or null. */
  themeable: 'now' | 'later' | null;
  streakLength: number;
  maxStage: number;
  stageNames: string[];
}

export type SubmitStatus =
  | 'passed' | 'failed' | 'timeout' | 'syntax_error' | 'import_error' | 'ungraded'
  // From POST /hint (a hint on request, not a submission):
  | 'hint' | 'no_hints' | 'complete';

export interface StageChange {
  concept: string;
  conceptName: string;
  oldStage: number;
  newStage: number;
  oldStageName: string;
  newStageName: string;
}

export interface QuestionResult {
  id: string;
  type: 'predict' | 'explain';
  correct: boolean | null;
  message: string;
  explanation: string | null;
  score: number | null;
  feedback: string | null;
}

export interface Outcome {
  status: SubmitStatus;
  passed: boolean;
  messages: string[];
  hint: string | null;
  hintSource: 'ai' | 'authored' | null;
  stageChanges: StageChange[];
  complete: boolean;
  notices: string[];
  questionResults: QuestionResult[];
  nextStep: NextStep | null;
  /** Plain-language explanation of a Python error. */
  explanation?: {text: string; line: number | null; kind: string; source: 'ai' | 'rules'} | null;
  /** The likely mistake behind a failed run, at the levels that name it: where to look, never the fix. */
  mistake?: {id: string; tip: string} | null;
  stuck?: string[];
}

export interface Health {ok: boolean; project: string; ai: boolean; aiReason: string | null; adaptive: boolean; dev?: boolean; devLocked?: boolean}

/** Dev-only AI inspector (server started with --dev): one recorded model call. */
export interface AiCall {
  id: number;
  at: string;
  feature: {name: string; what: string};
  model: string;
  student: string | null;
  system: string;
  input: string;
  maxTokens: number;
  tools: {name: string; description: string; schema: unknown}[];
  requireTool: boolean;
  ok: boolean;
  latencyMs: number;
  outputText?: string | null;
  toolName?: string | null;
  toolInput?: unknown;
  inputTokens?: number;
  outputTokens?: number;
  error?: string;
}
export interface AiInfo {ai: boolean; aiReason: string | null; model: string | null; modelSource?: string; safety?: string; features: {name: string; what: string; model: string | null}[]}
export interface SubmitResult {outcome: Outcome; state: StudentState}
export interface StartResult {message: string; built: boolean; state: StudentState}
export interface ThemeResult {built: boolean; message: string; state: StudentState}
export type BlocksResult =
  | {ok: true; workspace: import('../blocks/format').WorkspaceState; blockCount: number}
  | {ok: false; reason: 'syntax_error' | 'unsupported' | 'too_long' | 'too_complex'; message: string; line: number | null};

export interface CourseView {
  studentId: string;
  now: {project: string; isReview: boolean; complete: boolean};
  topics: {id: string; title: string; status: 'done' | 'current' | 'upcoming'; concepts: string[]}[];
  reviewsDone: string[];
  concepts: {id: string; name: string; stage: number; stageName: string; inProject: boolean}[];
  quest: {status: 'none' | 'in_progress' | 'finished' | 'applied'; seeded: string[]};
  nextStep: string | null;
  stageNames: string[];
}
