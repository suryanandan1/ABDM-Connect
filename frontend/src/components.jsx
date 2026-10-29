// Small pieces shared by several pages.
import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Avatar, Box, Breadcrumbs, Button, Chip, Dialog, DialogActions, DialogContent, DialogContentText,
  DialogTitle, Link, Paper, Skeleton, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead,
  TablePagination, TableRow, Tabs, Typography,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import { Link as RouterLink } from 'react-router-dom'
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import HourglassEmptyOutlined from '@mui/icons-material/HourglassEmptyOutlined'
import BlockOutlined from '@mui/icons-material/BlockOutlined'
import DoNotDisturbOnOutlined from '@mui/icons-material/DoNotDisturbOnOutlined'
import EventBusyOutlined from '@mui/icons-material/EventBusyOutlined'
import ErrorOutlineOutlined from '@mui/icons-material/ErrorOutlineOutlined'
import ArrowUpwardOutlined from '@mui/icons-material/ArrowUpwardOutlined'
import ArrowDownwardOutlined from '@mui/icons-material/ArrowDownwardOutlined'
import InboxOutlined from '@mui/icons-material/InboxOutlined'
import ContentCopyOutlined from '@mui/icons-material/ContentCopyOutlined'
import CheckOutlined from '@mui/icons-material/CheckOutlined'
import api, { errorText } from './api'

export const PURPOSES = {
  TREAT: 'Treatment',
  ETREAT: 'Emergency treatment',
  PUBHLTH: 'Public health',
  HRESCH: 'Healthcare research',
}

export const ROLE_LABELS = { ADMIN: 'Administrator', LAB: 'Laboratory (HIP)', HOSPITAL: 'Hospital (HIP + HIU)', PATIENT: 'Patient' }

export const fmt = (value) =>
  (value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—')

// Dates without a time (birth dates) are read as local dates so they never shift by a day.
export const fmtDate = (value) =>
  (value ? new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—')

// What an access request or consent covers: a lab report or a doctor consultation (metadata only).
export function recordInfo(x) {
  if (x.report) {
    return { kind: 'Lab report', title: x.report.title, ref: `Report #${x.report.id}`, holder: x.report.facility?.name, date: x.report.issued_at }
  }
  if (x.consultation) {
    const c = x.consultation
    return {
      kind: 'Consultation', title: `OP consultation · ${new Date(c.visit_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}`,
      ref: `Consultation #${c.id} · ${c.doctor.full_name}`, holder: c.facility.name, date: c.visit_at,
    }
  }
  return { kind: 'Record', title: 'Unknown record', ref: '', holder: '', date: null }
}

export function RecordKind({ value }) {
  return <Chip size="small" variant="outlined" label={value} color={value === 'Consultation' ? 'primary' : 'secondary'} sx={{ mb: 0.5 }} />
}

export const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')

// Load data from a GET endpoint; call reload() after a change.
export function useApi(url) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = useCallback(() => {
    if (!url) return
    setLoading(true)
    api
      .get(url)
      .then((r) => { setData(r.data); setError('') })
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false))
  }, [url])
  useEffect(reload, [reload])
  return { data, error, loading, reload }
}

