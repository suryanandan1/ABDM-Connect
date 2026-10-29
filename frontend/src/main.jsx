import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import App from './App'

// One place for colours, type and component defaults. Pages only add layout.
const border = '#E3E8EF'
const theme = createTheme({
  palette: {
    primary: { main: '#1D4F91', dark: '#163C6E', light: '#E9F0FA', contrastText: '#fff' },
    secondary: { main: '#0E8A86', dark: '#0B6E6B', light: '#E6F5F4', contrastText: '#fff' },
    success: { main: '#15803D', dark: '#166534' },
    warning: { main: '#B45309', dark: '#92400E' },
    error: { main: '#C62828', dark: '#9F1D1D' },
    info: { main: '#1D4F91', dark: '#163C6E' },
    background: { default: '#F5F7FA', paper: '#FFFFFF' },
    text: { primary: '#1E293B', secondary: '#5B6B7F' },
    divider: border,
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h5: { fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.01em' },
    h6: { fontSize: '1.0625rem', fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
    overline: { fontWeight: 600, letterSpacing: '0.06em', lineHeight: 1.6 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 8 } },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          '&.MuiPaper-elevation1': { border: `1px solid ${border}`, boxShadow: '0 1px 2px rgba(16, 24, 40, 0.04)' },
        },
      },
    },
    MuiAppBar: { defaultProps: { elevation: 0 } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: border },
        head: {
          fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
          color: '#5B6B7F', backgroundColor: '#F8FAFC', whiteSpace: 'nowrap',
        },
        sizeSmall: { padding: '10px 14px' },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 6 } } },
    MuiOutlinedInput: { styleOverrides: { root: { backgroundColor: '#fff' }, notchedOutline: { borderColor: '#CBD5E1' } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 14 } } },
    MuiDialogTitle: { styleOverrides: { root: { fontWeight: 600, fontSize: '1.125rem' } } },
    MuiAlert: { styleOverrides: { root: { borderRadius: 10 } } },
    MuiTab: { styleOverrides: { root: { textTransform: 'none', fontWeight: 600, minHeight: 44 } } },
    MuiTabs: { styleOverrides: { root: { minHeight: 44 } } },
    MuiTooltip: { defaultProps: { arrow: true } },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
