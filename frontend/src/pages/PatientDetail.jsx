import { useState } from 'react'
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom'
import {
  Alert, Avatar, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import NoteAddOutlined from '@mui/icons-material/NoteAddOutlined'
import PostAddOutlined from '@mui/icons-material/PostAddOutlined'
import { useAuth } from '../App'
import api, { errorText } from '../api'
import {
  Code, ConsultationTable, StatusChip, InfoItem, Loader, PURPOSES, PageTitle, ReportTable, SectionCard, fmt, fmtDate, infoGrid, initials, useApi,
} from '../components'

// `record` = { body: {report_id} | {consultation_id}, title, detail, noun } describing what is requested.
function RequestDialog({ record, onClose, onDone }) {
  const [purpose, setPurpose] = useState('TREAT')
  const [days, setDays] = useState(7)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const daysValid = Number.isInteger(Number(days)) && Number(days) >= 1 && Number(days) <= 30

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post('/access-requests', { ...record.body, purpose, duration_days: Number(days) })
      onDone(`Access request sent for "${record.title}". The patient must approve it before you can read the ${record.noun}.`)
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return (
    <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>Request access</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ mt: 0.5 }}>
          <Box sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: '#F8FAFC' }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{record.title}</Typography>
            <Typography variant="caption" color="text.secondary">{record.detail}</Typography>
          </Box>
          {error && <Alert severity="error" sx={{ whiteSpace: 'pre-line' }}>{error}</Alert>}
          <TextField select label="Purpose of use" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
            {Object.entries(PURPOSES).map(([code, label]) => <MenuItem key={code} value={code}>{label} ({code})</MenuItem>)}
          </TextField>
          <TextField label="Access needed for (days)" type="number" value={days} slotProps={{ htmlInput: { min: 1, max: 30 } }}
            onChange={(e) => setDays(e.target.value)} error={!daysValid}
            helperText={daysValid ? "1 to 30 days, counted from the patient's approval" : 'Enter a whole number from 1 to 30.'} />
          <Typography variant="caption" color="text.secondary">
            The patient is asked to approve or deny. You can retrieve the {record.noun} only while their consent is active.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !daysValid}>{busy ? 'Sending…' : 'Send request'}</Button>
      </DialogActions>
    </Dialog>
  )
}

const ROLE_NOTES = {
  LAB: 'Only reports from your laboratory are listed.',
  HOSPITAL: 'Results are hidden until the patient approves an access request.',
  ADMIN: 'Admins see report metadata only, never results.',
}

