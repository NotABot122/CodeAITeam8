import {createTheme} from '@mui/material';

// Team Rubber Ducky: duck yellow brand, orange Run (the beak), Geist/Space Grotesk, 6-12px radii.
export function makeTheme(mode: 'light' | 'dark') {
  const dark = mode === 'dark';
  return createTheme({
    palette: {
      mode,
      primary: {main: dark ? '#ffd23f' : '#ffc933', dark: dark ? '#ffe28a' : '#8a5a00', contrastText: '#1f1a0a'},
      secondary: {main: '#f46800'},
      success: {main: dark ? '#4cc38a' : '#1a7f4b'},
      error: {main: dark ? '#ff7a8a' : '#c8102e'},
      warning: {main: '#e8a200'},
      background: dark ? {default: '#17140c', paper: '#221e12'} : {default: '#fffaf0', paper: '#ffffff'},
      divider: dark ? '#3d3620' : '#eadfc4',
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
