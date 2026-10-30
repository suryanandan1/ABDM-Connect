import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import {
  Alert, Avatar, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment, MenuItem, Paper, Stack,
  Tab, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, Tabs, TextField, Typography,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined'
import ChevronRight from '@mui/icons-material/ChevronRight'
import api, { errorText } from '../api'
import { useAuth } from '../App'
import { Code, Loader, PageTitle, SectionCard, fmtDate, initials, useApi } from '../components'

const EMPTY = { full_name: '', gender: 'female', birth_date: '', phone: '', username: '', password: '' }
const today = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10) }

// Same rules as the backend (schemas.PatientIn), checked here only to give earlier feedback.
function validate(f) {
  const e = {}
  if (f.full_name.trim().length < 2) e.full_name = 'Enter the full name (at least 2 characters).'
  if (!f.birth_date) e.birth_date = 'Enter the date of birth.'
  else if (f.birth_date > today() || f.birth_date < '1900-01-01') e.birth_date = 'Must be between 1900 and today.'
  if (f.phone && !/^[0-9]{10}$/.test(f.phone)) e.phone = 'Use exactly 10 digits, or leave empty.'
  if (!/^[a-zA-Z0-9_.-]{3,50}$/.test(f.username)) e.username = '3–50 characters: letters, numbers, . _ -'
  if (f.password.length < 8) e.password = 'At least 8 characters.'
  return e
}

function age(birthDate) {
  const b = new Date(`${birthDate}T00:00:00`)
  const n = new Date()
  return n.getFullYear() - b.getFullYear() - (n < new Date(n.getFullYear(), b.getMonth(), b.getDate()) ? 1 : 0)
}

function RegisterDialog({ open, onClose }) {
  const [tab, setTab] = useState('abha')
  const [busy, setBusy] = useState(false)
  const close = () => { if (!busy) onClose() }
  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 0 }}>Register patient</DialogTitle>
      <Tabs value={tab} onChange={(_, v) => !busy && setTab(v)} sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab value="abha" label="With ABHA" />
        <Tab value="manual" label="Without ABHA" />
      </Tabs>
      {/* Unmounted while closed, so each opening starts from a clean form. */}
      {open && (tab === 'abha'
        ? <AbhaRegister onClose={onClose} busy={busy} setBusy={setBusy} />
        : <ManualRegister onClose={onClose} busy={busy} setBusy={setBusy} />)}
    </Dialog>
  )
}

const ABHA_NUMBER = /^\d{2}-?\d{4}-?\d{4}-?\d{4}$/
const ABHA_ADDRESS = /^[a-zA-Z0-9_.]{3,}@[a-z]+$/

