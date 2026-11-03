import {ThemeProvider, createTheme} from '@mui/material';
import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {MOCK_DIAGNOSTIC, MOCK_NEXT_STEPS, MOCK_SKILL_TREE} from '@/api/mock/data';
import {createMockClient} from '@/api/mock/mockClient';

import DiagnosticPlayer from './features/diagnostic/DiagnosticPlayer';
import LessonView from './features/lesson/LessonView';
import SkillTree from './features/skilltree/SkillTree';

// React splits adjacent text into nodes joined by <!-- --> markers, escapes
// "&", and Emotion inlines <style> tags; none of that matters for what these
// tests assert.
const render = (node: React.ReactNode) =>
  renderToString(<ThemeProvider theme={createTheme()}>{node}</ThemeProvider>)
    .replace(/<style[^>]*>[\s\S]*?<\/style>/g, '')
    .replace(/<!-- -->/g, '')
    .replace(/&amp;/g, '&');

// Server-side render smoke tests: they catch a component that throws on its
// first render, not layout or interaction problems.
describe('render smoke tests', () => {
  it('draws every skill with its state in an accessible label', () => {
    const html = render(<SkillTree tree={MOCK_SKILL_TREE} />);
    for (const node of MOCK_SKILL_TREE.nodes) {
      expect(html).toContain(`${node.title}: ${node.state.toLowerCase()}`);
    }
  });

  it('draws a filter chip per category', () => {
    const html = render(<SkillTree tree={MOCK_SKILL_TREE} />);
    for (const category of MOCK_SKILL_TREE.categories) {
      expect(html).toContain(category.title);
    }
  });

  it('shows the first diagnostic question', () => {
    const html = render(
      <DiagnosticPlayer client={createMockClient()} questions={MOCK_DIAGNOSTIC} />
    );
    expect(html).toContain('Question 1 of 3');
  });

  it('shows the lesson starter code', () => {
    const step = MOCK_NEXT_STEPS.find(s => s.stance === 'STANCE_ADVANCE');
    if (step?.stance !== 'STANCE_ADVANCE') throw new Error('mock missing advance step');
    const html = render(
      <LessonView
        client={createMockClient()}
        lessonId={step.lesson.id}
        title={step.lesson.title}
        instructions={step.lesson.instructions}
        starterCode={step.lesson.starterCode}
      />
    );
    expect(html).toContain(step.lesson.title);
    expect(html).toContain('range(1, 6)');
  });
});
