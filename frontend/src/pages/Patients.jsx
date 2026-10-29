import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import {
  Alert, Avatar, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment, MenuItem, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
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
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const errors = submitted ? validate(form) : {}
  const field = (name, help = ' ') => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    error: Boolean(errors[name]),
    helperText: errors[name] || help,
  })

  const close = () => { if (!busy) { onClose(); setSubmitted(false); setError('') } }

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
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <form onSubmit={submit} noValidate>
        <DialogTitle>Register patient</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 0.5 }}>
            <Alert severity="info">A patient ID (PAT-…) is generated. This is not an ABHA number; ABHA linking comes with ABDM integration.</Alert>
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
          <Button onClick={close} disabled={busy} color="inherit">Cancel</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Saving…' : 'Register'}</Button>
        </DialogActions>
      </form>
    </Dialog>
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
