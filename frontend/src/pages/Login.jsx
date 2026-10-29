import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Alert, Avatar, Box, Button, CircularProgress, Divider, IconButton, InputAdornment, List, ListItemButton,
  ListItemIcon, ListItemText, Stack, TextField, Typography,
} from '@mui/material'
import Visibility from '@mui/icons-material/Visibility'
import VisibilityOff from '@mui/icons-material/VisibilityOff'
import MonitorHeartOutlined from '@mui/icons-material/MonitorHeartOutlined'
import ScienceOutlined from '@mui/icons-material/ScienceOutlined'
import LocalHospitalOutlined from '@mui/icons-material/LocalHospitalOutlined'
import PersonOutlined from '@mui/icons-material/PersonOutlined'
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined'
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined'
import api, { errorText } from '../api'
import { useAuth } from '../App'

// Sample accounts created by `python -m app.seed`. Shown only in development builds.
const SAMPLE_USERS = [
  ['lab1', 'Laboratory (HIP)', ScienceOutlined], ['hospital1', 'Hospital (HIP + HIU)', LocalHospitalOutlined],
  ['asha', 'Patient', PersonOutlined], ['admin', 'Admin', AdminPanelSettingsOutlined],
]

const SAMPLE_PASSWORD = 'Connect@2026'

const FEATURES = [
  [DescriptionOutlined, 'FHIR R4 diagnostic reports', 'Lab results coded with LOINC and validated on every save.'],
  [VerifiedUserOutlined, 'Patient-controlled consent', 'Hospitals read a report only after the patient approves, for a limited time.'],
  [ReceiptLongOutlined, 'Complete audit trail', 'Every request, decision and access is recorded, including denials.'],
]

export default function Login() {
  const { login } = useAuth()
  const [params] = useSearchParams()
  const [form, setForm] = useState({ username: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [touched, setTouched] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const missing = { username: touched && !form.username.trim(), password: touched && !form.password }

  const submit = async (e) => {
    e.preventDefault()
    setTouched(true)
    if (!form.username.trim() || !form.password) return
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/auth/login', form)
      login(data.access_token, data.user)
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, bgcolor: 'background.default' }}>
      <Box sx={{ display: { xs: 'none', md: 'flex' }, flexDirection: 'column', justifyContent: 'space-between', bgcolor: 'primary.dark', color: '#fff', p: 6 }}>
        <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5 }}>
          <Avatar variant="rounded" sx={{ bgcolor: 'rgba(255,255,255,0.14)', borderRadius: 2 }}><MonitorHeartOutlined /></Avatar>
          <Typography variant="h6" component="p" sx={{ fontWeight: 700 }}>ABDM Connect</Typography>
        </Stack>
        <Box sx={{ maxWidth: 460 }}>
          <Typography variant="h4" component="p" sx={{ fontWeight: 700, letterSpacing: '-0.02em', mb: 2 }}>
            Consent-driven exchange of laboratory reports
          </Typography>
          <Typography sx={{ opacity: 0.8, mb: 4 }}>
            Health information exchange connecting laboratories, hospitals and patients.
          </Typography>
          <Stack spacing={2.5}>
            {FEATURES.map(([Icon, title, text]) => (
              <Stack key={title} direction="row" sx={{ gap: 2 }}>
                <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: '#9FE3DF', width: 40, height: 40 }}><Icon fontSize="small" /></Avatar>
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
                  <Typography variant="body2" sx={{ opacity: 0.75 }}>{text}</Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        </Box>
        <Typography variant="caption" sx={{ opacity: 0.7 }}>
          Test environment, not yet connected to ABDM. Do not enter real patient data.
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2, sm: 4 } }}>
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          <Stack direction="row" sx={{ display: { xs: 'flex', md: 'none' }, alignItems: 'center', gap: 1.5, mb: 4 }}>
            <Avatar variant="rounded" sx={{ bgcolor: 'primary.main', borderRadius: 2 }}><MonitorHeartOutlined /></Avatar>
            <Typography variant="h6" component="p" sx={{ fontWeight: 700 }}>ABDM Connect</Typography>
          </Stack>
          <Typography variant="h5" component="h1">Sign in</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5, mb: 3 }}>Sign in with your account to continue.</Typography>

          {params.get('expired') && <Alert severity="warning" sx={{ mb: 2 }}>Your session ended. Please log in again.</Alert>}
          {error && <Alert severity="error" sx={{ mb: 2 }} role="alert">{error}</Alert>}

          <Stack component="form" spacing={2} onSubmit={submit} noValidate>
            <TextField label="Username" value={form.username} autoFocus required autoComplete="username"
              error={missing.username} helperText={missing.username ? 'Enter your username.' : ' '}
              onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <TextField label="Password" type={showPassword ? 'text' : 'password'} value={form.password} required autoComplete="current-password"
              error={missing.password} helperText={missing.password ? 'Enter your password.' : ' '}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton edge="end" onClick={() => setShowPassword((s) => !s)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }} />
            <Button type="submit" variant="contained" size="large" disabled={busy}
              startIcon={busy ? <CircularProgress size={18} color="inherit" /> : null}>
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </Stack>

          {import.meta.env.DEV && (<>
          <Divider sx={{ my: 3 }}><Typography variant="caption" color="text.secondary">Sample accounts (development only)</Typography></Divider>
          <List disablePadding sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1 }}>
            {SAMPLE_USERS.map(([u, label, Icon]) => (
              <ListItemButton key={u} onClick={() => { setForm({ username: u, password: SAMPLE_PASSWORD }); setTouched(false) }}
                sx={{ border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'background.paper', py: 0.75 }}>
                <ListItemIcon sx={{ minWidth: 34, color: 'primary.main' }}><Icon fontSize="small" /></ListItemIcon>
                <ListItemText primary={u} secondary={label}
                  slotProps={{ primary: { sx: { fontWeight: 600, fontSize: 14 } }, secondary: { sx: { fontSize: 12 } } }} />
              </ListItemButton>
            ))}
          </List>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5, textAlign: 'center' }}>
            Click an account to fill the form. Password for all sample accounts: <b>{SAMPLE_PASSWORD}</b>
          </Typography>
          </>)}
        </Box>
      </Box>
    </Box>
  )
}
