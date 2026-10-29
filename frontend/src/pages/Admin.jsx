import { useState } from 'react'
import {
  Alert, Avatar, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined'
import AddBusinessOutlined from '@mui/icons-material/AddBusinessOutlined'
import api, { errorText } from '../api'
import { useAuth } from '../App'
import { Code, ConfirmDialog, Loader, PageTitle, ROLE_LABELS, SectionCard, StatusChip, initials, useApi } from '../components'

const FACILITY_TYPES = { LAB: 'Laboratory (HIP)', HOSPITAL: 'Hospital (HIP + HIU)' }

// Small form helper: submit runs `send(form)`, then resets the form and refreshes the list.
function useForm(initial, send, onDone) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) })
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await send(form)
      setForm(initial)
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return { form, field, submit, error, busy }
}

const formBox = { p: 2, mb: 2.5, borderRadius: 2, bgcolor: '#F8FAFC', border: 1, borderColor: 'divider' }

function UsersSection({ facilities }) {
  const { user: me } = useAuth()
  const users = useApi('/admin/users')
  const [toggle, setToggle] = useState(null)
  const [resetFor, setResetFor] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const create = useForm(
    { username: '', full_name: '', password: '', role: 'LAB', facility_id: '' },
    (f) => api.post('/admin/users', { ...f, facility_id: f.role === 'ADMIN' ? null : Number(f.facility_id) || null }),
    () => { users.reload(); setMessage({ severity: 'success', text: 'User created.' }) },
  )

  const patch = async (id, body, text) => {
    setBusy(true)
    try {
      await api.patch(`/admin/users/${id}`, body)
      setMessage({ severity: 'success', text })
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err) })
    } finally {
      setBusy(false)
      setToggle(null)
      setResetFor(null)
      setNewPassword('')
      users.reload()
    }
  }

  const facilityChoices = facilities.filter((f) => f.facility_type === create.form.role)
  return (
    <SectionCard title="Users" subtitle={`${users.data?.length ?? '…'} account(s). Patient accounts are created by a laboratory when it registers a patient.`} sx={{ mb: 3 }}>
      {message && <Alert severity={message.severity} sx={{ mb: 2 }} onClose={() => setMessage(null)}>{message.text}</Alert>}
      <Box component="form" onSubmit={create.submit} sx={formBox}>
        <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Add a staff or admin user</Typography>
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(5, 1fr) auto' } }}>
          <TextField size="small" label="Username" required {...create.field('username')} />
          <TextField size="small" label="Full name" required {...create.field('full_name')} />
          <TextField size="small" label="Password" type="password" required autoComplete="new-password" {...create.field('password')} />
          <TextField size="small" select label="Role" {...create.field('role')}>
            {['LAB', 'HOSPITAL', 'ADMIN'].map((r) => <MenuItem key={r} value={r}>{ROLE_LABELS[r]}</MenuItem>)}
          </TextField>
          <TextField size="small" select label="Facility" disabled={create.form.role === 'ADMIN'} {...create.field('facility_id')}>
            {facilityChoices.length === 0 && <MenuItem value="" disabled>No facility of this type</MenuItem>}
            {facilityChoices.map((f) => <MenuItem key={f.id} value={f.id}>{f.name}</MenuItem>)}
          </TextField>
          <Button type="submit" variant="contained" disabled={create.busy} startIcon={<PersonAddAlt1Outlined />}>Add user</Button>
        </Box>
        {create.error && <Alert severity="error" sx={{ mt: 1.5, whiteSpace: 'pre-line' }}>{create.error}</Alert>}
      </Box>
      <Loader loading={users.loading && !users.data} error={users.error}>
        <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>User</TableCell><TableCell>Role</TableCell><TableCell>Facility</TableCell><TableCell>Status</TableCell><TableCell align="right">Actions</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {(users.data || []).map((u) => (
                <TableRow key={u.id} hover>
                  <TableCell>
                    <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5 }}>
                      <Avatar sx={{ width: 32, height: 32, fontSize: 13, fontWeight: 600, bgcolor: 'primary.light', color: 'primary.main' }}>{initials(u.full_name)}</Avatar>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{u.full_name}{u.id === me.id && ' (you)'}</Typography>
                        <Typography variant="caption" color="text.secondary">{u.username}</Typography>
                      </Box>
                    </Stack>
                  </TableCell>
                  <TableCell><Chip size="small" variant="outlined" label={ROLE_LABELS[u.role] || u.role} /></TableCell>
                  <TableCell>{u.facility?.name || '—'}</TableCell>
                  <TableCell>
                    <StatusChip label={u.is_active ? 'Active' : 'Inactive'} tone={u.is_active ? 'success' : 'default'} />
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    <Button size="small" onClick={() => setResetFor(u)}>Reset password</Button>
                    <Button size="small" color={u.is_active ? 'error' : 'primary'} disabled={u.id === me.id} onClick={() => setToggle(u)}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Loader>
      {toggle && (
        <ConfirmDialog open busy={busy} danger={toggle.is_active}
          title={`${toggle.is_active ? 'Deactivate' : 'Activate'} ${toggle.username}?`}
          text={toggle.is_active ? 'The user will be signed out and unable to log in.' : 'The user will be able to log in again.'}
          confirmText={toggle.is_active ? 'Deactivate' : 'Activate'}
          onConfirm={() => patch(toggle.id, { is_active: !toggle.is_active }, `User ${toggle.is_active ? 'deactivated' : 'activated'}.`)}
          onClose={() => setToggle(null)} />
      )}
      {resetFor && (
        <Dialog open onClose={busy ? undefined : () => setResetFor(null)} fullWidth maxWidth="xs">
          <DialogTitle>Reset password for {resetFor.username}</DialogTitle>
          <DialogContent>
            <TextField sx={{ mt: 1 }} fullWidth type="password" label="New password" autoComplete="new-password" value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)} error={newPassword.length > 0 && newPassword.length < 8}
              helperText="At least 8 characters. The user will be signed out everywhere." />
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button color="inherit" onClick={() => { setResetFor(null); setNewPassword('') }} disabled={busy}>Cancel</Button>
            <Button variant="contained" disabled={busy || newPassword.length < 8}
              onClick={() => patch(resetFor.id, { password: newPassword }, 'Password reset. The user was signed out everywhere.')}>
              {busy ? 'Resetting…' : 'Reset'}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </SectionCard>
  )
}

