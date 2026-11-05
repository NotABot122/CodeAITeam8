import {Box, Typography, useTheme} from '@mui/material';
import type {ReactNode} from 'react';

// Code and data shown inside a question: a line-numbered, highlighted code block and a small data table.
// Everything is rendered as React text nodes (never innerHTML), so content can't inject markup.

export type CodeLang = 'python' | 'sql';

const KEYWORDS: Record<CodeLang, RegExp> = {
  python: /^(and|or|not|in|is|if|elif|else|for|while|def|return|None|True|False|import|from|as|with|break|continue|pass|lambda)$/,
  sql: /^(SELECT|FROM|WHERE|AND|OR|NOT|ORDER|BY|ASC|DESC|LIMIT|LIKE|IN|IS|NULL|AS|GROUP|HAVING|COUNT|SUM|MAX|MIN|AVG)$/i,
};
const COMMENT: Record<CodeLang, string> = {python: '#', sql: '--'};
// Strings, numbers, words, and anything else (operators, spaces), in that order.
const TOKEN = /('(?:[^'\\]|\\.)*'?|"(?:[^"\\]|\\.)*"?)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|([^'"A-Za-z0-9_]+|.)/g;

type Kind = 'keyword' | 'string' | 'number' | 'comment' | 'call' | 'plain';

const PALETTE: Record<'light' | 'dark', Record<Kind, string | undefined>> = {
  // Each colour keeps at least 4.5:1 contrast on the block's background.
  light: {keyword: '#7a1fa2', string: '#1f6f2b', number: '#a14a00', comment: '#5f6368', call: '#0b57a8', plain: undefined},
  dark: {keyword: '#d7a6ff', string: '#9ad79f', number: '#ffb36b', comment: '#a8adb3', call: '#8cc4ff', plain: undefined},
};

export function tokenize(line: string, lang: CodeLang): {text: string; kind: Kind}[] {
  const out: {text: string; kind: Kind}[] = [];
  const marker = COMMENT[lang];
  let code = line;
  let comment = '';
  // A comment marker outside a string starts a comment.
  let quote: string | null = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quote) { if (ch === quote && line[i - 1] !== '\\') quote = null; continue; }
    if (ch === "'" || ch === '"') { quote = ch; continue; }
    if (line.startsWith(marker, i)) { code = line.slice(0, i); comment = line.slice(i); break; }
  }
  for (const m of code.matchAll(TOKEN)) {
    const [text, str, num, word] = m;
    if (str) out.push({text, kind: 'string'});
    else if (num) out.push({text, kind: 'number'});
    else if (word) {
      const next = code.slice((m.index ?? 0) + text.length).trimStart();
      out.push({text, kind: KEYWORDS[lang].test(word) ? 'keyword' : next.startsWith('(') ? 'call' : 'plain'});
    } else out.push({text, kind: 'plain'});
  }
  if (comment) out.push({text: comment, kind: 'comment'});
  return out;
}

const LANG_LABEL: Record<CodeLang, string> = {python: 'Python', sql: 'SQL'};

/** A code block: language label, line numbers, light highlighting. Long lines scroll inside the block. */
export function CodeBlock({code, lang = 'python'}: {code: string; lang?: CodeLang}) {
  const mode = useTheme().palette.mode;
  const colours = PALETTE[mode];
  const lines = code.replace(/\n+$/, '').split('\n');
  return (
    <Box component="figure" sx={{m: 0, borderRadius: '10px', border: 1, borderColor: 'divider', bgcolor: mode === 'dark' ? '#16181c' : '#f6f7f9', overflow: 'hidden'}}>
      <Typography component="figcaption" variant="caption" sx={{display: 'block', px: 1.5, py: 0.5, borderBottom: 1, borderColor: 'divider', color: 'text.secondary', fontWeight: 700, letterSpacing: 0.4}}>
        {LANG_LABEL[lang]}
      </Typography>
      <Box component="pre" aria-label={`${LANG_LABEL[lang]} code`} sx={{m: 0, py: 1.25, overflowX: 'auto', fontFamily: 'var(--code-font)', fontSize: 15, lineHeight: 1.7}}>
        {lines.map((line, i) => (
          <Box key={i} component="span" sx={{display: 'flex'}}>
            <Box component="span" aria-hidden sx={{flex: 'none', width: 40, pr: 1.5, textAlign: 'right', color: 'text.disabled', userSelect: 'none'}}>{i + 1}</Box>
            <Box component="span" sx={{whiteSpace: 'pre', pr: 2}}>
              {tokenize(line, lang).map((t, j) => <span key={j} style={colours[t.kind] ? {color: colours[t.kind]} : undefined}>{t.text}</span>)}
              {line === '' ? ' ' : null}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

/** Rows of data, e.g. a few rows of a database table. */
export function DataTable({columns, rows, caption}: {columns: string[]; rows: string[][]; caption?: ReactNode}) {
  return (
    <Box sx={{overflowX: 'auto'}}>
      <Box component="table" sx={{borderCollapse: 'collapse', fontFamily: 'var(--code-font)', fontSize: 15,
        '& th, & td': {border: 1, borderColor: 'divider', px: 1.5, py: 0.75, textAlign: 'left', whiteSpace: 'nowrap'},
        '& th': {bgcolor: 'action.hover', fontWeight: 700}}}>
        {caption && <Box component="caption" sx={{captionSide: 'top', textAlign: 'left', pb: 0.5, fontFamily: 'inherit', color: 'text.secondary'}}>{caption}</Box>}
        <thead><tr>{columns.map(c => <th key={c} scope="col">{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody>
      </Box>
    </Box>
  );
}