export default function PatientDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const patient = useApi(`/patients/${id}`)
  const reports = useApi(`/patients/${id}/reports`)
  const isHospital = user.role === 'HOSPITAL'
  const consultations = useApi(isHospital ? `/patients/${id}/consultations` : null)
  const external = useApi(isHospital ? `/patients/${id}/consultations/other-facilities` : null)
  const [requesting, setRequesting] = useState(null)
  const [message, setMessage] = useState('')
  const p = patient.data

  return (
    <Loader loading={patient.loading} error={patient.error}>
      {p && (
        <>
          <PageTitle
            crumbs={[['Patients', '/patients'], [p.full_name]]}
            title={p.full_name}
            subtitle="Patient record"
            action={(user.role === 'LAB' && (
              <Button variant="contained" startIcon={<NoteAddOutlined />} component={RouterLink} to={`/reports/new?patient=${p.id}`}>Create report</Button>
            )) || (user.role === 'HOSPITAL' && (
              <Button variant="contained" startIcon={<PostAddOutlined />} component={RouterLink} to={`/consultations/new?patient=${p.id}`}>New consultation</Button>
            ))}
          />
          {location.state?.created && <Alert severity="success" sx={{ mb: 2 }}>Patient registered with patient ID {location.state.created}.</Alert>}
          {location.state?.linked && <Alert severity="success" sx={{ mb: 2 }}>Verified ABHA {location.state.linked} linked to this patient.</Alert>}
          {message && (
            <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMessage('')}
              action={<Button color="inherit" size="small" component={RouterLink} to="/access-requests">View requests</Button>}>
              {message}
            </Alert>
          )}
          <Paper sx={{ p: 2.5, mb: 3 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2.5, alignItems: { sm: 'center' } }}>
              <Avatar sx={{ width: 56, height: 56, bgcolor: 'primary.light', color: 'primary.main', fontWeight: 700 }}>{initials(p.full_name)}</Avatar>
              <Box sx={{ ...infoGrid, flexGrow: 1 }}>
                <InfoItem label="Patient ID"><Code>{p.patient_code}</Code></InfoItem>
                <InfoItem label="ABHA">
                  {p.abha_number ? (
                    <>
                      <Code>{p.abha_number}</Code>
                      {p.abha_address && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>{p.abha_address}</Typography>}
                    </>
                  ) : 'Not linked'}
                </InfoItem>
                <InfoItem label="Gender"><Box component="span" sx={{ textTransform: 'capitalize' }}>{p.gender}</Box></InfoItem>
                <InfoItem label="Date of birth">{fmtDate(p.birth_date)}</InfoItem>
                <InfoItem label="Mobile">{p.phone || 'Not provided'}</InfoItem>
                <InfoItem label="Registered">{fmt(p.created_at)}</InfoItem>
              </Box>
            </Stack>
          </Paper>
          {user.role === 'HOSPITAL' && (
            <SectionCard title="Consultations at your hospital" subtitle="Your records (HIP). Other hospitals can read them only with the patient's consent." flush sx={{ mb: 3 }}>
              <Loader loading={consultations.loading} error={consultations.error} empty={consultations.data?.length === 0} emptyTitle="No consultations yet"
                emptyText="Record this patient's visit: complaint, findings, diagnosis and prescription."
                emptyAction={<Button variant="outlined" component={RouterLink} to={`/consultations/new?patient=${p.id}`}>Start a consultation</Button>}>
                {consultations.data && <ConsultationTable items={consultations.data} />}
              </Loader>
            </SectionCard>
          )}
          {isHospital && (
            <SectionCard title="Consultations at other hospitals" flush sx={{ mb: 3 }}
              subtitle="Held by other hospitals (you act as HIU). Only the date, hospital and doctor are shown until the patient approves.">
              <Loader loading={external.loading} error={external.error} empty={external.data?.length === 0} emptyTitle="None found"
                emptyText="This patient has no consultations recorded at other hospitals.">
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow><TableCell>Visit</TableCell><TableCell>Hospital</TableCell><TableCell>Doctor</TableCell><TableCell>Status</TableCell><TableCell align="right">Action</TableCell></TableRow>
                    </TableHead>
                    <TableBody>
                      {(external.data || []).map((c) => (
                        <TableRow key={c.id} hover>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{fmt(c.visit_at)}</Typography>
                            <Typography variant="caption" color="text.secondary">Consultation #{c.id}</Typography>
                          </TableCell>
                          <TableCell>{c.facility.name}</TableCell>
                          <TableCell>{c.doctor.full_name}</TableCell>
                          <TableCell><StatusChip value={c.status} /></TableCell>
                          <TableCell align="right">
                            <Button size="small" variant="outlined" onClick={() => setRequesting({
                              body: { consultation_id: c.id }, noun: 'consultation',
                              title: `OP consultation · ${new Date(c.visit_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}`,
                              detail: `Consultation #${c.id} · ${c.facility.name} · ${c.doctor.full_name}`,
                            })}>Request access</Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Loader>
            </SectionCard>
          )}
          <SectionCard title={user.role === 'HOSPITAL' ? 'Laboratory reports' : 'Reports'} subtitle={ROLE_NOTES[user.role]} flush>
            <Loader loading={reports.loading} error={reports.error} empty={reports.data?.length === 0} emptyTitle="No reports"
              emptyText="No reports are available for this patient yet.">
              {reports.data && (
                <ReportTable
                  reports={reports.data}
                  linkReports={user.role === 'LAB'}
                  action={user.role === 'HOSPITAL' ? (r) => (
                    <Button size="small" variant="outlined" disabled={r.status === 'entered-in-error'} onClick={() => setRequesting({
                      body: { report_id: r.id }, noun: 'report', title: r.title,
                      detail: `Report #${r.id} · ${r.facility.name} · issued ${fmt(r.issued_at)}`,
                    })}>Request access</Button>
                  ) : null}
                />
              )}
            </Loader>
          </SectionCard>
          {requesting && (
            <RequestDialog record={requesting} onClose={() => setRequesting(null)}
              onDone={(text) => { setRequesting(null); setMessage(text) }} />
          )}
        </>
      )}
    </Loader>
  )
}
