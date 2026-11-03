import type {
  DiagnosticQuestion,
  GrowthReport,
  NextStep,
  SkillTree,
} from '../types';

export const MOCK_SKILL_TREE: SkillTree = {
  categories: [
    {id: 'foundations', title: 'Foundations'},
    {id: 'conditionals', title: 'Conditionals / Boolean Logic'},
    {id: 'iteration', title: 'Iteration / Loops'},
    {id: 'data', title: 'Data & Lists'},
    {id: 'procedures', title: 'Procedures'},
  ],
  nodes: [
    {
      id: 'variables',
      title: 'Variables',
      description: 'Name a value and change it over time.',
      categories: ['foundations'],
      requires: [],
      state: 'MASTERED',
      mastery: {conceptual: 0.92, syntax: 0.88, problemSolving: 0.85},
    },
    {
      id: 'expressions',
      title: 'Expressions',
      description: 'Combine values with operators.',
      categories: ['foundations'],
      requires: ['variables'],
      state: 'MASTERED',
      mastery: {conceptual: 0.85, syntax: 0.9, problemSolving: 0.8},
    },
    {
      id: 'booleans',
      title: 'Booleans',
      description: 'True, false, and, or, not.',
      categories: ['conditionals'],
      requires: ['expressions'],
      state: 'MASTERED',
      mastery: {conceptual: 0.8, syntax: 0.82, problemSolving: 0.75},
    },
    {
      id: 'if-statements',
      title: 'If Statements',
      description: 'Run code only when a condition holds.',
      categories: ['conditionals'],
      requires: ['booleans'],
      state: 'AVAILABLE',
      mastery: {conceptual: 0.55, syntax: 0.6, problemSolving: 0.4},
    },
    {
      id: 'for-loops',
      title: 'For Loops',
      description: 'Repeat code a known number of times.',
      categories: ['iteration'],
      requires: ['expressions'],
      state: 'AVAILABLE',
      mastery: {conceptual: 0.35, syntax: 0.5, problemSolving: 0.2},
    },
    {
      id: 'lists',
      title: 'Lists',
      description: 'Store and index many values.',
      categories: ['data'],
      requires: ['variables'],
      state: 'AVAILABLE',
      mastery: {conceptual: 0.3, syntax: 0.25, problemSolving: 0.1},
    },
    {
      id: 'while-loops',
      title: 'While Loops',
      description: 'Repeat code until a condition changes.',
      categories: ['conditionals', 'iteration'],
      requires: ['if-statements', 'for-loops'],
      state: 'LOCKED',
      mastery: {conceptual: 0, syntax: 0, problemSolving: 0},
    },
    {
      id: 'list-filtering',
      title: 'List Filtering',
      description: 'Loop over a list and keep what matches.',
      categories: ['data', 'iteration'],
      requires: ['lists', 'for-loops'],
      state: 'LOCKED',
      mastery: {conceptual: 0, syntax: 0, problemSolving: 0},
    },
    {
      id: 'procedures',
      title: 'Procedures',
      description: 'Name a block of code and reuse it.',
      categories: ['procedures'],
      requires: ['if-statements'],
      state: 'LOCKED',
      mastery: {conceptual: 0, syntax: 0, problemSolving: 0},
    },
  ],
  targetNodeIds: ['while-loops', 'list-filtering', 'procedures'],
};

export const MOCK_DIAGNOSTIC: DiagnosticQuestion[] = [
  {
    id: 1,
    type: 'multipleChoice',
    prompt: 'After `x = 3` and then `x = x + 2`, what is the value of x?',
    graded: true,
    choices: [
      {id: 'a', text: '3'},
      {id: 'b', text: '5'},
      {id: 'c', text: '2'},
      {id: 'd', text: 'It causes an error'},
    ],
  },
  {
    id: 2,
    type: 'multipleChoice',
    prompt: 'Which situation is best suited to a while loop?',
    graded: true,
    allowOther: {placeholder: 'Something else...'},
    choices: [
      {id: 'a', text: 'Printing a name exactly 10 times'},
      {id: 'b', text: 'Asking for a password until it is correct'},
      {id: 'c', text: 'Adding two numbers'},
    ],
  },
  {
    id: 3,
    type: 'openEnded',
    prompt: 'Explain what a variable is in your own words.',
    placeholder: 'A variable is...',
  },
];

/** Cycled by the mock client so every stance can be previewed. */
export const MOCK_NEXT_STEPS: NextStep[] = [
  {
    stance: 'STANCE_REINFORCE',
    nodeIds: ['if-statements'],
    rationale: 'Your if-statement answers were close. One more check.',
    question: {
      id: 11,
      type: 'multipleChoice',
      graded: true,
      prompt: 'What does `if x > 3` do when x is exactly 3?',
      choices: [
        {id: 'a', text: 'Runs the block'},
        {id: 'b', text: 'Skips the block'},
        {id: 'c', text: 'Causes an error'},
      ],
    },
  },
  {
    stance: 'STANCE_ADVANCE',
    nodeIds: ['for-loops'],
    rationale: 'You are ready for loops.',
    lesson: {
      id: 'lesson-for-loops',
      title: 'Your first for loop',
      instructions: 'Print the numbers 1 to 5 using a for loop.',
      starterCode: 'for i in range(1, 6):\n    # your code here\n',
    },
  },
  {
    stance: 'STANCE_BRIDGE',
    nodeIds: ['if-statements', 'for-loops'],
    rationale: 'You know both. Try them together.',
    challenge: {
      id: 'challenge-evens',
      title: 'Count the even numbers',
      prompt: 'Loop over 1 to 20 and print only the even numbers.',
    },
  },
  {
    stance: 'STANCE_PROJECT_SYNTHESIS',
    nodeIds: ['while-loops', 'list-filtering', 'procedures'],
    rationale: 'You have the skills for the final project.',
    project: {
      id: 'project-quiz-game',
      title: 'Build a quiz game',
      brief: 'Use loops, lists, and procedures to build a quiz.',
    },
  },
];

export const MOCK_GROWTH: GrowthReport = {
  perNode: [
    {nodeId: 'variables', pre: 0.4, post: 0.92, delta: 0.52},
    {nodeId: 'if-statements', pre: 0.2, post: 0.7, delta: 0.5},
    {nodeId: 'while-loops', pre: 0.1, post: 0.45, delta: 0.35},
  ],
  gapNodeIds: ['while-loops'],
  reteachAvailable: true,
};
