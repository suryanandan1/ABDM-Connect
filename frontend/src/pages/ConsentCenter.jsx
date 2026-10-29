import { useState } from 'react'
import { Alert, Avatar, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import LocalHospitalOutlined from '@mui/icons-material/LocalHospitalOutlined'
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined'
import BlockOutlined from '@mui/icons-material/BlockOutlined'
import DoNotDisturbOnOutlined from '@mui/icons-material/DoNotDisturbOnOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import api, { errorText } from '../api'
import { ConfirmDialog, InfoItem, Loader, PURPOSES, PageTitle, RecordKind, StatusChip, fmt, infoGrid, recordInfo, useApi } from '../components'

const ACTIONS = {
  approve: { title: 'Approve this request?', confirm: 'Approve', color: 'success', done: 'Consent approved.',
    text: (c) => `${c.requester_facility.name} will be able to read "${recordInfo(c).title}" for ${c.duration_days} day(s), for ${PURPOSES[c.purpose]}.` },
  deny: { title: 'Deny this request?', confirm: 'Deny', color: 'error', done: 'Consent denied.',
    text: (c) => `${c.requester_facility.name} will not be able to read "${recordInfo(c).title}".` },
  revoke: { title: 'Revoke this consent?', confirm: 'Revoke', color: 'error', done: 'Consent revoked.',
    text: (c) => `${c.requester_facility.name} will immediately lose access to "${recordInfo(c).title}". This cannot be undone; they would need to ask again.` },
}

const ACCENT = { PENDING: 'warning.main', ACTIVE: 'success.main' }

function ConsentCard({ consent: c, onAction }) {
  return (
    <Paper sx={{ p: 2.5, borderLeft: 4, borderLeftColor: ACCENT[c.status] || 'divider' }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: 'flex-start', mb: 2 }}>
        <Avatar variant="rounded" sx={{ bgcolor: 'primary.light', color: 'primary.main', borderRadius: 2 }}><LocalHospitalOutlined /></Avatar>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600 }}>{c.requester_facility.name}</Typography>
          <Typography variant="caption" color="text.secondary">
            {c.requester_facility.facility_code}{c.requester_facility.city && ` · ${c.requester_facility.city}`} · requests access to your record
          </Typography>
        </Box>
        <StatusChip value={c.status} />
      </Stack>

      <Box sx={infoGrid}>
        <InfoItem label="Requested record">
          <RecordKind value={recordInfo(c).kind} />
          <Box>{recordInfo(c).title}</Box>
        </InfoItem>
        <InfoItem label="Held by">{recordInfo(c).holder}</InfoItem>
        <InfoItem label="Purpose">{PURPOSES[c.purpose]}</InfoItem>
        <InfoItem label="Access duration">{c.duration_days} day(s)</InfoItem>
        <InfoItem label="Requested on">{fmt(c.created_at)}</InfoItem>
        {c.decided_at && <InfoItem label="Decided on">{fmt(c.decided_at)}</InfoItem>}
        {c.expires_at && <InfoItem label={c.status === 'EXPIRED' ? 'Expired on' : 'Valid until'}>{fmt(c.expires_at)}</InfoItem>}
        {c.revoked_at && <InfoItem label="Revoked on">{fmt(c.revoked_at)}</InfoItem>}
      </Box>

      {c.status === 'PENDING' && (
        <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: 'divider', gap: 1.5, alignItems: { sm: 'center' } }}>
          <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
            Nothing is shared until you approve. Approval lasts {c.duration_days} day(s) and you can revoke it at any time.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button color="error" variant="outlined" startIcon={<BlockOutlined />} onClick={() => onAction(c, 'deny')}>Deny</Button>
            <Button color="success" variant="contained" startIcon={<CheckCircleOutlined />} onClick={() => onAction(c, 'approve')}>Approve</Button>
          </Stack>
        </Stack>
      )}
      {c.status === 'ACTIVE' && (
        <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: 'divider', gap: 1.5, alignItems: { sm: 'center' } }}>
          <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
            This hospital can read the record until {fmt(c.expires_at)}.
          </Typography>
          <Button color="error" variant="outlined" startIcon={<DoNotDisturbOnOutlined />} onClick={() => onAction(c, 'revoke')}>Revoke</Button>
        </Stack>
      )}
    </Paper>
  )
}

