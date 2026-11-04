import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import type {CourseView} from '@/api/types';
import {CourseBody} from './CoursePage';

const view: CourseView = {
  studentId: 'x', now: {project: 'Data & Logic', isReview: false, complete: false},
  topics: [
    {id: 'a', title: 'Intro', status: 'done', concepts: ['Variables']},
    {id: 'b', title: 'Data & Logic', status: 'current', concepts: ['Conditionals', 'Loops']},
    {id: 'c', title: 'Functions', status: 'upcoming', concepts: ['Functions']},
  ],
  reviewsDone: ['Review 1'],
  concepts: [{id: 'v', name: 'Variables', stage: 3, stageName: 'Exceeding'}, {id: 'l', name: 'Loops', stage: 0, stageName: 'Missing'}],
  quest: {status: 'applied', seeded: ['Variables']}, nextStep: 'Next: review loops.', stageNames: [],
};

describe('CourseBody', () => {
  it('shows topics with status, concepts and next step', () => {
    const out = renderToString(<CourseBody view={view} />).replace(/<!-- -->/g, '');
    for (const t of ['You are here', 'Done', 'Up next', 'Next: review loops.', 'Review 1', 'Loops: Missing', 'Conditionals · Loops']) expect(out).toContain(t);
  });
});
