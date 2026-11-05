import {ThemeProvider} from '@mui/material';
import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import ConceptMeters from './ui/ConceptMeters';
import PathStrip from './ui/PathStrip';
import NextStepPanel from './ui/NextStepPanel';
import QuizPanel, {quizReady} from './ui/QuizPanel';
import Results from './ui/Results';
import {makeTheme} from './ui/theme';
import type {Outcome, StudentState} from './api/types';
import type {ItemStep} from './quest/types';

const wrap = (n: React.ReactNode) =>
  renderToString(<ThemeProvider theme={makeTheme('light')}>{n}</ThemeProvider>).replace(/<style[^>]*>[\s\S]*?<\/style>/g, '').replace(/<!-- -->/g, '');

const state = {
  maxStage: 3,
  concepts: [{id: 'sql', name: 'SQL', stage: 2, stageName: 'Meeting', streak: 0}],
  path: [
    {id: 'level-1', kind: 'level', title: 'Retrieve', number: 1, status: 'done', concepts: ['sql'], afterLevelId: null},
    {id: 'level-2', kind: 'level', title: 'Classify', number: 2, status: 'current', concepts: [], afterLevelId: null},
    {id: 'practice-db-count', kind: 'practice', title: 'Count rows', number: null, status: 'current', concepts: ['sql'], afterLevelId: 'level-1'},
  ],
} as unknown as StudentState;

describe('screens', () => {
  it('labels each level with its state and shows assigned practice', () => {
    const html = wrap(<PathStrip path={state.path} />);
    expect(html).toContain('Level 1: Retrieve, done');
    expect(html).toContain('Level 2: Classify, in progress');
    expect(html).toContain('Practice: Count rows');
  });
  it('exposes stage as a meter', () => {
    const html = wrap(<ConceptMeters state={state} highlight={[]} />);
    expect(html).toContain('aria-valuenow="2"');
    expect(html).toContain('Meeting');
  });
  it('shows failure messages, the hint and stage changes', () => {
    const o: Outcome = {status: 'failed', passed: false, messages: ['Level 1: define get_readings'], hint: 'Try SELECT', hintSource: 'authored',
      stageChanges: [{concept: 'sql', conceptName: 'SQL', oldStage: 1, newStage: 2, oldStageName: 'Beginning', newStageName: 'Meeting'}], complete: false, notices: [], questionResults: [], nextStep: null};
    const html = wrap(<Results outcome={o} />);
    expect(html).toContain('Not quite yet');
    expect(html).toContain('define get_readings');
    expect(html).toContain('Try SELECT');
    expect(html).toContain('Meeting');
  });
  it('draws quiz questions and only enables checking once all are answered', () => {
    const qs = [{id: 'q1', type: 'predict' as const, prompt: 'What prints?', code: 'print(1)', choices: ['1', '2']}, {id: 'q2', type: 'explain' as const, prompt: 'Explain it'}];
    const html = wrap(<QuizPanel questions={qs} answers={{}} onChange={() => {}} results={[]} />);
    expect(html).toContain('What prints?');
    expect(html).toContain('Explain it');
    expect(quizReady(qs, {q1: 0})).toBe(false);
    expect(quizReady(qs, {q1: 0, q2: '  '})).toBe(false);
    expect(quizReady(qs, {q1: 0, q2: 'because'})).toBe(true);
  });
  it('lists next-step options with the first recommended', () => {
    const st = {project: {title: 'Weather Station'}, concepts: [], maxStage: 3, nextStep: {kind: 'revision', reason: 'Loops took extra tries.', options: [
      {kind: 'revision', label: 'Review Loops', project: 'r', concept: 'loops', topic: null},
      {kind: 'next_topic', label: 'Start Lists and Dictionaries', project: 'w', concept: null, topic: 'collections'}]}} as unknown as StudentState;
    const html = wrap(<NextStepPanel state={st} busy={false} error={null} onPick={() => {}} onRestart={() => {}} />);
    expect(html).toContain('Loops took extra tries.');
    expect(html).toContain('Review Loops (recommended)');
    expect(html).toContain('Start Lists and Dictionaries');
  });
});

describe('quest screens', () => {
  it('draws choice, order and sort questions', async () => {
    const {ItemView, responseReady, initialResponse} = await import('./quest/StepView');
    const choice = {kind: 'item', id: 'a', type: 'choice', prompt: 'p', options: [{id: 'x', text: 'rainy'}, {id: 'y', text: '22'}]} as ItemStep;
    expect(wrap(<ItemView step={choice} value={null} onChange={() => {}} disabled={false} />)).toContain('rainy');
    expect(responseReady(choice, null)).toBe(false);
    expect(responseReady(choice, 'x')).toBe(true);
    const order = {kind: 'item', id: 'b', type: 'order', prompt: 'p', cards: [{id: 's1', text: 'Get it'}, {id: 's2', text: 'Give it back'}]} as ItemStep;
    const html = wrap(<ItemView step={order} value={initialResponse(order)} onChange={() => {}} disabled={false} />);
    expect(html).toContain('Move &quot;Get it&quot; down');
    const sort = {kind: 'item', id: 'c', type: 'sort', prompt: 'p', cards: [{id: 'k1', text: 'Mon'}], buckets: [{id: 'h', text: 'Hot'}, {id: 'n', text: 'Not hot'}]} as ItemStep;
    expect(responseReady(sort, {})).toBe(false);
    expect(responseReady(sort, {k1: 'h'})).toBe(true);
    expect(wrap(<ItemView step={sort} value={{}} onChange={() => {}} disabled={false} />)).toContain('Not hot');
  });
});
