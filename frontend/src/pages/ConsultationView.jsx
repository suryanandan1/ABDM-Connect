import { useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import {
  Alert, Box, Button, Paper, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, Typography,
} from '@mui/material'
import BlockOutlined from '@mui/icons-material/BlockOutlined'
import EventOutlined from '@mui/icons-material/EventOutlined'
import api, { errorText } from '../api'
import { useAuth } from '../App'
import {
  Code, ConfirmDialog, FhirViewer, InfoItem, Loader, PageTitle, StatusChip, fmt, fmtDate, infoGrid, useApi,
} from '../components'

function Block({ title, children }) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary" component="h3">{title}</Typography>
      {children}
    </Box>
  )
}

function Vital({ label, value, unit }) {
  return (
    <Box sx={{ px: 1.5, py: 1, border: 1, borderColor: 'divider', borderRadius: 2, minWidth: 110 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography sx={{ fontWeight: 700 }}>{value} <Box component="span" sx={{ fontWeight: 400, fontSize: 13, color: 'text.secondary' }}>{unit}</Box></Typography>
    </Box>
  )
}

export function ConsultationDetails({ c }) {
  const vitals = [
    c.bp_systolic != null && ['Blood pressure', `${c.bp_systolic}/${c.bp_diastolic}`, 'mmHg'],
    c.pulse != null && ['Pulse', c.pulse, '/min'],
    c.temperature != null && ['Temperature', c.temperature, '°C'],
    c.spo2 != null && ['SpO₂', c.spo2, '%'],
    c.weight != null && ['Weight', c.weight, 'kg'],
  ].filter(Boolean)
  const text = { whiteSpace: 'pre-line' }

  return (
    <Stack spacing={3}>
      {c.status === 'entered-in-error' && (
        <Alert severity="warning">This consultation was withdrawn by the hospital (entered in error) and must not be relied on.</Alert>
      )}
      <Box sx={infoGrid}>
        <InfoItem label="Patient">{c.patient.full_name}</InfoItem>
        <InfoItem label="Patient ID"><Code>{c.patient.patient_code}</Code></InfoItem>
        <InfoItem label="Visit">{fmt(c.visit_at)}</InfoItem>
        <InfoItem label="Doctor">{c.doctor.full_name}</InfoItem>
        <InfoItem label="Hospital">{c.facility.name}</InfoItem>
        <InfoItem label="Status"><StatusChip value={c.status} /></InfoItem>
      </Box>

      <Block title="Chief complaint"><Typography sx={text}>{c.chief_complaint}</Typography></Block>
      {c.examination && <Block title="Examination findings"><Typography sx={text}>{c.examination}</Typography></Block>}
      {vitals.length > 0 && (
        <Block title="Vital signs">
          <Stack direction="row" sx={{ gap: 1.5, flexWrap: 'wrap', mt: 0.5 }}>
            {vitals.map(([label, value, unit]) => <Vital key={label} label={label} value={value} unit={unit} />)}
          </Stack>
        </Block>
      )}
      <Box sx={{ borderLeft: 3, borderColor: 'primary.main', bgcolor: 'primary.light', px: 2, py: 1.5, borderRadius: 1 }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: 'primary.dark' }}>Diagnosis</Typography>
        <Typography sx={{ fontWeight: 600 }}>{c.diagnosis}</Typography>
      </Box>

      <Block title="Prescription">
        {c.medications.length === 0 ? (
          <Typography color="text.secondary">No medicines prescribed.</Typography>
        ) : (
          <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2, mt: 0.5 }}>
            <Table size="small">
              <TableHead>
                <TableRow><TableCell>#</TableCell><TableCell>Medicine</TableCell><TableCell>Dose</TableCell><TableCell>Frequency</TableCell><TableCell>Duration</TableCell><TableCell>Instructions</TableCell></TableRow>
              </TableHead>
              <TableBody>
                {c.medications.map((m, i) => (
                  <TableRow key={m.id}>
                    <TableCell>{i + 1}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{m.name}</TableCell>
                    <TableCell>{m.dosage}</TableCell>
                    <TableCell>{m.frequency}</TableCell>
                    <TableCell>{m.duration}</TableCell>
                    <TableCell>{m.instructions || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Block>

      {(c.advice || c.follow_up_date) && (
        <Block title="Advice & follow-up">
          {c.advice && <Typography sx={text}>{c.advice}</Typography>}
          {c.follow_up_date && (
            <Stack direction="row" sx={{ gap: 1, alignItems: 'center', mt: 1, color: 'secondary.dark' }}>
              <EventOutlined fontSize="small" />
              <Typography sx={{ fontWeight: 600 }}>Follow-up on {fmtDate(c.follow_up_date)}</Typography>
            </Stack>
          )}
        </Block>
      )}
    </Stack>
  )
}

export default function ConsultationView() {
  const { id } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const consultation = useApi(`/consultations/${id}`)
  const fhir = useApi(`/consultations/${id}/fhir`)
  const [tab, setTab] = useState(0)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [withdrawn, setWithdrawn] = useState(false)
  const c = consultation.data

  const withdraw = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post(`/consultations/${id}/withdraw`)
      setWithdrawn(true)
      consultation.reload()
      fhir.reload()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
      setConfirm(false)
    }
  }

  const canWithdraw = user.role === 'HOSPITAL' && c && c.facility.id === user.facility_id && c.status !== 'entered-in-error'
  return (
    <>
      <PageTitle
        crumbs={[[user.role === 'PATIENT' ? 'My consultations' : 'Consultations', '/consultations'], [`Consultation #${id}`]]}
        title={c ? `Consultation · ${new Date(c.visit_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}` : `Consultation #${id}`}
        subtitle={c ? `${c.doctor.full_name} · ${c.facility.name}` : undefined}
        action={canWithdraw && <Button color="error" variant="outlined" startIcon={<BlockOutlined />} onClick={() => setConfirm(true)}>Withdraw</Button>} />
      {location.state?.created && !withdrawn && <Alert severity="success" sx={{ mb: 2 }}>Consultation saved. The patient can now see it in their portal.</Alert>}
      {withdrawn && <Alert severity="success" sx={{ mb: 2 }}>Consultation withdrawn. It is now marked entered in error.</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper sx={{ overflow: 'hidden' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Summary" />
          <Tab label="FHIR R4 JSON" />
        </Tabs>
        <Box sx={{ p: { xs: 2, sm: 3 } }}>
          {tab === 0 && <Loader loading={consultation.loading} error={consultation.error}>{c && <ConsultationDetails c={c} />}</Loader>}
          {tab === 1 && <Loader loading={fhir.loading} error={fhir.error}>{fhir.data && <FhirViewer data={fhir.data} />}</Loader>}
        </Box>
      </Paper>
      <ConfirmDialog open={confirm} danger busy={busy} title="Withdraw this consultation?" confirmText="Withdraw"
        text="It will be marked 'entered in error'. The patient will still see it, clearly marked as withdrawn. This cannot be undone."
        onConfirm={withdraw} onClose={() => setConfirm(false)} />
    </>
  )
}