// Three steps, mirroring the ABDM flow: ABHA → OTP the patient received → verified profile → save.
// Today the backend talks to the local mock ABDM server (mock_abdm/, OTP printed in its terminal).
function AbhaRegister({ onClose, busy, setBusy }) {
  const navigate = useNavigate()
  const [step, setStep] = useState('id')
  const [abha, setAbha] = useState('')
  const [otp, setOtp] = useState('')
  const [txn, setTxn] = useState(null)
  const [verified, setVerified] = useState(null)
  const [login, setLogin] = useState({ username: '', password: '' })
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const value = abha.trim()
  const isAddress = value.includes('@')
  const abhaError = submitted && step === 'id' && !(isAddress ? ABHA_ADDRESS.test(value.toLowerCase()) : ABHA_NUMBER.test(value))
  const otpError = submitted && step === 'otp' && !/^\d{6}$/.test(otp)
  const loginErrors = submitted && step === 'profile' ? {
    username: !/^[a-zA-Z0-9_.-]{3,50}$/.test(login.username) && '3–50 characters: letters, numbers, . _ -',
    password: login.password.length < 8 && 'At least 8 characters.',
  } : {}

  const run = async (valid, action) => {
    setSubmitted(true)
    if (!valid) return
    setBusy(true)
    setError('')
    try {
      await action()
      setSubmitted(false)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const sendOtp = (e) => {
    e.preventDefault()
    const ok = isAddress ? ABHA_ADDRESS.test(value.toLowerCase()) : ABHA_NUMBER.test(value)
    run(ok, async () => {
      const { data } = await api.post('/patients/abha/init', isAddress ? { abha_address: value } : { abha_number: value })
      setTxn(data)
      setOtp('')
      setStep('otp')
    })
  }

  const verifyOtp = (e) => {
    e.preventDefault()
    run(/^\d{6}$/.test(otp), async () => {
      const { data } = await api.post('/patients/abha/verify', { txn_id: txn.txn_id, otp })
      setVerified(data)
      setStep('profile')
    })
  }

  const register = (e) => {
    e.preventDefault()
    const ok = /^[a-zA-Z0-9_.-]{3,50}$/.test(login.username) && login.password.length >= 8
    run(ok, async () => {
      const { data } = await api.post('/patients/abha/register', { abha_token: verified.abha_token, ...login })
      onClose()
      navigate(`/patients/${data.id}`, { state: { created: data.patient_code } })
    })
  }

  const link = () => run(true, async () => {
    const { data } = await api.post(`/patients/${verified.possible_match.id}/abha`, { abha_token: verified.abha_token })
    onClose()
    navigate(`/patients/${data.id}`, { state: { linked: data.abha_number } })
  })

  const restart = () => { setStep('id'); setTxn(null); setVerified(null); setError(''); setSubmitted(false) }
  const cancel = <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
  const errorBox = error && <Alert severity="error" sx={{ whiteSpace: 'pre-line' }}>{error}</Alert>

  if (step === 'id') return (
    <form onSubmit={sendOtp} noValidate>
      <DialogContent>
        <Stack spacing={2.5}>
          <Alert severity="info">
            ABDM sends a one-time password to the mobile linked to the patient's ABHA. Connected to the <b>mock ABDM server</b>,
            not real ABDM: the OTP appears in the mock server's terminal.
          </Alert>
          {errorBox}
          <TextField label="ABHA number or ABHA address" required autoFocus value={abha} onChange={(e) => setAbha(e.target.value)}
            error={abhaError} placeholder="91-1111-2222-3333 or name@sbx"
            helperText={abhaError ? 'Enter a 14-digit ABHA number or an ABHA address like name@sbx.' : '14-digit ABHA number (hyphens optional) or ABHA address'} />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {cancel}
        <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Sending…' : 'Send OTP'}</Button>
      </DialogActions>
    </form>
  )

  if (step === 'otp') return (
    <form onSubmit={verifyOtp} noValidate>
      <DialogContent>
        <Stack spacing={2.5}>
          <Alert severity="success">{txn.message}. Ask the patient for the 6-digit code.</Alert>
          {errorBox}
          <TextField label="OTP" required autoFocus value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
            error={otpError} helperText={otpError ? 'Enter the 6-digit OTP.' : 'Valid for 5 minutes, 3 attempts'}
            slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6, autoComplete: 'one-time-code' } }} />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={restart} disabled={busy} color="inherit" sx={{ mr: 'auto' }}>Change ABHA / resend</Button>
        {cancel}
        <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Verifying…' : 'Verify'}</Button>
      </DialogActions>
    </form>
  )

  const { profile, existing_patient: existing, possible_match: match } = verified
  return (
    <form onSubmit={register} noValidate>
      <DialogContent>
        <Stack spacing={2.5}>
          {errorBox}
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="overline" color="text.secondary">Verified ABHA profile</Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{profile.full_name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
              {profile.gender} · born {fmtDate(profile.birth_date)}{profile.phone && ` · ${profile.phone}`}
            </Typography>
            <Stack direction="row" sx={{ gap: 1, mt: 1, flexWrap: 'wrap' }}>
              <Code>{profile.abha_number}</Code>{profile.abha_address && <Code>{profile.abha_address}</Code>}
            </Stack>
          </Paper>
          {existing && <Alert severity="info">This ABHA is already registered as <b>{existing.patient_code}</b>.</Alert>}
          {match && (
            <Alert severity="warning">
              <b>{match.patient_code}</b> has the same name and birth date but no ABHA yet. If this is the same person,
              link the ABHA to that record instead of creating a duplicate.
            </Alert>
          )}
          {!existing && !match && (
            <>
              <Typography variant="overline" color="text.secondary" sx={{ mb: -1.5 }}>Patient portal login</Typography>
              <TextField label="Patient portal username" required autoComplete="off" value={login.username}
                onChange={(e) => setLogin({ ...login, username: e.target.value })}
                error={Boolean(loginErrors.username)} helperText={loginErrors.username || 'Letters, numbers, . _ -'} />
              <TextField label="Temporary password" required type="password" autoComplete="new-password" value={login.password}
                onChange={(e) => setLogin({ ...login, password: e.target.value })}
                error={Boolean(loginErrors.password)} helperText={loginErrors.password || 'At least 8 characters. Give it to the patient.'} />
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {cancel}
        {existing && <Button variant="contained" onClick={() => { onClose(); navigate(`/patients/${existing.id}`) }}>Open patient record</Button>}
        {match && <Button variant="contained" disabled={busy} onClick={link}>{busy ? 'Linking…' : `Link ABHA to ${match.patient_code}`}</Button>}
        {!existing && !match && <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Saving…' : 'Register'}</Button>}
      </DialogActions>
    </form>
  )
}

function ManualRegister({ onClose, busy, setBusy }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const errors = submitted ? validate(form) : {}
  const field = (name, help = ' ') => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    error: Boolean(errors[name]),
    helperText: errors[name] || help,
  })

  const submit = async (e) => {
    e.preventDefault()
    setSubmitted(true)
    if (Object.keys(validate(form)).length) return
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/patients', { ...form, phone: form.phone || null })
      setForm(EMPTY)
      setSubmitted(false)
      onClose()
      navigate(`/patients/${data.id}`, { state: { created: data.patient_code } })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <DialogContent>
        <Stack spacing={2.5}>
          <Alert severity="info">For patients without an ABHA. A patient ID (PAT-…) is generated; an ABHA can be linked later.</Alert>
          {error && <Alert severity="error" sx={{ whiteSpace: 'pre-line' }}>{error}</Alert>}
          <Typography variant="overline" color="text.secondary" sx={{ mb: -1.5 }}>Personal details</Typography>
          <TextField label="Full name" required {...field('full_name')} />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField select label="Gender" sx={{ flex: 1 }} {...field('gender')}>
              {['female', 'male', 'other', 'unknown'].map((g) => <MenuItem key={g} value={g} sx={{ textTransform: 'capitalize' }}>{g}</MenuItem>)}
            </TextField>
            <TextField label="Birth date" type="date" required sx={{ flex: 1 }}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: today(), min: '1900-01-01' } }} {...field('birth_date')} />
          </Stack>
          <TextField label="Mobile (10 digits, optional)" slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 10 } }} {...field('phone')} />
          <Typography variant="overline" color="text.secondary" sx={{ mb: -1.5 }}>Patient portal login</Typography>
          <TextField label="Patient portal username" required autoComplete="off" {...field('username', 'Letters, numbers, . _ -')} />
          <TextField label="Temporary password" required type="password" autoComplete="new-password"
            {...field('password', 'At least 8 characters. Give it to the patient.')} />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
        <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Saving…' : 'Register'}</Button>
      </DialogActions>
    </form>
  )
}

