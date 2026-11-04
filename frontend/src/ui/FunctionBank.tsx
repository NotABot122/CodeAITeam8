import {Box, Button, ButtonBase, Paper, Popover, Typography} from '@mui/material';
import {useId, useState} from 'react';

import type {FunctionInfo} from '@/api/types';

// The functions this problem's answer should use, on the left of the text editor (where the block
// toolbox sits in Blocks mode). Choosing one opens a short description; nothing is inserted.
// The bank fades with the student's level (engine/support.py): full (description and example),
// names (description only), hidden (closed until the student opens it).
export type BankMode = 'full' | 'names' | 'hidden';
export default function FunctionBank({functions, mode = 'full'}: {functions: FunctionInfo[]; mode?: BankMode}) {
  const [open, setOpen] = useState<{el: HTMLElement; fn: FunctionInfo} | null>(null);
  const [shown, setShown] = useState(false);
  const titleId = useId();

  if (mode === 'hidden' && !shown) {
    return (
      <Paper variant="outlined" component="nav" aria-label="Functions for this problem"
        sx={{flex: {xs: 'none', sm: '0 0 196px'}, p: 1.5, borderRadius: '8px', display: 'grid', gap: 1, alignContent: 'start'}}>
        <Typography variant="body2" color="text.secondary">You're ready to work from the instructions. The function list is here if you need it.</Typography>
        <Button size="small" variant="outlined" onClick={() => setShown(true)}>Show functions</Button>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" component="nav" aria-label="Functions for this problem"
      sx={{flex: {xs: 'none', sm: '0 0 196px'}, display: 'flex', flexDirection: 'column', borderRadius: '8px', overflow: 'hidden', minHeight: 0}}>
      <Typography variant="overline" sx={{px: 1.5, pt: 1, lineHeight: 1.6, fontWeight: 700, color: 'text.secondary'}}>Functions to use</Typography>
      {functions.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{px: 1.5, pb: 1.5}}>
          This one doesn't need any functions. The instructions say which Python to use.
        </Typography>
      )}
      <Box component="ul" sx={{listStyle: 'none', m: 0, p: 1, pt: 0.5, display: 'flex', flexDirection: {xs: 'row', sm: 'column'}, flexWrap: 'wrap', gap: 0.75, overflowY: 'auto', '&:empty': {display: 'none'}}}>
        {functions.map(fn => (
          <li key={fn.call}>
            <ButtonBase
              aria-haspopup="dialog"
              aria-expanded={open?.fn === fn}
              onClick={e => setOpen({el: e.currentTarget, fn})}
              sx={{width: '100%', justifyContent: 'flex-start', textAlign: 'left', px: 1, py: 0.75, borderRadius: '6px', border: 1, borderColor: 'divider',
                bgcolor: open?.fn === fn ? 'action.selected' : 'background.paper', fontFamily: 'var(--code-font)', fontSize: 12.5, lineHeight: 1.35,
                wordBreak: 'break-word', '&:hover': {bgcolor: 'action.hover'}, '&.Mui-focusVisible': {outline: '2px solid #1aa6a6', outlineOffset: 1}}}>
              {fn.call}
            </ButtonBase>
          </li>
        ))}
      </Box>

      <Popover
        open={!!open}
        anchorEl={open?.el}
        onClose={() => setOpen(null)}
        anchorOrigin={{vertical: 'top', horizontal: 'right'}}
        transformOrigin={{vertical: 'top', horizontal: 'left'}}
        slotProps={{paper: {role: 'dialog', 'aria-labelledby': titleId, sx: {p: 2, maxWidth: 360, borderRadius: '10px'}}}}
      >
        {open && (
          <>
            <Typography id={titleId} component="h3" sx={{fontFamily: 'var(--code-font)', fontWeight: 700, fontSize: 14, mb: 1}}>{open.fn.call}</Typography>
            <Typography variant="body2" sx={{whiteSpace: 'pre-line'}}>{open.fn.summary}</Typography>
            {open.fn.example && mode === 'full' && (
              <>
                <Typography variant="caption" color="text.secondary" component="p" sx={{mt: 1.5, mb: 0.5, fontWeight: 600}}>Example</Typography>
                <Box component="pre" sx={{m: 0, p: 1, borderRadius: '6px', bgcolor: 'action.hover', fontFamily: 'var(--code-font)', fontSize: 12.5, overflowX: 'auto', whiteSpace: 'pre'}}>
                  {open.fn.example}
                </Box>
              </>
            )}
          </>
        )}
      </Popover>
    </Paper>
  );
}
