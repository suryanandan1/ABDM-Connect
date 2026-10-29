import { useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { Alert, Box, Button, Paper, Tab, Tabs } from '@mui/material'
import BlockOutlined from '@mui/icons-material/BlockOutlined'
import api, { errorText } from '../api'
import { useAuth } from '../App'
import { ConfirmDialog, FhirViewer, Loader, PageTitle, ReportDetails, useApi } from '../components'

export default function ReportView() {
  const { id } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const report = useApi(`/reports/${id}`)
  const fhir = useApi(`/reports/${id}/fhir`)
  const [tab, setTab] = useState(0)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [withdrawn, setWithdrawn] = useState(false)

  const withdraw = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post(`/reports/${id}/withdraw`)
      setWithdrawn(true)
      report.reload()
      fhir.reload()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
      setConfirm(false)
    }
  }

  const canWithdraw = user.role === 'LAB' && report.data && report.data.status !== 'entered-in-error'
  return (
    <>
      <PageTitle
        crumbs={[['Reports', '/'], [`Report #${id}`]]}
        title={report.data?.title || `Report #${id}`}
        subtitle={report.data ? `Report #${id} · ${report.data.facility.name}` : undefined}
        action={canWithdraw && <Button color="error" variant="outlined" startIcon={<BlockOutlined />} onClick={() => setConfirm(true)}>Withdraw report</Button>} />
      {location.state?.created && !withdrawn && <Alert severity="success" sx={{ mb: 2 }}>Report saved. Its FHIR R4 representation is on the second tab.</Alert>}
      {withdrawn && <Alert severity="success" sx={{ mb: 2 }}>Report withdrawn. It is now marked entered in error.</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper sx={{ overflow: 'hidden' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Report" />
          <Tab label="FHIR R4 JSON" />
        </Tabs>
        <Box sx={{ p: { xs: 2, sm: 3 } }}>
          {tab === 0 && <Loader loading={report.loading} error={report.error}>{report.data && <ReportDetails report={report.data} />}</Loader>}
          {tab === 1 && <Loader loading={fhir.loading} error={fhir.error}>{fhir.data && <FhirViewer data={fhir.data} />}</Loader>}
        </Box>
      </Paper>
      <ConfirmDialog open={confirm} danger busy={busy} title="Withdraw this report?" confirmText="Withdraw"
        text="The report will be marked 'entered in error'. Hospitals will no longer be able to request or retrieve it. This cannot be undone."
        onConfirm={withdraw} onClose={() => setConfirm(false)} />
    </>
  )
}
