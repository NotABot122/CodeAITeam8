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
  streak: number;
}

export interface ProblemView {
  id: string;
  kind: 'level' | 'practice';
  title: string;
  number: number | null;
  label: string;
  instructions: string;
  concepts: string[];
  hintCount: number;
  hintsSeen: number;
  attempts: number;
}

export interface StudentState {
  studentId: string;
  project: {id: string; title: string};
  complete: boolean;
  onFallback: boolean;
  notices: string[];
  problem: ProblemView | null;
  code: string;
  path: PathNode[];
  concepts: ConceptProgress[];
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

export interface Outcome {
  status: SubmitStatus;
  passed: boolean;
  messages: string[];
  hint: string | null;
  hintSource: 'ai' | 'authored' | null;
  stageChanges: StageChange[];
  complete: boolean;
  notices: string[];
}

export interface Health {ok: boolean; project: string; ai: boolean; aiReason: string | null; adaptive: boolean}
export interface SubmitResult {outcome: Outcome; state: StudentState}
export interface ThemeResult {built: boolean; message: string; state: StudentState}
