import {Box} from '@mui/material';
import {useRef, type KeyboardEvent} from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
  disabled?: boolean;
}

// A plain textarea with a line-number gutter. Tab inserts 4 spaces; Esc then Tab moves focus on (so keyboard
// users aren't trapped); Ctrl/Cmd+Enter runs.
export default function CodeEditor({value, onChange, onRun, disabled}: Props) {
  const gutter = useRef<HTMLDivElement>(null);
  const escaped = useRef(false);
  const lines = value.split('\n').length;

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') { escaped.current = true; return; }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); onRun(); return; }
    if (e.key === 'Tab' && !escaped.current) {
      e.preventDefault();
      const t = e.currentTarget;
      const {selectionStart: a, selectionEnd: b} = t;
      onChange(value.slice(0, a) + '    ' + value.slice(b));
      requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = a + 4; });
      return;
    }
    escaped.current = false;
  };

  return (
    <Box sx={{display: 'flex', border: 1, borderColor: 'divider', borderRadius: '8px', overflow: 'hidden', bgcolor: 'background.paper', flex: '1 0 260px'}}>
      <Box ref={gutter} aria-hidden sx={{py: 1.5, px: 1, textAlign: 'right', color: 'text.disabled', bgcolor: 'action.hover', fontFamily: 'var(--code-font)', fontSize: 13, lineHeight: '20px', userSelect: 'none', overflow: 'hidden'}}>
        {Array.from({length: lines}, (_, i) => <div key={i}>{i + 1}</div>)}
      </Box>
      <Box
        component="textarea"
        aria-label="Your Python code"
        value={value}
        disabled={disabled}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        wrap="off"
        onChange={e => onChange((e.target as HTMLTextAreaElement).value)}
        onKeyDown={onKey}
        onScroll={e => { if (gutter.current) gutter.current.scrollTop = (e.target as HTMLTextAreaElement).scrollTop; }}
        sx={{flex: 1, border: 0, outline: 0, resize: 'none', py: 1.5, px: 1.5, bgcolor: 'transparent', color: 'text.primary', fontFamily: 'var(--code-font)', fontSize: 13, lineHeight: '20px', tabSize: 4, whiteSpace: 'pre', overflow: 'auto',
          '&:focus-visible': {boxShadow: 'inset 0 0 0 2px #1aa6a6'}}}
      />
    </Box>
  );
}