// Page heading with optional breadcrumbs ([label, to] pairs; the last item is plain text) and actions.
export function PageTitle({ title, subtitle, action, crumbs }) {
  return (
    <Box sx={{ mb: 3 }}>
      {crumbs && (
        <Breadcrumbs sx={{ mb: 1, fontSize: 14 }}>
          {crumbs.map(([label, to]) => (to
            ? <Link key={label} component={RouterLink} to={to} underline="hover" color="text.secondary">{label}</Link>
            : <Typography key={label} color="text.primary" sx={{ fontSize: 14 }}>{label}</Typography>))}
        </Breadcrumbs>
      )}
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' }, gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h5" component="h1">{title}</Typography>
          {subtitle && <Typography color="text.secondary" sx={{ mt: 0.5 }}>{subtitle}</Typography>}
        </Box>
        {action && <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', flexShrink: 0 }}>{action}</Stack>}
      </Stack>
    </Box>
  )
}

// A white card with an optional header row. `flush` removes the body padding (for full-width tables).
export function SectionCard({ title, subtitle, action, children, flush, sx }) {
  return (
    <Paper sx={{ overflow: 'hidden', ...sx }}>
      {(title || action) && (
        <Stack direction="row" sx={{ px: 2.5, py: 2, gap: 2, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ minWidth: 0 }}>
            {title && <Typography variant="h6" component="h2">{title}</Typography>}
            {subtitle && <Typography variant="body2" color="text.secondary">{subtitle}</Typography>}
          </Box>
          {action}
        </Stack>
      )}
      <Box sx={{ p: flush ? 0 : 2.5 }}>{children}</Box>
    </Paper>
  )
}

export function EmptyState({ icon: Icon = InboxOutlined, title, text, action }) {
  return (
    <Stack sx={{ alignItems: 'center', textAlign: 'center', py: 5, px: 2, gap: 1 }}>
      <Avatar sx={{ bgcolor: 'primary.light', color: 'primary.main', width: 48, height: 48, mb: 1 }}><Icon /></Avatar>
      {title && <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{title}</Typography>}
      {text && <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>{text}</Typography>}
      {action && <Box sx={{ mt: 1 }}>{action}</Box>}
    </Stack>
  )
}

// Shows skeleton rows, an error, or an empty state; otherwise renders the children.
export function Loader({ loading, error, empty, emptyText = 'Nothing to show yet.', emptyTitle, emptyAction, children }) {
  if (loading) {
    return (
      <Stack spacing={1.5} sx={{ p: 2.5 }} role="status" aria-busy="true" aria-label="Loading">
        {[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={i ? 32 : 40} />)}
      </Stack>
    )
  }
  if (error) return <Alert severity="error" sx={{ m: 2, whiteSpace: 'pre-line' }}>{error}</Alert>
  if (empty) return <EmptyState title={emptyTitle} text={emptyText} action={emptyAction} />
  return children
}

// Status → [label, colour, icon]. Every status is shown as text, never colour alone.
const STATUS = {
  PENDING: ['Pending', 'warning', HourglassEmptyOutlined],
  ACTIVE: ['Active', 'success', CheckCircleOutlined],
  DENIED: ['Denied', 'error', BlockOutlined],
  REVOKED: ['Revoked', 'error', DoNotDisturbOnOutlined],
  EXPIRED: ['Expired', 'default', EventBusyOutlined],
  SUCCESS: ['Success', 'success', CheckCircleOutlined],
  FAILURE: ['Failure', 'error', ErrorOutlineOutlined],
  final: ['Final', 'success', CheckCircleOutlined],
  amended: ['Amended', 'info', null],
  'entered-in-error': ['Entered in error', 'error', BlockOutlined],
  H: ['High', 'error', ArrowUpwardOutlined],
  L: ['Low', 'warning', ArrowDownwardOutlined],
  N: ['Normal', 'success', null],
}

export function StatusChip({ value, label: customLabel, tone: customTone }) {
  if (!value && !customLabel) return null
  const [label, tone, Icon] = STATUS[value] || [customLabel || value, customTone || 'default', null]
  return (
    <Chip
      size="small"
      label={customLabel || label}
      icon={Icon ? <Icon /> : undefined}
      sx={(t) => {
        const main = tone === 'default' ? t.palette.grey[600] : t.palette[tone].main
        return {
          bgcolor: alpha(main, 0.1), color: tone === 'default' ? t.palette.grey[800] : t.palette[tone].dark,
          '& .MuiChip-icon': { color: 'inherit', fontSize: 16, ml: 0.75 },
        }
      }}
    />
  )
}

// A label/value pair used in detail grids.
export function InfoItem({ label, children }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 500 }}>{label}</Typography>
      <Typography component="div" variant="body2" sx={{ fontWeight: 500, overflowWrap: 'anywhere' }}>{children ?? '—'}</Typography>
    </Box>
  )
}

export const infoGrid = { display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))' }

// Monospace identifier (patient IDs, LOINC codes, facility codes).
export function Code({ children }) {
  return (
    <Box component="code" sx={{ fontFamily: 'Consolas, "SF Mono", Menlo, monospace', fontSize: '0.8125rem', bgcolor: "#F1F5F9", px: 0.75, py: 0.25, borderRadius: 1, whiteSpace: "nowrap" }}>
      {children}
    </Box>
  )
}

