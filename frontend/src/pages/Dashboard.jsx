import { Link as RouterLink } from 'react-router-dom'
import { Alert, Avatar, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import PeopleAltOutlined from '@mui/icons-material/PeopleAltOutlined'
import ApartmentOutlined from '@mui/icons-material/ApartmentOutlined'
import BadgeOutlined from '@mui/icons-material/BadgeOutlined'
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined'
import AssignmentTurnedInOutlined from '@mui/icons-material/AssignmentTurnedInOutlined'
import GppMaybeOutlined from '@mui/icons-material/GppMaybeOutlined'
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import BlockOutlined from '@mui/icons-material/BlockOutlined'
import HourglassEmptyOutlined from '@mui/icons-material/HourglassEmptyOutlined'
import DoNotDisturbOnOutlined from '@mui/icons-material/DoNotDisturbOnOutlined'
import EventBusyOutlined from '@mui/icons-material/EventBusyOutlined'
import NoteAddOutlined from '@mui/icons-material/NoteAddOutlined'
import PersonSearchOutlined from '@mui/icons-material/PersonSearchOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import MedicalServicesOutlined from '@mui/icons-material/MedicalServicesOutlined'
import PostAddOutlined from '@mui/icons-material/PostAddOutlined'
import { useAuth } from '../App'
import {
  Code, ConsultationTable, InfoItem, recordInfo, Loader, PURPOSES, PageTitle, ROLE_LABELS, ReportTable, SectionCard, StatusChip, fmt, fmtDate,
  infoGrid, initials, useApi,
} from '../components'

const CONSENT_STATES = [
  ['PENDING', 'Pending', 'warning', HourglassEmptyOutlined, 'Awaiting patient decision'],
  ['ACTIVE', 'Active', 'success', CheckCircleOutlined, 'Ready to retrieve'],
  ['DENIED', 'Denied', 'error', BlockOutlined, 'Refused by the patient'],
  ['REVOKED', 'Revoked', 'error', DoNotDisturbOnOutlined, 'Withdrawn by the patient'],
  ['EXPIRED', 'Expired', 'grey', EventBusyOutlined, 'Validity period ended'],
]

function StatCard({ icon: Icon, label, value, tone = 'primary', caption }) {
  return (
    <Paper sx={{ p: 2.5, display: 'flex', gap: 2, alignItems: 'flex-start' }}>
      <Avatar variant="rounded" sx={(t) => {
        const c = tone === 'grey' ? t.palette.grey[600] : t.palette[tone].main
        return { bgcolor: alpha(c, 0.1), color: c, borderRadius: 2, width: 42, height: 42 }
      }}>
        <Icon fontSize="small" />
      </Avatar>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>{label}</Typography>
        <Typography sx={{ fontSize: 28, fontWeight: 700, lineHeight: 1.2 }}>{value}</Typography>
        {caption && <Typography variant="caption" color="text.secondary">{caption}</Typography>}
      </Box>
    </Paper>
  )
}

const cardGrid = { display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', mb: 3 }

// Horizontal stacked bar of consent counts by status, with a text legend.
function ConsentBreakdown({ counts }) {
  const total = CONSENT_STATES.reduce((sum, [s]) => sum + (counts[s] || 0), 0)
  const color = (t, tone) => (tone === 'grey' ? t.palette.grey[500] : t.palette[tone].main)
  return (
    <SectionCard title="Consents by status" subtitle={`${total} consent record(s) in total`}>
      {total === 0 ? (
        <Typography color="text.secondary">No consents have been requested yet.</Typography>
      ) : (
        <>
          <Box role="img" aria-label={CONSENT_STATES.map(([s, label]) => `${label}: ${counts[s] || 0}`).join(', ')}
            sx={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', bgcolor: 'grey.100', mb: 2.5 }}>
            {CONSENT_STATES.map(([s, , tone]) => counts[s] > 0 && (
              <Box key={s} sx={(t) => ({ width: `${(counts[s] / total) * 100}%`, bgcolor: color(t, tone) })} />
            ))}
          </Box>
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))' }}>
            {CONSENT_STATES.map(([s, label, tone]) => (
              <Stack key={s} direction="row" sx={{ alignItems: 'center', gap: 1 }}>
                <Box sx={(t) => ({ width: 10, height: 10, borderRadius: '50%', bgcolor: color(t, tone) })} />
                <Typography variant="body2" color="text.secondary">{label}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700, ml: 'auto' }}>{counts[s] || 0}</Typography>
              </Stack>
            ))}
          </Box>
        </>
      )}
    </SectionCard>
  )
}

