import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Box, Button, InputAdornment, TextField } from '@mui/material'
import PostAddOutlined from '@mui/icons-material/PostAddOutlined'
import SearchIcon from '@mui/icons-material/Search'
import { useAuth } from '../App'
import { ConsultationTable, Loader, PageTitle, SectionCard, useApi } from '../components'

export default function Consultations() {
  const { user } = useAuth()
  const isDoctor = user.role === 'HOSPITAL'
  const { data, loading, error } = useApi('/consultations')
  const [filter, setFilter] = useState('')
  const shown = (data || []).filter((c) =>
    `${c.diagnosis} ${c.patient.full_name} ${c.patient.patient_code} ${c.doctor.full_name} ${c.facility.name}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <>
      <PageTitle
        title={isDoctor ? 'Consultations' : 'My consultations'}
        subtitle={isDoctor ? 'Outpatient visits recorded by doctors at your hospital' : 'Visit summaries and prescriptions from your doctors'}
        action={isDoctor && <Button variant="contained" startIcon={<PostAddOutlined />} component={RouterLink} to="/consultations/new">New consultation</Button>}
      />
      <SectionCard flush>
        <Box sx={{ p: 2.5, borderBottom: 1, borderColor: 'divider' }}>
          <TextField size="small" fullWidth placeholder={isDoctor ? 'Filter by patient, diagnosis or doctor' : 'Filter by diagnosis, doctor or hospital'}
            value={filter} onChange={(e) => setFilter(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Filter consultations' },
              input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
            }} />
        </Box>
        <Loader loading={loading} error={error} empty={shown.length === 0} emptyTitle="No consultations"
          emptyText={data?.length ? 'No consultations match the filter.'
            : isDoctor ? 'Open a patient from "Find patient", or start a new consultation.' : 'When a doctor records a visit, the summary appears here.'}
          emptyAction={isDoctor && !data?.length && <Button variant="contained" component={RouterLink} to="/consultations/new">Start a consultation</Button>}>
          <ConsultationTable items={shown} showPatient={isDoctor} />
        </Loader>
      </SectionCard>
    </>
  )
}