export default function Admin() {
  const facilities = useApi('/facilities')
  const [created, setCreated] = useState(false)
  const create = useForm(
    { name: '', facility_type: 'LAB', city: '' },
    (f) => api.post('/facilities', f),
    () => { facilities.reload(); setCreated(true) },
  )
  return (
    <>
      <PageTitle title="Users & facilities" subtitle="Staff accounts and registered facilities" />
      <Loader loading={facilities.loading && !facilities.data} error={facilities.error}>
        {facilities.data && <UsersSection facilities={facilities.data} />}
      </Loader>
      <SectionCard title="Facilities" subtitle={`${facilities.data?.length ?? '…'} simulated laboratories and hospitals`}>
        {created && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setCreated(false)}>Facility created.</Alert>}
        <Box component="form" onSubmit={create.submit} sx={formBox}>
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Add a facility</Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
            <TextField size="small" label="Facility name" required sx={{ flex: 2 }} {...create.field('name')} />
            <TextField size="small" select label="Type" sx={{ flex: 1 }} {...create.field('facility_type')}>
              {Object.entries(FACILITY_TYPES).map(([v, label]) => <MenuItem key={v} value={v}>{label}</MenuItem>)}
            </TextField>
            <TextField size="small" label="City" sx={{ flex: 1 }} {...create.field('city')} />
            <Button type="submit" variant="contained" disabled={create.busy} startIcon={<AddBusinessOutlined />}>Add facility</Button>
          </Stack>
          {create.error && <Alert severity="error" sx={{ mt: 1.5, whiteSpace: 'pre-line' }}>{create.error}</Alert>}
        </Box>
        <Loader loading={facilities.loading && !facilities.data} error={facilities.error}>
          <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
            <Table size="small">
              <TableHead><TableRow><TableCell>Facility code</TableCell><TableCell>Name</TableCell><TableCell>Type</TableCell><TableCell>City</TableCell></TableRow></TableHead>
              <TableBody>
                {(facilities.data || []).map((f) => (
                  <TableRow key={f.id} hover>
                    <TableCell><Code>{f.facility_code}</Code></TableCell>
                    <TableCell sx={{ fontWeight: 500 }}>{f.name}</TableCell>
                    <TableCell>
                      <Chip size="small" variant="outlined" color={f.facility_type === 'LAB' ? 'secondary' : 'primary'} label={FACILITY_TYPES[f.facility_type] || f.facility_type} />
                    </TableCell>
                    <TableCell>{f.city || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Loader>
      </SectionCard>
    </>
  )
}
