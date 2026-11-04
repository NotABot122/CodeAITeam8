// Shapes returned by webapi/ (a thin JSON layer over engine.session). Keep in sync with webapi/service.py.
export type Stage = 0 | 1 | 2 | 3;
export type NodeStatus = 'done' | 'current' | 'todo';

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
}

export interface FunctionInfo {
  call: string;
  summary: string;
  example: string | null;
}

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
  nextStep: NextStep | null;
  themed: boolean;
  aiAvailable: boolean;
  streakLength: number;
  maxStage: number;
  stageNames: string[];
}

export type SubmitStatus =
  | 'passed' | 'failed' | 'timeout' | 'syntax_error' | 'import_error' | 'ungraded';

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
}

export interface Health {ok: boolean; project: string; ai: boolean; aiReason: string | null; adaptive: boolean}
export interface SubmitResult {outcome: Outcome; state: StudentState}
export interface StartResult {message: string; built: boolean; state: StudentState}
export interface ThemeResult {built: boolean; message: string; state: StudentState}
export type BlocksResult =
  | {ok: true; workspace: import('../blocks/format').WorkspaceState; blockCount: number}
  | {ok: false; reason: 'syntax_error' | 'unsupported' | 'too_long' | 'too_complex'; message: string; line: number | null};
