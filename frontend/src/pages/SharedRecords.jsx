import { useState } from 'react'
import {
  Alert, Box, Button, InputAdornment, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs,
  TextField, Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import SearchIcon from '@mui/icons-material/Search'
import { useAuth } from '../App'
import { Code, Loader, PURPOSES, PageTitle, RecordKind, SectionCard, StatusChip, fmt, recordInfo, useApi } from '../components'

const STATUSES = ['PENDING', 'ACTIVE', 'DENIED', 'REVOKED', 'EXPIRED']

// HIP view: who asked for this facility's records, and whether the patient allowed it.
export default function SharedRecords() {
  const { user } = useAuth()
  const { data, loading, error, reload } = useApi('/access-requests/incoming')
  const [status, setStatus] = useState('ALL')
  const [filter, setFilter] = useState('')
  const all = data || []
  const shown = all.filter((r) => (status === 'ALL' || r.status === status)
    && `${r.requester_facility.name} ${r.patient.full_name} ${r.patient.patient_code} ${recordInfo(r).title}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <>
      <PageTitle title="Shared records"
        subtitle={`Requests from other facilities for records held by ${user.facility?.name || 'your facility'} (your HIP role)`}
        action={<Button startIcon={<RefreshIcon />} onClick={reload} disabled={loading}>Refresh</Button>} />
      <Alert severity="info" sx={{ mb: 3 }}>
        Your facility does not approve these requests: the patient does. A record is released only while their consent is active,
        and every release is written to the audit log.
      </Alert>
      <SectionCard flush>
        <Tabs value={status} onChange={(_, v) => setStatus(v)} variant="scrollable" scrollButtons="auto"
          sx={{ px: 1.5, borderBottom: 1, borderColor: 'divider' }} aria-label="Filter by consent status">
          <Tab value="ALL" label={`All (${all.length})`} />
          {STATUSES.map((s) => <Tab key={s} value={s} label={`${s[0]}${s.slice(1).toLowerCase()} (${all.filter((r) => r.status === s).length})`} />)}
        </Tabs>
        <Box sx={{ p: 2.5, pb: 1 }}>
          <TextField size="small" fullWidth placeholder="Filter by requesting facility, patient or record" value={filter}
            onChange={(e) => setFilter(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Filter shared records' },
              input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
            }} />
        </Box>
        <Loader loading={loading && !data} error={error} empty={shown.length === 0} emptyTitle="No requests"
          emptyText={all.length ? 'No requests match the filter.' : 'No other facility has requested your records yet.'}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Requested by</TableCell><TableCell>Patient</TableCell><TableCell>Record</TableCell>
                  <TableCell>Purpose</TableCell><TableCell>Requested</TableCell><TableCell>Consent</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {shown.map((r) => {
                  const rec = recordInfo(r)
                  return (
                    <TableRow key={r.id} hover>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.requester_facility.name}</Typography>
                        <Typography variant="caption" color="text.secondary">{r.requester_facility.facility_code}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{r.patient.full_name}</Typography>
                        <Code>{r.patient.patient_code}</Code>
                      </TableCell>
                      <TableCell>
                        <RecordKind value={rec.kind} />
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>{rec.title}</Typography>
                        <Typography variant="caption" color="text.secondary">{rec.ref}</Typography>
                      </TableCell>
                      <TableCell>{PURPOSES[r.purpose]}</TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(r.created_at)}</TableCell>
                      <TableCell>
                        <StatusChip value={r.status} />
                        {r.consent.expires_at && r.status === 'ACTIVE' && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>until {fmt(r.consent.expires_at)}</Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Loader>
      </SectionCard>
    </>
  )
}