export default function ConsentCenter() {
  const { data, loading, error, reload } = useApi('/consents')
  const [pending, setPending] = useState(null) // { consent, action } waiting for confirmation
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  const run = async () => {
    setBusy(true)
    try {
      await api.post(`/consents/${pending.consent.id}/${pending.action}`)
      setMessage({ severity: 'success', text: ACTIONS[pending.action].done })
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err) })
    } finally {
      setBusy(false)
      setPending(null)
      reload()
    }
  }

  const groups = [
    ['Waiting for your decision', 'Hospitals asking to read one of your records', (c) => c.status === 'PENDING'],
    ['Active consents', 'Hospitals that can read a record right now', (c) => c.status === 'ACTIVE'],
    ['History', 'Denied, revoked and expired consents', (c) => !['PENDING', 'ACTIVE'].includes(c.status)],
  ]
  const action = pending && ACTIONS[pending.action]
  const c = pending?.consent

  return (
    <>
      <PageTitle title="Consent center" subtitle="You decide which hospital may read which record, for how long"
        action={<Button startIcon={<RefreshIcon />} onClick={reload} disabled={loading}>Refresh</Button>} />
      {message && <Alert severity={message.severity} sx={{ mb: 3 }} onClose={() => setMessage(null)}>{message.text}</Alert>}
      <Loader loading={loading && !data} error={error} empty={data?.length === 0} emptyTitle="No requests yet"
        emptyText="No hospital has requested your records yet. When one does, it will appear here for your decision.">
        {data && groups.map(([title, subtitle, test]) => {
          const items = data.filter(test)
          return (
            <Box key={title} component="section" sx={{ mb: 4 }}>
              <Stack direction="row" sx={{ alignItems: 'center', gap: 1, mb: 0.25 }}>
                <Typography variant="h6" component="h2">{title}</Typography>
                <Chip size="small" label={items.length} />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{subtitle}</Typography>
              <Stack spacing={1.5}>
                {items.map((consent) => <ConsentCard key={consent.id} consent={consent} onAction={(x, a) => setPending({ consent: x, action: a })} />)}
                {items.length === 0 && (
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2, px: 2.5, border: 1, borderStyle: 'dashed', borderColor: 'divider', borderRadius: 2 }}>
                    None.
                  </Typography>
                )}
              </Stack>
            </Box>
          )
        })}
      </Loader>
      {pending && (
        <ConfirmDialog open title={action.title} text={action.text(c)} confirmText={action.confirm}
          color={action.color} busy={busy} onConfirm={run} onClose={() => setPending(null)}>
          <Box sx={{ ...infoGrid, gridTemplateColumns: '1fr 1fr', mt: 2, p: 1.5, bgcolor: '#F8FAFC', borderRadius: 2, border: 1, borderColor: 'divider' }}>
            <InfoItem label="Hospital">{c.requester_facility.name}</InfoItem>
            <InfoItem label="Record">{recordInfo(c).title}</InfoItem>
            <InfoItem label="Purpose">{PURPOSES[c.purpose]}</InfoItem>
            <InfoItem label={pending.action === 'revoke' ? 'Currently valid until' : 'Duration'}>
              {pending.action === 'revoke' ? fmt(c.expires_at) : `${c.duration_days} day(s)`}
            </InfoItem>
          </Box>
          {pending.action === 'approve' && (
            <Stack direction="row" sx={{ gap: 1, mt: 2, alignItems: 'flex-start' }}>
              <VerifiedUserOutlined fontSize="small" sx={{ color: 'secondary.main' }} />
              <Typography variant="caption" color="text.secondary">Access starts only after the server confirms your approval. You can revoke it later.</Typography>
            </Stack>
          )}
        </ConfirmDialog>
      )}
    </>
  )
}
