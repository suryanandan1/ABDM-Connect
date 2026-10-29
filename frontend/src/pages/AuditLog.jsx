import { useState } from 'react'
import {
  Box, Button, InputAdornment, MenuItem, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination,
  TableRow, TextField, Typography,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import RefreshIcon from '@mui/icons-material/Refresh'
import SearchIcon from '@mui/icons-material/Search'
import { useAuth } from '../App'
import { Code, Loader, PageTitle, SectionCard, StatusChip, fmt, useApi } from '../components'

const EVENT_TYPES = [
  'LOGIN', 'LOGOUT', 'PATIENT_CREATED', 'REPORT_CREATED', 'REPORT_WITHDRAWN', 'REPORT_VIEW', 'ACCESS_REQUESTED',
  'CONSENT_APPROVED', 'CONSENT_DENIED', 'CONSENT_REVOKED', 'CONSENT_EXPIRED', 'REPORT_RETRIEVE',
  'CONSULTATION_CREATED', 'CONSULTATION_VIEW', 'CONSULTATION_WITHDRAWN', 'CONSULTATION_RETRIEVE',
  'ADMIN_USER_CREATED', 'ADMIN_USER_UPDATED', 'ADMIN_FACILITY_CREATED',
]

export default function AuditLog() {
  const { user } = useAuth()
  const [eventType, setEventType] = useState('')
  const [outcome, setOutcome] = useState('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(0)
  const [perPage, setPerPage] = useState(25)
  const { data, loading, error, reload } = useApi(`/audit-events?event_type=${eventType}&outcome=${outcome}`)
  const shown = (data || []).filter((e) =>
    `${e.actor_username} ${e.detail} ${e.resource_type} ${e.resource_id}`.toLowerCase().includes(text.toLowerCase()))
  const current = Math.min(page, Math.max(0, Math.ceil(shown.length / perPage) - 1))
  const filtered = eventType || outcome || text
  const isPatient = user.role === 'PATIENT'

  return (
    <>
      <PageTitle
        title={isPatient ? 'My access history' : 'Audit log'}
        subtitle={isPatient ? 'Every request, decision and access to your records' : 'Latest 200 events, newest first'}
        action={<Button startIcon={<RefreshIcon />} onClick={reload} disabled={loading}>Refresh</Button>}
      />
      <SectionCard flush>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ p: 2.5, borderBottom: 1, borderColor: 'divider' }}>
          <TextField select size="small" label="Event" value={eventType} onChange={(e) => { setEventType(e.target.value); setPage(0) }} sx={{ minWidth: 220 }}>
            <MenuItem value="">All events</MenuItem>
            {EVENT_TYPES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Outcome" value={outcome} onChange={(e) => { setOutcome(e.target.value); setPage(0) }} sx={{ minWidth: 150 }}>
            <MenuItem value="">All</MenuItem>
            {['SUCCESS', 'DENIED', 'FAILURE'].map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
          </TextField>
          <TextField size="small" fullWidth placeholder="Search user, detail or resource" value={text}
            onChange={(e) => { setText(e.target.value); setPage(0) }}
            slotProps={{
              htmlInput: { 'aria-label': 'Search events' },
              input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
            }} />
          {filtered && (
            <Button color="inherit" sx={{ flexShrink: 0 }} onClick={() => { setEventType(''); setOutcome(''); setText(''); setPage(0) }}>Clear filters</Button>
          )}
        </Stack>
        <Loader loading={loading && !data} error={error} empty={shown.length === 0} emptyTitle="No matching events"
          emptyText={filtered ? 'Try removing a filter.' : 'No events have been recorded yet.'}>
          <Typography variant="body2" color="text.secondary" sx={{ px: 2.5, py: 1.5 }}>
            {shown.length} event(s){filtered ? ' match the filters' : ''}. Denied and failed events are highlighted.
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell><TableCell>Event</TableCell><TableCell>Outcome</TableCell><TableCell>Actor</TableCell>
                  <TableCell>Resource</TableCell><TableCell>Patient</TableCell><TableCell>Detail</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {shown.slice(current * perPage, current * perPage + perPage).map((e) => {
                  const flagged = e.outcome !== 'SUCCESS'
                  return (
                    <TableRow key={e.id} hover
                      sx={flagged ? (t) => ({ bgcolor: alpha(t.palette.error.main, 0.04), '& td:first-of-type': { boxShadow: `inset 3px 0 0 ${t.palette.error.main}` } }) : undefined}>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(e.created_at)}</TableCell>
                      <TableCell><Code>{e.event_type}</Code></TableCell>
                      <TableCell><StatusChip value={e.outcome} /></TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>{e.actor_username || 'system'}</Typography>
                        {e.actor_role && <Typography variant="caption" color="text.secondary">{e.actor_role}</Typography>}
                      </TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{e.resource_type ? `${e.resource_type}/${e.resource_id}` : '—'}</TableCell>
                      <TableCell>{e.patient_id ?? '—'}</TableCell>
                      <TableCell sx={{ minWidth: 220 }}>{e.detail || '—'}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>
          <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
            <TablePagination component="div" count={shown.length} page={current} rowsPerPage={perPage} rowsPerPageOptions={[25, 50, 100]}
              onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setPerPage(Number(e.target.value)); setPage(0) }} />
          </Box>
        </Loader>
      </SectionCard>
    </>
  )
}