export function ConfirmDialog({ open, title, text, children, confirmText = 'Confirm', danger, color, onConfirm, onClose, busy }) {
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {text && <DialogContentText>{text}</DialogContentText>}
        {children}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
        <Button variant="contained" color={color || (danger ? 'error' : 'primary')} onClick={onConfirm} disabled={busy}>
          {busy ? 'Working…' : confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// Doctor consultations. `showPatient` adds a patient column (hospital lists); patients see the hospital instead.
export function ConsultationTable({ items, showPatient }) {
  const [page, setPage] = useState(0)
  const perPage = 10
  const current = Math.min(page, Math.max(0, Math.ceil(items.length / perPage) - 1))
  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Visit</TableCell><TableCell>Diagnosis</TableCell>
              {showPatient ? <TableCell>Patient</TableCell> : <TableCell>Hospital</TableCell>}
              <TableCell>Doctor</TableCell><TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.slice(current * perPage, current * perPage + perPage).map((c) => (
              <TableRow key={c.id} hover>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>
                  <Link component={RouterLink} to={`/consultations/${c.id}`} underline="hover" sx={{ fontWeight: 600 }}>{fmt(c.visit_at)}</Link>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>Consultation #{c.id}</Typography>
                </TableCell>
                <TableCell sx={{ fontWeight: 500 }}>{c.diagnosis}</TableCell>
                {showPatient
                  ? <TableCell>{c.patient.full_name}<Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{c.patient.patient_code}</Typography></TableCell>
                  : <TableCell>{c.facility.name}</TableCell>}
                <TableCell>{c.doctor.full_name}</TableCell>
                <TableCell><StatusChip value={c.status} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {items.length > perPage && (
        <TablePagination component="div" count={items.length} page={current} rowsPerPage={perPage}
          rowsPerPageOptions={[perPage]} onPageChange={(_, p) => setPage(p)} />
      )}
    </>
  )
}

export function ReportTable({ reports, linkReports = true, action }) {
  const [page, setPage] = useState(0)
  const perPage = 10
  const lastPage = Math.max(0, Math.ceil(reports.length / perPage) - 1)
  const current = Math.min(page, lastPage)
  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Report</TableCell><TableCell>Laboratory</TableCell><TableCell>Collected</TableCell>
              <TableCell>Issued</TableCell><TableCell>Status</TableCell>{action && <TableCell align="right">Action</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {reports.slice(current * perPage, current * perPage + perPage).map((r) => (
              <TableRow key={r.id} hover>
                <TableCell>
                  {linkReports
                    ? <Link component={RouterLink} to={`/reports/${r.id}`} underline="hover" sx={{ fontWeight: 600 }}>{r.title}</Link>
                    : <Typography component="span" variant="body2" sx={{ fontWeight: 600 }}>{r.title}</Typography>}
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>Report #{r.id}</Typography>
                </TableCell>
                <TableCell>{r.facility.name}</TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(r.collected_at)}</TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(r.issued_at)}</TableCell>
                <TableCell><StatusChip value={r.status} /></TableCell>
                {action && <TableCell align="right">{action(r)}</TableCell>}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {reports.length > perPage && (
        <TablePagination component="div" count={reports.length} page={current} rowsPerPage={perPage}
          rowsPerPageOptions={[perPage]} onPageChange={(_, p) => setPage(p)} />
      )}
    </>
  )
}

// Human-readable report: summary, results table and conclusion.
export function ReportDetails({ report }) {
  const abnormal = report.observations.filter((o) => o.interpretation === 'H' || o.interpretation === 'L').length
  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        <Typography variant="h6" component="h2">{report.title}</Typography>
        <StatusChip value={report.status} />
        {abnormal > 0 && <StatusChip label={`${abnormal} outside reference range`} tone="warning" />}
      </Stack>
      {report.status === 'entered-in-error' && (
        <Alert severity="warning">This report was withdrawn by the laboratory and must not be used for clinical decisions.</Alert>
      )}
      <Box sx={infoGrid}>
        <InfoItem label="Patient">{report.patient.full_name}</InfoItem>
        <InfoItem label="Patient ID"><Code>{report.patient.patient_code}</Code></InfoItem>
        <InfoItem label="Laboratory">{report.facility.name}</InfoItem>
        <InfoItem label="Specimen collected">{fmt(report.collected_at)}</InfoItem>
        <InfoItem label="Issued">{fmt(report.issued_at)}</InfoItem>
        {report.panel_loinc_code && <InfoItem label="Panel (LOINC)"><Code>{report.panel_loinc_code}</Code></InfoItem>}
      </Box>
      <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Test</TableCell><TableCell>LOINC</TableCell><TableCell align="right">Result</TableCell>
              <TableCell>Reference range</TableCell><TableCell>Flag</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {report.observations.map((o) => {
              const out = o.interpretation === 'H' || o.interpretation === 'L'
              return (
                <TableRow key={o.id}>
                  <TableCell sx={{ fontWeight: 500 }}>{o.test_name}</TableCell>
                  <TableCell>
                    <Code>{o.loinc_code}</Code>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>{o.loinc_display}</Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    <Box component="span" sx={{ fontWeight: 700, color: out ? `${o.interpretation === 'H' ? 'error' : 'warning'}.dark` : 'text.primary' }}>{o.value}</Box> {o.unit}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{o.ref_low ?? '—'} – {o.ref_high ?? '—'} {o.unit}</TableCell>
                  <TableCell><StatusChip value={o.interpretation} /></TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {report.conclusion && (
        <Box sx={{ borderLeft: 3, borderColor: 'secondary.main', bgcolor: 'secondary.light', px: 2, py: 1.5, borderRadius: 1 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'secondary.dark' }}>Conclusion</Typography>
          <Typography variant="body2">{report.conclusion}</Typography>
        </Box>
      )}
    </Stack>
  )
}

// Very small JSON highlighter: colours keys, strings, numbers and literals. The JSON text itself is unchanged.
const JSON_TOKEN = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g
const TOKEN_COLORS = { key: '#1D4F91', string: '#0B6E6B', number: '#B45309', literal: '#7C3AED' }

function JsonCode({ text }) {
  return text.split(JSON_TOKEN).map((part, i) => {
    if (i % 2 === 0) return part
    const kind = part.startsWith('"') ? (part.trimEnd().endsWith(':') ? 'key' : 'string') : /^[tfn]/.test(part) ? 'literal' : 'number'
    return <span key={i} style={{ color: TOKEN_COLORS[kind] }}>{part}</span>
  })
}

// FHIR JSON with its validation result. `data` is { resource, validation } from the API.
export function FhirViewer({ data }) {
  const [tab, setTab] = useState(0)
  const [copied, setCopied] = useState('')
  if (!data?.resource) return <Alert severity="warning">No FHIR resource was returned for this report.</Alert>

  const entries = data.resource.entry || []
  const current = Math.min(tab, entries.length)
  const shown = current === 0 ? data.resource : entries[current - 1]?.resource
  const text = JSON.stringify(shown, null, 2) ?? ''
  const { valid, errors = [], checked_against: checkedAgainst } = data.validation || {}

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied('Copied')
    } catch {
      setCopied('Copy failed')
    }
    setTimeout(() => setCopied(''), 2000)
  }

  return (
    <Box>
      {data.validation && (valid ? (
        <Alert severity="success" sx={{ mb: 2 }}>Valid. Checked against: {checkedAgainst}</Alert>
      ) : (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-line' }}>
          {errors.length} validation error(s):{'\n'}{errors.join('\n')}
        </Alert>
      ))}
      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
        <Tabs value={current} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: '#F8FAFC', px: 1 }}>
          <Tab label={`${data.resource.resourceType || 'Resource'} (${entries.length})`} />
          {entries.map((e, i) => <Tab key={e.fullUrl || i} label={`${e.resource?.resourceType}/${e.resource?.id}`} />)}
        </Tabs>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1, gap: 1, borderBottom: 1, borderColor: 'divider', flexWrap: 'wrap' }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', minWidth: 0, flexWrap: 'wrap' }}>
            <Chip size="small" label={shown?.resourceType || 'Unknown type'} color="primary" variant="outlined" />
            {shown?.id && <Typography variant="body2" color="text.secondary">id <Code>{shown.id}</Code></Typography>}
            {shown?.type && typeof shown.type === 'string' && <Typography variant="body2" color="text.secondary">type <Code>{shown.type}</Code></Typography>}
          </Stack>
          <Button size="small" startIcon={copied === 'Copied' ? <CheckOutlined /> : <ContentCopyOutlined />} onClick={copy} aria-live="polite">
            {copied || 'Copy JSON'}
          </Button>
        </Stack>
        <Box component="pre" tabIndex={0} aria-label="FHIR JSON"
          sx={{ m: 0, p: 2, maxHeight: 520, overflow: 'auto', fontSize: 12.5, lineHeight: 1.6, fontFamily: 'Consolas, "SF Mono", Menlo, monospace', bgcolor: '#FBFCFE', color: '#334155' }}>
          {shown ? <JsonCode text={text} /> : 'This entry has no resource.'}
        </Box>
      </Box>
    </Box>
  )
}
