import {createTheme} from '@mui/material';

// Tokens follow Code.org's CodeAI component library: purple brand, orange Run, Geist/Space Grotesk, 6-12px radii.
export function makeTheme(mode: 'light' | 'dark') {
  const dark = mode === 'dark';
  return createTheme({
    palette: {
      mode,
      primary: {main: dark ? '#9b93f5' : '#4c42cf', contrastText: dark ? '#14122e' : '#fff'},
      secondary: {main: '#f46800'},
      success: {main: dark ? '#4cc38a' : '#1a7f4b'},
      error: {main: dark ? '#ff7a8a' : '#c8102e'},
      warning: {main: '#e8a200'},
      background: dark ? {default: '#12121a', paper: '#1b1b27'} : {default: '#f7f7fb', paper: '#ffffff'},
      divider: dark ? '#2e2e40' : '#e3e3ee',
    },
    shape: {borderRadius: 8},
    typography: {
      fontFamily: '"Geist", system-ui, -apple-system, "Segoe UI", sans-serif',
      h4: {fontFamily: '"Space Grotesk", "Geist", sans-serif', fontWeight: 700},
      h5: {fontFamily: '"Space Grotesk", "Geist", sans-serif', fontWeight: 700},
      button: {textTransform: 'none', fontWeight: 600},
    },
    components: {
      MuiButton: {styleOverrides: {root: {borderRadius: 8, minHeight: 40}}},
      MuiPaper: {styleOverrides: {root: {backgroundImage: 'none'}}},
    },
  });
}
