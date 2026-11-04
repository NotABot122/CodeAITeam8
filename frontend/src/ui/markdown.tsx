import {Box, Typography} from '@mui/material';
import type {ReactNode} from 'react';

// Instructions are teacher-authored markdown: headings, paragraphs, lists, tables, fenced code, **bold**, `code`.
// Rendered as React nodes (never innerHTML), so nothing in the text can inject markup.

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(
      tok.startsWith('`') ? (
        <Box component="code" key={i++} sx={{px: 0.6, py: 0.1, borderRadius: '4px', bgcolor: 'action.hover', fontFamily: 'var(--code-font)', fontSize: '0.9em'}}>
          {tok.slice(1, -1)}
        </Box>
      ) : (
        <strong key={i++}>{tok.slice(2, -2)}</strong>
      )
    );
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({source}: {source: string}) {
  const lines = source.replace(/\r/g, '').split('\n');
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith('```')) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
      i++;
      blocks.push(
        <Box key={key++} component="pre" sx={{m: 0, my: 1.5, p: 1.5, borderRadius: '8px', bgcolor: 'action.hover', overflowX: 'auto', fontFamily: 'var(--code-font)', fontSize: 13, lineHeight: 1.6}}>
          {code.join('\n')}
        </Box>
      );
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      blocks.push(
        <Typography key={key++} component={`h${Math.min(level + 1, 6)}` as 'h2'} variant={level === 1 ? 'h5' : 'subtitle1'} sx={{mt: level === 1 ? 0 : 2.5, mb: 1, fontWeight: 700}}>
          {inline(h[2])}
        </Typography>
      );
      i++;
      continue;
    }
    if (line.trim().startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        const cells = lines[i].trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
        if (!cells.every(c => /^:?-+:?$/.test(c))) rows.push(cells);
        i++;
      }
      const [head, ...body] = rows;
      blocks.push(
        <Box key={key++} sx={{overflowX: 'auto', my: 1.5}}>
          <Box component="table" sx={{borderCollapse: 'collapse', fontSize: 14, '& th, & td': {border: 1, borderColor: 'divider', px: 1.25, py: 0.6, textAlign: 'left'}, '& th': {bgcolor: 'action.hover'}}}>
            <thead><tr>{head.map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
            <tbody>{body.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
          </Box>
        </Box>
      );
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      blocks.push(
        <Box key={key++} component={ordered ? 'ol' : 'ul'} sx={{my: 1, pl: 3, '& li': {mb: 0.5}}}>
          {items.map((t, j) => <li key={j}>{inline(t)}</li>)}
        </Box>
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|\||\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++]);
    blocks.push(<Typography key={key++} sx={{my: 1, lineHeight: 1.65}}>{inline(para.join(' '))}</Typography>);
  }
  return <>{blocks}</>;
}
