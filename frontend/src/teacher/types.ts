// Shapes from /api/teacher (webapi/teacher.py).
export interface Row {
  studentId: string;
  status: 'quest' | 'working' | 'finished' | 'new';
  quest: string;
  project: string;
  current: string | null;
  attempts: number;
  passed: number;
  completedProjects: number;
  onFallback: boolean;
  needsHelp: string | null;
  stages: Record<string, number>;
  lastActive: string | null;
}
export interface Overview {
  students: Row[];
  summary: {total: number; quest: number; working: number; finished: number; new: number; needHelp: number};
  concepts: {id: string; name: string; counts: number[]}[];
  stageNames: string[];
  truncated: boolean;
}
export interface ConceptReport {
  concept: string; zone: string; stage: number; stage_name: string; confidence: number; borderline: boolean;
  questions_asked: number; mistakes: string[]; adjusted_by_ai: unknown;
  explain: {status: string; text: string | null; stage: number | null; quotes: string[]; flags: string[]; rationale: string | null} | null;
}
export interface QuestReport {
  finished: boolean;
  goal: {label: string; own_words: string | null};
  minutes_estimate: number;
  within_target_minutes: boolean;
  fixed_order_fallback: {used: boolean; reason: string | null};
  concepts: ConceptReport[];
  placement: {next_task_id: string | null; reason: string; practice_ahead: string[]; fallback: boolean};
  teacher_note: string;
  ai: {used: boolean; model_id: string | null; fell_back: boolean};
  content_filter: {responses_held_back: string[]; follow_up: string | null};
}
export interface ProjectProgress {
  id: string; title: string; complete: boolean; current: string; onFallback: boolean;
  attempts: Record<string, number>; hintsSeen: Record<string, number>; passed: string[]; needsHelp: string | null;
  route: {selected: string | null; reason: string | null; policy: string | null; at: string | null}[];
}
export interface Detail {
  studentId: string;
  concepts: {id: string; name: string; stage: number; stageName: string}[];
  projects: ProjectProgress[];
  completed: {project: string; topic: string; at: string}[];
  nextStep: string | null;
  seededFromQuest: Record<string, number>;
  quest: QuestReport | null;
  lastActive: string | null;
}
export interface Check {project?: string; passed: boolean; problems: string[]; notices: string[]}
export interface ContentCheck {projects: Check[]; quest: Check}
