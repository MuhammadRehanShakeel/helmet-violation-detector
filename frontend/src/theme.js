/**
 * theme.js - RoadGuard look: a dark "traffic control room" with safety-yellow accents.
 * Change colours here and the whole app follows.
 */
import { createTheme } from '@mui/material/styles';

export const colors = {
  bg: '#0d141c',
  panel: '#141e29',
  panelHigh: '#1b2836',
  line: '#26364a',
  amber: '#f5b301',
  red: '#ef4444',
  green: '#22c55e',
  blue: '#38bdf8',
  text: '#e6edf3',
  muted: '#8b9bb0',
};

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: colors.amber, contrastText: '#111' },
    secondary: { main: colors.blue },
    error: { main: colors.red },
    success: { main: colors.green },
    warning: { main: '#f59e0b' },
    background: { default: colors.bg, paper: colors.panel },
    text: { primary: colors.text, secondary: colors.muted },
    divider: colors.line,
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
    h1: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700 },
    h4: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, letterSpacing: 0.3 },
    h5: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, letterSpacing: 0.3 },
    h6: { fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, letterSpacing: 0.3 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none', border: `1px solid ${colors.line}` } } },
    MuiCard: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTableCell: { styleOverrides: { root: { borderColor: colors.line } } },
    MuiDialog: { styleOverrides: { paper: { border: `1px solid ${colors.line}` } } },
  },
});

export default theme;
