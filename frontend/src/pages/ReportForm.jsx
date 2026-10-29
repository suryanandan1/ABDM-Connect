import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Alert, Autocomplete, Avatar, Box, Button, CircularProgress, IconButton, MenuItem, Paper, Stack, TextField, Tooltip, Typography,
} from '@mui/material'
import DeleteOutlined from '@mui/icons-material/DeleteOutlined'
import AddOutlined from '@mui/icons-material/AddOutlined'
import PlaylistAddOutlined from '@mui/icons-material/PlaylistAddOutlined'
import api, { errorText } from '../api'
import { Code, PageTitle, SectionCard, useApi } from '../components'

// Illustrative adult reference ranges for the CBC template (edit them to match your lab).
const CBC_TEMPLATE = [
  ['718-7', 'Hemoglobin', 12, 15.5], ['6690-2', 'WBC count', 4, 11], ['789-8', 'RBC count', 4.2, 5.4],
  ['4544-3', 'Hematocrit', 36, 46], ['787-2', 'MCV', 80, 100], ['785-6', 'MCH', 27, 33],
  ['786-4', 'MCHC', 32, 36], ['777-3', 'Platelet count', 150, 410],
]
const newRow = () => ({ key: Math.random(), concept: null, test_name: '', value: '', unit: '', ref_low: '', ref_high: '' })

function localNow(offsetMinutes = 0) {
  const d = new Date(Date.now() - offsetMinutes * 60000)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

// Search-as-you-type LOINC picker. Nothing is chosen automatically: the user must pick a concept.
function LoincPicker({ kind, value, onChange, label }) {
  const [input, setInput] = useState('')
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (input.trim().length < 2 || (value && input === `${value.code} · ${value.display}`)) return
    const timer = setTimeout(() => {
      setLoading(true)
      setFailed(false)
      api.get('/loinc/search', { params: { q: input, kind } })
        .then((r) => setOptions(r.data))
        .catch(() => { setOptions([]); setFailed(true) })
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(timer)
  }, [input, kind, value])

  const noOptions = failed ? 'LOINC search failed. Check that the backend is running, then type again.'
    : input.trim().length < 2 ? 'Type at least 2 characters' : `No LOINC concept matches "${input}"`

  return (
    <Autocomplete
      value={value}
      options={value && !options.some((o) => o.code === value.code) ? [value, ...options] : options}
      loading={loading}
      loadingText="Searching LOINC…"
      filterOptions={(x) => x}
      getOptionLabel={(o) => `${o.code} · ${o.display}`}
      isOptionEqualToValue={(a, b) => a.code === b.code}
      onInputChange={(_, v) => setInput(v)}
      onChange={(_, v) => onChange(v)}
      noOptionsText={noOptions}
      renderOption={(props, o) => (
        <li {...props} key={o.code}>
          <Box>
            <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
              <Code>{o.code}</Code>
              <Typography variant="body2">{o.display}</Typography>
            </Stack>
            {(o.abbreviations.length > 0 || o.unit) && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.25 }}>
                {o.abbreviations.length > 0 && `Also: ${o.abbreviations.join(', ')}`}
                {o.abbreviations.length > 0 && o.unit && ' · '}
                {o.unit && `Unit: ${o.unit}`}
              </Typography>
            )}
          </Box>
        </li>
      )}
      renderInput={(params) => (
        <TextField {...params} label={label} size="small" placeholder="Search name, abbreviation or code"
          helperText={value ? `Selected: ${value.display}` : 'Pick a concept from the list'}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              endAdornment: <>{loading && <CircularProgress color="inherit" size={16} />}{params.slotProps.input.endAdornment}</>,
            },
          }} />
      )}
    />
  )
}

