import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Alert, Autocomplete, Box, Button, CircularProgress, IconButton, InputAdornment, Paper, Stack, TextField, Tooltip,
} from '@mui/material'
import AddOutlined from '@mui/icons-material/AddOutlined'
import DeleteOutlined from '@mui/icons-material/DeleteOutlined'
import api, { errorText } from '../api'
import { PageTitle, SectionCard } from '../components'

const FREQUENCIES = ['Once a day', 'Twice a day', 'Three times a day', 'Four times a day', 'At bedtime', 'As needed (SOS)']

// Vital signs: [field, label, unit, min, max, step]. Same limits as the backend (schemas.ConsultationIn).
const VITALS = [
  ['bp_systolic', 'BP systolic', 'mmHg', 50, 260, 1], ['bp_diastolic', 'BP diastolic', 'mmHg', 30, 160, 1],
  ['pulse', 'Pulse', '/min', 20, 250, 1], ['temperature', 'Temperature', '°C', 30, 45, 0.1],
  ['spo2', 'SpO₂', '%', 50, 100, 1], ['weight', 'Weight', 'kg', 0.5, 400, 0.1],
]

const newMed = () => ({ key: Math.random(), name: '', dosage: '', frequency: '', duration: '', instructions: '' })
const isBlank = (m) => !m.name.trim() && !m.dosage.trim() && !m.frequency.trim() && !m.duration.trim() && !m.instructions.trim()

function localNow() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function validate(f, meds) {
  const e = {}
  if (!f.patient) e.patient = 'Choose the patient.'
  if (!f.visit_at) e.visit_at = 'Enter the visit date and time.'
  else if (f.visit_at > localNow()) e.visit_at = 'The visit cannot be in the future.'
  if (f.chief_complaint.trim().length < 2) e.chief_complaint = 'Describe why the patient came in.'
  if (f.diagnosis.trim().length < 2) e.diagnosis = 'Enter the diagnosis or provisional diagnosis.'
  VITALS.forEach(([name, label, , min, max]) => {
    if (f[name] !== '' && (Number(f[name]) < min || Number(f[name]) > max)) e[name] = `${label}: ${min}–${max}`
  })
  if ((f.bp_systolic === '') !== (f.bp_diastolic === '')) e.bp_diastolic = 'Enter both BP values, or neither.'
  else if (f.bp_systolic !== '' && Number(f.bp_systolic) <= Number(f.bp_diastolic)) e.bp_diastolic = 'Must be lower than systolic.'
  if (f.follow_up_date && f.visit_at && f.follow_up_date < f.visit_at.slice(0, 10)) e.follow_up_date = 'Cannot be before the visit.'
  meds.forEach((m, i) => {
    if (isBlank(m)) return
    if (!m.name.trim() || !m.dosage.trim() || !m.frequency.trim() || !m.duration.trim()) {
      e[`med${m.key}`] = `Medicine ${i + 1}: enter name, dose, frequency and duration (or remove the row).`
    }
  })
  return e
}