export default function Patients() {
  const { user } = useAuth()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [perPage, setPerPage] = useState(10)
  const { data, loading, error } = useApi(`/patients?q=${encodeURIComponent(query)}`)
  const rows = data || []
  const current = Math.min(page, Math.max(0, Math.ceil(rows.length / perPage) - 1))

  return (
    <>
      <PageTitle
        title="Patients"
        subtitle="Search by name, patient ID or mobile number"
        action={user.role === 'LAB' && <Button variant="contained" startIcon={<PersonAddAlt1Outlined />} onClick={() => setOpen(true)}>Register patient</Button>}
      />
      <SectionCard flush>
        <Stack direction="row" spacing={1} component="form" role="search" sx={{ p: 2.5, borderBottom: 1, borderColor: 'divider' }}
          onSubmit={(e) => { e.preventDefault(); setQuery(text); setPage(0) }}>
          <TextField size="small" fullWidth placeholder="e.g. Asha or PAT-000001" value={text} onChange={(e) => setText(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Search patients' },
              input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
            }} />
          <Button type="submit" variant="outlined">Search</Button>
        </Stack>
        <Loader loading={loading} error={error} empty={rows.length === 0} emptyTitle="No matching patients"
          emptyText={query ? `Nothing matches "${query}". Try a different name, patient ID or mobile number.` : 'No patients are registered yet.'}
          emptyAction={user.role === 'LAB' && <Button variant="contained" onClick={() => setOpen(true)}>Register a patient</Button>}>
          <Typography variant="body2" color="text.secondary" sx={{ px: 2.5, py: 1.5 }}>
            {rows.length === 50 ? 'Showing the first 50 matches. Refine your search to narrow the list.' : `${rows.length} patient(s)`}
            {query && ` matching "${query}"`}
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow><TableCell>Patient</TableCell><TableCell>Patient ID</TableCell><TableCell>Gender</TableCell><TableCell>Birth date</TableCell><TableCell /></TableRow>
              </TableHead>
              <TableBody>
                {rows.slice(current * perPage, current * perPage + perPage).map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell>
                      <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5 }}>
                        <Avatar sx={{ width: 32, height: 32, fontSize: 13, fontWeight: 600, bgcolor: 'primary.light', color: 'primary.main' }}>{initials(p.full_name)}</Avatar>
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.full_name}</Typography>
                          {p.phone && <Typography variant="caption" color="text.secondary">{p.phone}</Typography>}
                        </Box>
                      </Stack>
                    </TableCell>
                    <TableCell><Code>{p.patient_code}</Code></TableCell>
                    <TableCell sx={{ textTransform: 'capitalize' }}>{p.gender}</TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {fmtDate(p.birth_date)}
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{age(p.birth_date)} years</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Button size="small" endIcon={<ChevronRight />} component={RouterLink} to={`/patients/${p.id}`}>Open</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {rows.length > 10 && (
            <TablePagination component="div" count={rows.length} page={current} rowsPerPage={perPage} rowsPerPageOptions={[10, 25, 50]}
              onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setPerPage(Number(e.target.value)); setPage(0) }} />
          )}
        </Loader>
      </SectionCard>
      <RegisterDialog open={open} onClose={() => setOpen(false)} />
    </>
  )
}
