// Shapes from /api/quest (the readiness quest in diagnostic/). The quest never sends stages, scores or answer keys.
import type {ProjectMatch} from '@/api/types';
export interface Zone {id: string; name: string; story: string; done?: boolean; current?: boolean}
export interface Choice {id: string; label: string}
export interface QuestOptions {title: string; guide: string; message: string; buddies: Choice[]; goals: Choice[]; zones: Zone[]}
export interface Game {guide: string; xp: number; rank: string; streak: number; badges: {id: string; name: string}[]}

export interface ItemStep {
  kind: 'item' | 'booster';
  id: string;
  type: 'choice' | 'spot' | 'trace' | 'order' | 'sort';
  prompt: string;
  options?: {id: string; text: string}[];
  cards?: {id: string; text: string}[];
  buckets?: {id: string; text: string}[];
  display?: 'rows' | 'belt' | 'chips';
  /** A code block shown under the prompt. The prompt sentence itself never contains code. */
  code?: {lang: 'python' | 'sql'; text: string};
  /** Rows of data shown under the prompt. */
  table?: {columns: string[]; rows: string[][]};
  /** 'code': draw every option and card in the code font. Text options may still hold `inline code`. */
  option_format?: 'text' | 'code';
  zone?: {id: string; name: string};
  intro?: string;
}
export interface ExplainStep {
  kind: 'explain';
  id: string;
  type: 'text';
  prompt: string;
  intro?: string;
  can_skip: boolean;
  max_chars: number;
  zone?: {id: string; name: string};
}
export type Step = ItemStep | ExplainStep;

export interface NextStepResult {
  done: false;
  step: Step;
  zones: Zone[];
  notices?: string[];
}
export interface SkillNode {id: string; name: string; zone: string; parents: string[]; state: 'locked' | 'open' | 'star'; try_next: boolean}
export interface QuestDone {
  done: true;
  message: string;
  goal_connection?: string;
  next_stop?: {zone: string; activity: {id: string; title: string} | null; project?: string};
  /** Why the suggested project fits: interests chose the story, the check's results chose the start. */
  match?: ProjectMatch | null;
  skill_tree: SkillNode[];
  zones: Zone[];
}
export type QuestNext = NextStepResult | QuestDone;

export interface QuestStart {
  student_id: string;
  /** e.g. the interests text was dropped because it had personal details. */
  notices?: string[];
  welcome: {title: string; message: string; buddies: Choice[]; goals: Choice[]; zones: Zone[]; game: Game};
  first: QuestNext;
}
export interface Feedback {
  correct: boolean | null;
  message: string;
  tip: string | null;
  new_badges: {id: string; name: string}[];
  zone_cleared: string | {name: string} | null;
}
export interface AnswerResult {feedback: Feedback; game: Game; zones: Zone[]}