export default function ConsultationForm() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [form, setForm] = useState({
    patient: null, visit_at: localNow(), chief_complaint: '', examination: '', diagnosis: '', advice: '', follow_up_date: '',
    bp_systolic: '', bp_diastolic: '', pulse: '', temperature: '', spo2: '', weight: '',
  })
  const [meds, setMeds] = useState([newMed()])
  const [patientOptions, setPatientOptions] = useState([])
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const errors = submitted ? validate(form, meds) : {}
  const set = (name, value) => setForm((f) => ({ ...f, [name]: value }))
  const field = (name, help = ' ') => ({
    value: form[name], onChange: (e) => set(name, e.target.value), error: Boolean(errors[name]), helperText: errors[name] || help,
  })

  useEffect(() => {
    const id = params.get('patient')
    if (id) api.get(`/patients/${id}`).then((r) => set('patient', r.data)).catch(() => {})
  }, [params])
  const searchPatients = (q) => api.get('/patients', { params: { q } }).then((r) => setPatientOptions(r.data)).catch(() => {})
  useEffect(() => { searchPatients('') }, [])

  const updateMed = (key, changes) => setMeds((ms) => ms.map((m) => (m.key === key ? { ...m, ...changes } : m)))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitted(true)
    setError('')
    if (Object.keys(validate(form, meds)).length) return
    const num = (v) => (v === '' ? null : Number(v))
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/consultations', {
        patient_id: form.patient.id,
        visit_at: new Date(form.visit_at).toISOString(),
        chief_complaint: form.chief_complaint, examination: form.examination || null,
        diagnosis: form.diagnosis, advice: form.advice || null, follow_up_date: form.follow_up_date || null,
        ...Object.fromEntries(VITALS.map(([name]) => [name, num(form[name])])),
        medications: meds.filter((m) => !isBlank(m)).map(({ name, dosage, frequency, duration, instructions }) => (
          { name, dosage, frequency, duration, instructions: instructions || null })),
      })
      navigate(`/consultations/${data.id}`, { state: { created: true } })
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  const medErrors = meds.map((m) => errors[`med${m.key}`]).filter(Boolean)
  const grid2 = { display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }

  return (
    <form onSubmit={submit} noValidate>
      <PageTitle crumbs={[['Consultations', '/consultations'], ['New consultation']]} title="New consultation"
        subtitle="Record the outpatient visit. The patient can read this summary in their portal." />
      <Stack spacing={3}>
        <SectionCard title="Patient & visit">
          <Box sx={grid2}>
            <Autocomplete
              value={form.patient}
              options={form.patient && !patientOptions.some((p) => p.id === form.patient.id) ? [form.patient, ...patientOptions] : patientOptions}
              getOptionLabel={(p) => `${p.full_name} (${p.patient_code})`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              filterOptions={(x) => x}
              noOptionsText="No matching patient"
              onInputChange={(_, v, reason) => reason === 'input' && searchPatients(v)}
              onChange={(_, v) => set('patient', v)}
              renderInput={(p) => <TextField {...p} label="Patient" required size="small" error={Boolean(errors.patient)} helperText={errors.patient || 'Search by name or patient ID'} />}
            />
            <TextField label="Visit date & time" type="datetime-local" required size="small"
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: localNow() } }} {...field('visit_at')} />
          </Box>
        </SectionCard>

        <SectionCard title="Complaint & examination">
          <Stack spacing={2}>
            <TextField label="Chief complaint" required multiline minRows={2} size="small" placeholder="e.g. Fever and sore throat for 2 days"
              slotProps={{ htmlInput: { maxLength: 500 } }} {...field('chief_complaint', 'Why the patient came in, in their words')} />
            <TextField label="Examination findings (optional)" multiline minRows={2} size="small" placeholder="e.g. Throat congested, chest clear"
              slotProps={{ htmlInput: { maxLength: 1000 } }} {...field('examination')} />
          </Stack>
        </SectionCard>

        <SectionCard title="Vital signs" subtitle="Optional. Leave blank what was not measured.">
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' } }}>
            {VITALS.map(([name, label, unit, min, max, step]) => (
              <TextField key={name} label={label} type="number" size="small" {...field(name)}
                slotProps={{
                  htmlInput: { min, max, step },
                  input: { endAdornment: <InputAdornment position="end">{unit}</InputAdornment> },
                }} />
            ))}
          </Box>
        </SectionCard>

        <SectionCard title="Diagnosis">
          <TextField label="Diagnosis" required fullWidth size="small" placeholder="e.g. Acute pharyngitis"
            slotProps={{ htmlInput: { maxLength: 300 } }} {...field('diagnosis', 'Final or provisional diagnosis (free text)')} />
        </SectionCard>

        <SectionCard title="Prescription" subtitle="Optional. Empty rows are ignored.">
          <Stack spacing={1.5}>
            {meds.map((m, i) => (
              <Paper key={m.key} variant="outlined" sx={{ p: 1.5, borderRadius: 2, borderColor: errors[`med${m.key}`] ? 'error.main' : 'divider' }}>
                <Box sx={{ display: 'grid', gap: 1.5, alignItems: 'start', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '2fr 1fr 1.3fr 1fr 1.5fr 40px' } }}>
                  <TextField size="small" label={`Medicine ${i + 1}`} placeholder="e.g. Paracetamol 500 mg tablet" value={m.name}
                    onChange={(e) => updateMed(m.key, { name: e.target.value })} slotProps={{ htmlInput: { maxLength: 120 } }} />
                  <TextField size="small" label="Dose" placeholder="1 tablet" value={m.dosage}
                    onChange={(e) => updateMed(m.key, { dosage: e.target.value })} slotProps={{ htmlInput: { maxLength: 60 } }} />
                  <Autocomplete freeSolo options={FREQUENCIES} value={m.frequency} inputValue={m.frequency}
                    onInputChange={(_, v) => updateMed(m.key, { frequency: v })}
                    renderInput={(p) => <TextField {...p} size="small" label="Frequency" />} />
                  <TextField size="small" label="Duration" placeholder="5 days" value={m.duration}
                    onChange={(e) => updateMed(m.key, { duration: e.target.value })} slotProps={{ htmlInput: { maxLength: 60 } }} />
                  <TextField size="small" label="Instructions (optional)" placeholder="After food" value={m.instructions}
                    onChange={(e) => updateMed(m.key, { instructions: e.target.value })} slotProps={{ htmlInput: { maxLength: 200 } }} />
                  <Tooltip title={`Remove medicine ${i + 1}`} describeChild>
                    <IconButton aria-label={`Remove medicine ${i + 1}`} onClick={() => setMeds(meds.length === 1 ? [newMed()] : meds.filter((x) => x.key !== m.key))}>
                      <DeleteOutlined />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Paper>
            ))}
          </Stack>
          {medErrors.length > 0 && <Alert severity="error" sx={{ mt: 1.5, whiteSpace: 'pre-line' }}>{medErrors.join('\n')}</Alert>}
          <Button sx={{ mt: 2 }} startIcon={<AddOutlined />} onClick={() => setMeds([...meds, newMed()])} disabled={meds.length >= 20}>Add medicine</Button>
        </SectionCard>

        <SectionCard title="Advice & follow-up">
          <Box sx={grid2}>
            <TextField label="Advice (optional)" multiline minRows={2} size="small" placeholder="e.g. Plenty of fluids and rest"
              slotProps={{ htmlInput: { maxLength: 1000 } }} {...field('advice')} />
            <TextField label="Follow-up date (optional)" type="date" size="small"
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: form.visit_at.slice(0, 10) } }} {...field('follow_up_date')} />
          </Box>
        </SectionCard>

        {Object.keys(errors).length > 0 && <Alert severity="error">Please correct the highlighted fields.</Alert>}
        {error && <Alert severity="error" sx={{ whiteSpace: 'pre-line' }}>{error}</Alert>}
        <Stack direction="row" sx={{ justifyContent: 'flex-end', gap: 1, alignItems: 'center' }}>
          <Button color="inherit" onClick={() => navigate(-1)} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="contained" size="large" disabled={busy}
            startIcon={busy ? <CircularProgress size={18} color="inherit" /> : null}>
            {busy ? 'Saving…' : 'Save consultation'}
          </Button>
        </Stack>
      </Stack>
    </form>
  )
}
