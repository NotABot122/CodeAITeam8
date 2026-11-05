import {renderToString} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {readResultsFile} from './ImportDialog';
import Landing from './Landing';

describe('importing results from an earlier lesson', () => {
  it('reads a results file as JSON in the browser', async () => {
    const file = new File([JSON.stringify({format: 'codeai-lesson-export', version: 1, concepts: {}})], 'results.json');
    expect(await readResultsFile(file)).toEqual({format: 'codeai-lesson-export', version: 1, concepts: {}});
  });

  it('turns away files that are not JSON or are far too big', async () => {
    await expect(readResultsFile(new File(['not json'], 'x.json'))).rejects.toThrow("isn't valid JSON");
    await expect(readResultsFile(new File(['x'.repeat(40 * 1024)], 'big.json'))).rejects.toThrow('too big');
  });

  it('offers the import on the landing page', () => {
    const html = renderToString(<Landing grade={null} onGrade={() => {}} onStart={() => {}} onSkip={() => {}} onImport={() => {}} resume={null} />);
    expect(html).toContain('Already did a lesson like this?');
    expect(html).toContain('Import my results');
  });
});