export default function ReportForm() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const units = useApi('/loinc/units')
  const [patient, setPatient] = useState(null)
  const [patientOptions, setPatientOptions] = useState([])
  const [title, setTitle] = useState('')
  const [panel, setPanel] = useState(null)
  const [collectedAt, setCollectedAt] = useState(localNow(60))
  const [conclusion, setConclusion] = useState('')
  const [rows, setRows] = useState([newRow()])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadingTemplate, setLoadingTemplate] = useState(false)

  useEffect(() => {
    const id = params.get('patient')
    if (id) api.get(`/patients/${id}`).then((r) => setPatient(r.data)).catch(() => {})
  }, [params])

  const searchPatients = (q) => api.get('/patients', { params: { q } }).then((r) => setPatientOptions(r.data)).catch(() => {})
  useEffect(() => { searchPatients('') }, [])

  const updateRow = (key, changes) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...changes } : r)))

  const pickConcept = (row, concept) => updateRow(row.key, {
    concept,
    test_name: row.test_name || (concept ? concept.abbreviations[0] || concept.display : ''),
    unit: concept?.unit || row.unit,
  })

  const loadCbcTemplate = async () => {
    setError('')
    setLoadingTemplate(true)
    try {
      const found = await Promise.all(CBC_TEMPLATE.map(([code]) => api.get('/loinc/search', { params: { q: code } })))
      const panelResult = await api.get('/loinc/search', { params: { q: '58410-2' } })
      setRows(CBC_TEMPLATE.map(([code, name, low, high], i) => {
        const concept = found[i].data.find((c) => c.code === code)
        return { ...newRow(), concept, test_name: name, unit: concept.unit, ref_low: low, ref_high: high }
      }))
      setPanel(panelResult.data[0])
      setTitle('Complete Blood Count')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoadingTemplate(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    const problems = []
    if (!patient) problems.push('Choose a patient.')
    if (title.trim().length < 2) problems.push('Enter a report title.')
    rows.forEach((r, i) => {
      if (!r.concept) problems.push(`Test ${i + 1}: select a LOINC concept from the list.`)
      if (r.value === '' || Number.isNaN(Number(r.value))) problems.push(`Test ${i + 1}: enter a numeric result.`)
      if (!r.unit) problems.push(`Test ${i + 1}: choose a unit.`)
      if (r.ref_low !== '' && r.ref_high !== '' && Number(r.ref_low) > Number(r.ref_high)) problems.push(`Test ${i + 1}: reference low must not be greater than high.`)
    })
    if (problems.length) { setError(problems.join('\n')); return }
    const num = (v) => (v === '' ? null : Number(v))
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/reports', {
        patient_id: patient.id,
        title,
        panel_loinc_code: panel?.code || null,
        collected_at: new Date(collectedAt).toISOString(),
        conclusion: conclusion || null,
        observations: rows.map((r) => ({
          test_name: r.test_name, loinc_code: r.concept.code, value: Number(r.value), unit: r.unit,
          ref_low: num(r.ref_low), ref_high: num(r.ref_high),
        })),
      })
      navigate(`/reports/${data.id}`, { state: { created: true } })
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <PageTitle title="New laboratory report" subtitle="Each result must be linked to a LOINC concept you select"
        action={(
          <Button variant="outlined" startIcon={loadingTemplate ? <CircularProgress size={16} /> : <PlaylistAddOutlined />}
            onClick={loadCbcTemplate} disabled={loadingTemplate}>
            Fill CBC template
          </Button>
        )} />

      <Stack spacing={3}>
        <SectionCard title="Patient & specimen" subtitle="Who the report is for and when the sample was taken">
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
            <Autocomplete
              value={patient}
              options={patient && !patientOptions.some((p) => p.id === patient.id) ? [patient, ...patientOptions] : patientOptions}
              getOptionLabel={(p) => `${p.full_name} (${p.patient_code})`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              filterOptions={(x) => x}
              noOptionsText="No matching patient. Register the patient first."
              onInputChange={(_, v, reason) => reason === 'input' && searchPatients(v)}
              onChange={(_, v) => setPatient(v)}
              renderInput={(p) => <TextField {...p} label="Patient" required size="small" helperText="Search by name or patient ID" />}
            />
            <TextField label="Specimen collected at" type="datetime-local" required size="small" value={collectedAt} helperText="Cannot be in the future"
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: localNow() } }} onChange={(e) => setCollectedAt(e.target.value)} />
          </Box>
        </SectionCard>

        <SectionCard title="Report details">
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
            <TextField label="Report title" required size="small" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Complete Blood Count" helperText=" " />
            <LoincPicker kind="panel" label="Panel LOINC code (optional)" value={panel} onChange={setPanel} />
            <TextField label="Conclusion (optional)" size="small" multiline minRows={2} value={conclusion}
              onChange={(e) => setConclusion(e.target.value)} sx={{ gridColumn: { md: 'span 2' } }}
              slotProps={{ htmlInput: { maxLength: 500 } }} helperText={`${conclusion.length}/500`} />
          </Box>
        </SectionCard>

        <SectionCard title="Results" subtitle={`${rows.length} test(s) · the high/low flag is calculated from the reference range when saved`}>
          <Stack spacing={1.5}>
            {rows.map((row, i) => (
              <Paper key={row.key} variant="outlined" sx={{ p: 1.5, borderRadius: 2, bgcolor: row.concept ? 'background.paper' : '#FCFDFE' }}>
                <Box sx={{ display: 'grid', gap: 1.5, alignItems: 'start', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '28px 2.4fr 1.3fr 0.9fr 1fr 0.8fr 0.8fr 40px' } }}>
                  <Avatar sx={{ width: 26, height: 26, fontSize: 12, fontWeight: 700, bgcolor: row.concept ? 'secondary.light' : 'grey.100', color: row.concept ? 'secondary.dark' : 'text.secondary', mt: 0.5, display: { xs: 'none', lg: 'flex' } }}>
                    {i + 1}
                  </Avatar>
                  <Box sx={{ gridColumn: { sm: 'span 2', lg: 'auto' } }}>
                    <LoincPicker kind="test" label={`Test ${i + 1}: LOINC concept`} value={row.concept} onChange={(c) => pickConcept(row, c)} />
                  </Box>
                  <TextField size="small" label="Test name (lab)" required value={row.test_name} onChange={(e) => updateRow(row.key, { test_name: e.target.value })} />
                  <TextField size="small" label="Result" required type="number" value={row.value}
                    slotProps={{ htmlInput: { step: 'any', min: 0 } }} onChange={(e) => updateRow(row.key, { value: e.target.value })} />
                  <TextField size="small" select label="Unit (UCUM)" value={row.unit} onChange={(e) => updateRow(row.key, { unit: e.target.value })}>
                    {(units.data || []).map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
                  </TextField>
                  <TextField size="small" label="Ref low" type="number" value={row.ref_low}
                    slotProps={{ htmlInput: { step: 'any' } }} onChange={(e) => updateRow(row.key, { ref_low: e.target.value })} />
                  <TextField size="small" label="Ref high" type="number" value={row.ref_high}
                    slotProps={{ htmlInput: { step: 'any' } }} onChange={(e) => updateRow(row.key, { ref_high: e.target.value })} />
                  <Tooltip title={rows.length === 1 ? 'A report needs at least one test' : `Remove test ${i + 1}`} describeChild>
                    <span>
                      <IconButton aria-label={`Remove test ${i + 1}`} disabled={rows.length === 1} onClick={() => setRows(rows.filter((r) => r.key !== row.key))}>
                        <DeleteOutlined />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Box>
              </Paper>
            ))}
          </Stack>
          <Button sx={{ mt: 2 }} startIcon={<AddOutlined />} onClick={() => setRows([...rows, newRow()])} disabled={rows.length >= 30}>Add test</Button>
          {rows.length >= 30 && <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>Maximum of 30 tests per report.</Typography>}
        </SectionCard>

        {error && <Alert severity="error" sx={{ whiteSpace: 'pre-line' }}>{error}</Alert>}
        <Stack direction="row" sx={{ justifyContent: 'flex-end', gap: 1 }}>
          <Button color="inherit" onClick={() => navigate(-1)} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="contained" size="large" disabled={busy}
            startIcon={busy ? <CircularProgress size={18} color="inherit" /> : null}>
            {busy ? 'Saving…' : 'Save report'}
          </Button>
        </Stack>
      </Stack>
    </form>
  )
}