function AdminDashboard() {
  const { data, loading, error } = useApi('/admin/stats')
  return (
    <Loader loading={loading} error={error}>
      {data && (
        <>
          <Box sx={cardGrid}>
            <StatCard icon={BadgeOutlined} label="Users" value={data.users} />
            <StatCard icon={ApartmentOutlined} label="Facilities" value={data.facilities} tone="secondary" />
            <StatCard icon={PeopleAltOutlined} label="Patients" value={data.patients} />
            <StatCard icon={DescriptionOutlined} label="Diagnostic reports" value={data.reports} tone="secondary" />
            <StatCard icon={MedicalServicesOutlined} label="Consultations" value={data.consultations} />
            <StatCard icon={AssignmentTurnedInOutlined} label="Access requests" value={data.access_requests} tone="secondary" />
            <StatCard icon={GppMaybeOutlined} label="Failed / denied events" value={data.denied_events} tone="error" caption="Security-relevant audit events" />
          </Box>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' } }}>
            <ConsentBreakdown counts={data.consents_by_status} />
            <SectionCard title="Administration">
              <Stack spacing={1.5}>
                <Button variant="outlined" component={RouterLink} to="/admin" sx={{ justifyContent: 'flex-start' }}>Manage users & facilities</Button>
                <Button variant="outlined" component={RouterLink} to="/audit" sx={{ justifyContent: 'flex-start' }}>Open audit log</Button>
                <Typography variant="caption" color="text.secondary">Admins see report metadata only, never clinical results.</Typography>
              </Stack>
            </SectionCard>
          </Box>
        </>
      )}
    </Loader>
  )
}

function LabDashboard() {
  const { data, loading, error } = useApi('/reports')
  const reports = data || []
  const withdrawn = reports.filter((r) => r.status === 'entered-in-error').length
  return (
    <>
      {data && (
        <Box sx={cardGrid}>
          <StatCard icon={DescriptionOutlined} label="Reports issued" value={reports.length} />
          <StatCard icon={CheckCircleOutlined} label="Final" value={reports.length - withdrawn} tone="success" />
          <StatCard icon={BlockOutlined} label="Withdrawn" value={withdrawn} tone="error" caption="Marked entered in error" />
          <StatCard icon={PeopleAltOutlined} label="Patients with reports" value={new Set(reports.map((r) => r.patient_id)).size} tone="secondary" />
        </Box>
      )}
      <SectionCard title="Reports issued by your laboratory" subtitle="Most recent first" flush>
        <Loader loading={loading} error={error} empty={reports.length === 0} emptyTitle="No reports yet"
          emptyText="Create a report for a registered patient. Each result is linked to a LOINC code."
          emptyAction={<Button variant="contained" component={RouterLink} to="/reports/new">Create lab report</Button>}>
          <ReportTable reports={reports} />
        </Loader>
      </SectionCard>
    </>
  )
}

function HospitalDashboard() {
  const { data, loading, error } = useApi('/access-requests')
  const consultations = useApi('/consultations')
  const count = (s) => data?.filter((r) => r.status === s).length || 0
  return (
    <Loader loading={loading} error={error}>
      <Box sx={cardGrid}>
        {consultations.data && (
          <StatCard icon={MedicalServicesOutlined} label="Consultations recorded" value={consultations.data.length} caption="By doctors at your hospital" />
        )}
        {CONSENT_STATES.map(([s, label, tone, icon, caption]) => (
          <StatCard key={s} icon={icon} label={`Requests ${label.toLowerCase()}`} value={count(s)} tone={tone} caption={caption} />
        ))}
      </Box>
      <SectionCard title="Recent consultations" flush sx={{ mb: 3 }}
        action={<Button size="small" component={RouterLink} to="/consultations">View all consultations</Button>}>
        <Loader loading={consultations.loading} error={consultations.error} empty={consultations.data?.length === 0} emptyTitle="No consultations yet"
          emptyText="Find a patient and record their visit.">
          {consultations.data && <ConsultationTable items={consultations.data.slice(0, 5)} showPatient />}
        </Loader>
      </SectionCard>
      <SectionCard title="Recent access requests" flush
        action={<Button size="small" component={RouterLink} to="/access-requests">View access requests</Button>}>
        {data?.length ? (
          <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}>
            {data.slice(0, 5).map((r) => (
              <Stack key={r.id} direction={{ xs: 'column', sm: 'row' }} sx={{ px: 2.5, py: 1.75, gap: 1, alignItems: { sm: 'center' } }}>
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{recordInfo(r).title} · {r.patient.full_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Request #{r.id} · {recordInfo(r).kind} from {recordInfo(r).holder} · {PURPOSES[r.purpose]} · requested {fmt(r.created_at)}
                  </Typography>
                </Box>
                <StatusChip value={r.status} />
              </Stack>
            ))}
          </Stack>
        ) : (
          <Typography color="text.secondary" sx={{ p: 2.5 }}>
            No access requests yet. Find a patient and request a lab report or another hospital's consultation.
          </Typography>
        )}
      </SectionCard>
    </Loader>
  )
}

