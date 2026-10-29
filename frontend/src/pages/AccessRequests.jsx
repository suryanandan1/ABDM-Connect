import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Alert, AlertTitle, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, InputAdornment, Tab,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Tooltip, Typography, useMediaQuery,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import SearchIcon from '@mui/icons-material/Search'
import api, { errorText } from '../api'
import {
  Code, FhirViewer, Loader, PURPOSES, PageTitle, RecordKind, ReportDetails, SectionCard, StatusChip, fmt, recordInfo, useApi,
} from '../components'
import { ConsultationDetails } from './ConsultationView'

const STATUSES = ['PENDING', 'ACTIVE', 'DENIED', 'REVOKED', 'EXPIRED']

// Shows a record (lab report or consultation) the hospital was allowed to retrieve.
function RetrievedDialog({ result, onClose }) {
  const [tab, setTab] = useState(0)
  const fullScreen = useMediaQuery((t) => t.breakpoints.down('sm'))
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="lg" fullScreen={fullScreen}>
      <DialogTitle>{result.consultation ? 'Retrieved consultation' : 'Retrieved report'}</DialogTitle>
      <DialogContent dividers>
        <Alert severity="success" sx={{ mb: 2 }}>
          Access granted by the patient's consent until {fmt(result.consent_expires_at)}. This access was recorded in the audit log.
        </Alert>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Tab label={result.consultation ? 'Summary' : 'Report'} /><Tab label="FHIR R4 JSON" />
        </Tabs>
        {tab === 1 ? <FhirViewer data={result.fhir} />
          : result.consultation ? <ConsultationDetails c={result.consultation} /> : <ReportDetails report={result.report} />}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 1.5 }}><Button variant="contained" onClick={onClose}>Close</Button></DialogActions>
    </Dialog>
  )
}

function validity(c) {
  if (c.status === 'PENDING') return `${c.duration_days} day(s) after approval`
  if (c.status === 'REVOKED') return `Revoked ${fmt(c.revoked_at)}`
  if (c.status === 'DENIED') return `Denied ${fmt(c.decided_at)}`
  if (c.expires_at) return `${c.status === 'EXPIRED' ? 'Expired' : 'Until'} ${fmt(c.expires_at)}`
  return '—'
}

export default function AccessRequests() {
  const { data, loading, error, reload } = useApi('/access-requests')
  const [filter, setFilter] = useState('')
  const [status, setStatus] = useState('ALL')
  const [busyId, setBusyId] = useState(null)
  const [message, setMessage] = useState(null)
  const [result, setResult] = useState(null)

  const retrieve = async (req) => {
    setBusyId(req.id)
    setMessage(null)
    try {
      const { data: res } = await api.post(`/access-requests/${req.id}/retrieve`, { purpose: req.purpose })
      setResult(res)
    } catch (err) {
      setMessage({ severity: 'error', title: `Retrieval of request #${req.id} refused`, text: errorText(err) })
    } finally {
      setBusyId(null)
      reload() // status may have changed (for example to EXPIRED)
    }
  }

  const all = data || []
  const count = (s) => all.filter((r) => r.status === s).length
  const shown = all.filter((r) => (status === 'ALL' || r.status === status)
    && `${r.patient.full_name} ${r.patient.patient_code} ${recordInfo(r).title} ${recordInfo(r).holder} ${r.status}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <>
      <PageTitle title="Access requests" subtitle="Records you requested from other facilities (your HIU role). Retrieval works only while the patient's consent is ACTIVE"
        action={<Button startIcon={<RefreshIcon />} onClick={reload} disabled={loading}>Refresh</Button>} />
      {message && (
        <Alert severity={message.severity} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
          <AlertTitle>{message.title}</AlertTitle>
          <span>{message.text}</span>
        </Alert>
      )}
      <SectionCard flush>
        <Tabs value={status} onChange={(_, v) => setStatus(v)} variant="scrollable" scrollButtons="auto"
          sx={{ px: 1.5, borderBottom: 1, borderColor: 'divider' }} aria-label="Filter by status">
          <Tab value="ALL" label={`All (${all.length})`} />
          {STATUSES.map((s) => <Tab key={s} value={s} label={`${s[0]}${s.slice(1).toLowerCase()} (${count(s)})`} />)}
        </Tabs>
        <Box sx={{ p: 2.5, pb: 1 }}>
          <TextField size="small" fullWidth placeholder="Filter by patient, report or status" value={filter}
            onChange={(e) => setFilter(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Filter requests' },
              input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
            }} />
        </Box>
        <Loader loading={loading && !data} error={error} empty={shown.length === 0} emptyTitle="No access requests"
          emptyText={all.length ? 'No requests match the current filter.' : 'Open a patient from "Find patient" to request a lab report or another hospital\'s consultation.'}
          emptyAction={!all.length && <Button variant="contained" component={RouterLink} to="/patients">Find a patient</Button>}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Request</TableCell><TableCell>Patient</TableCell><TableCell>Record</TableCell><TableCell>Purpose</TableCell>
                  <TableCell>Consent validity</TableCell><TableCell>Status</TableCell><TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {shown.map((r) => (
                  <TableRow key={r.id} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>#{r.id}</Typography>
                      <Typography variant="caption" color="text.secondary">{fmt(r.created_at)}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>{r.patient.full_name}</Typography>
                      <Code>{r.patient.patient_code}</Code>
                    </TableCell>
                    <TableCell>
                      <RecordKind value={recordInfo(r).kind} />
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>{recordInfo(r).title}</Typography>
                      <Typography variant="caption" color="text.secondary">{recordInfo(r).ref} · held by {recordInfo(r).holder}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{PURPOSES[r.purpose]}</Typography>
                      <Typography variant="caption" color="text.secondary">{r.purpose}</Typography>
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}><Typography variant="body2">{validity(r.consent)}</Typography></TableCell>
                    <TableCell><StatusChip value={r.status} /></TableCell>
                    <TableCell align="right">
                      <Tooltip describeChild title={r.status === 'ACTIVE' ? 'Read the record under the patient\'s consent' : 'The server will refuse unless consent is ACTIVE'}>
                        <span>
                          <Button size="small" variant={r.status === 'ACTIVE' ? 'contained' : 'outlined'} disabled={busyId === r.id} onClick={() => retrieve(r)}>
                            {busyId === r.id ? 'Retrieving…' : 'Retrieve'}
                          </Button>
                        </span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Loader>
      </SectionCard>
      {result && <RetrievedDialog result={result} onClose={() => setResult(null)} />}
    </>
  )
}