function PatientDashboard() {
  const { user } = useAuth()
  const profile = useApi(`/patients/${user.patient_id}`)
  const reports = useApi('/reports')
  const consultations = useApi('/consultations')
  const { data: requests } = useApi('/access-requests')
  const pending = requests?.filter((r) => r.status === 'PENDING').length || 0
  const active = requests?.filter((r) => r.status === 'ACTIVE').length || 0
  const p = profile.data
  return (
    <Stack spacing={3}>
      {pending > 0 && (
        <Alert severity="warning" variant="outlined" sx={{ bgcolor: 'background.paper', alignItems: 'center' }}
          action={<Button variant="contained" color="warning" component={RouterLink} to="/consents">Review requests</Button>}>
          You have <b>{pending}</b> access request(s) waiting for your decision.
        </Alert>
      )}
      {p && (
        <Paper sx={{ p: 2.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2.5, alignItems: { sm: 'center' } }}>
            <Avatar sx={{ width: 56, height: 56, bgcolor: 'primary.light', color: 'primary.main', fontWeight: 700 }}>{initials(p.full_name)}</Avatar>
            <Box sx={{ ...infoGrid, flexGrow: 1 }}>
              <InfoItem label="Name">{p.full_name}</InfoItem>
              <InfoItem label="Patient ID"><Code>{p.patient_code}</Code></InfoItem>
              <InfoItem label="Gender"><Box component="span" sx={{ textTransform: 'capitalize' }}>{p.gender}</Box></InfoItem>
              <InfoItem label="Date of birth">{fmtDate(p.birth_date)}</InfoItem>
              <InfoItem label="Registered">{fmt(p.created_at)}</InfoItem>
            </Box>
          </Stack>
        </Paper>
      )}
      {reports.data && requests && (
        <Box sx={{ ...cardGrid, mb: 0 }}>
          <StatCard icon={DescriptionOutlined} label="My reports" value={reports.data.length} />
          {consultations.data && <StatCard icon={MedicalServicesOutlined} label="Consultations" value={consultations.data.length} tone="secondary" caption="Visits recorded by your doctors" />}
          <StatCard icon={HourglassEmptyOutlined} label="Awaiting your decision" value={pending} tone="warning" />
          <StatCard icon={VerifiedUserOutlined} label="Active consents" value={active} tone="success" caption="Hospitals that can read a report now" />
        </Box>
      )}
      <SectionCard title="Recent consultations" subtitle="Visit summaries and prescriptions from your doctors" flush
        action={<Button size="small" component={RouterLink} to="/consultations">View all consultations</Button>}>
        <Loader loading={consultations.loading} error={consultations.error} empty={consultations.data?.length === 0} emptyTitle="No consultations yet"
          emptyText="When a doctor records a visit, the summary appears here.">
          {consultations.data && <ConsultationTable items={consultations.data.slice(0, 5)} />}
        </Loader>
      </SectionCard>
      <SectionCard title="My reports" subtitle="Reports issued to you by laboratories" flush>
        <Loader loading={reports.loading} error={reports.error} empty={reports.data?.length === 0} emptyTitle="No reports yet"
          emptyText="Reports appear here once a laboratory issues them to you.">
          {reports.data && <ReportTable reports={reports.data} />}
        </Loader>
      </SectionCard>
    </Stack>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const actions = {
    LAB: (
      <>
        <Button variant="outlined" component={RouterLink} to="/patients" startIcon={<PersonSearchOutlined />}>Register / find patient</Button>
        <Button variant="contained" component={RouterLink} to="/reports/new" startIcon={<NoteAddOutlined />}>Create lab report</Button>
      </>
    ),
    HOSPITAL: (
      <>
        <Button variant="outlined" component={RouterLink} to="/patients" startIcon={<PersonSearchOutlined />}>Find a patient</Button>
        <Button variant="contained" component={RouterLink} to="/consultations/new" startIcon={<PostAddOutlined />}>New consultation</Button>
      </>
    ),
  }
  return (
    <>
      <PageTitle title={`Welcome, ${user.full_name}`}
        subtitle={user.facility ? `${user.facility.name} (${user.facility.facility_code}) · ${ROLE_LABELS[user.role]}` : ROLE_LABELS[user.role]}
        action={actions[user.role]} />
      {user.role === 'ADMIN' && <AdminDashboard />}
      {user.role === 'LAB' && <LabDashboard />}
      {user.role === 'HOSPITAL' && <HospitalDashboard />}
      {user.role === 'PATIENT' && <PatientDashboard />}
    </>
  )
}
