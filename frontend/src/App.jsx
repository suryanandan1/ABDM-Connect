import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  AppBar, Avatar, Box, Button, Chip, CircularProgress, Drawer, IconButton, List, ListItemButton, ListItemIcon,
  ListItemText, Stack, Toolbar, Tooltip, Typography,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import MenuIcon from '@mui/icons-material/Menu'
import LogoutOutlined from '@mui/icons-material/LogoutOutlined'
import MonitorHeartOutlined from '@mui/icons-material/MonitorHeartOutlined'
import DashboardOutlined from '@mui/icons-material/DashboardOutlined'
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined'
import PeopleAltOutlined from '@mui/icons-material/PeopleAltOutlined'
import PersonSearchOutlined from '@mui/icons-material/PersonSearchOutlined'
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined'
import NoteAddOutlined from '@mui/icons-material/NoteAddOutlined'
import AssignmentTurnedInOutlined from '@mui/icons-material/AssignmentTurnedInOutlined'
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined'
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined'
import HistoryOutlined from '@mui/icons-material/HistoryOutlined'
import ShieldOutlined from '@mui/icons-material/ShieldOutlined'
import LockOutlined from '@mui/icons-material/LockOutlined'
import SearchOffOutlined from '@mui/icons-material/SearchOffOutlined'
import ApartmentOutlined from '@mui/icons-material/ApartmentOutlined'
import MedicalServicesOutlined from '@mui/icons-material/MedicalServicesOutlined'
import ShareOutlined from '@mui/icons-material/ShareOutlined'
import api from './api'
import { EmptyState, ROLE_LABELS, initials } from './components'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Patients from './pages/Patients'
import PatientDetail from './pages/PatientDetail'
import ReportForm from './pages/ReportForm'
import ReportView from './pages/ReportView'
import AccessRequests from './pages/AccessRequests'
import ConsentCenter from './pages/ConsentCenter'
import AuditLog from './pages/AuditLog'
import Admin from './pages/Admin'
import Consultations from './pages/Consultations'
import ConsultationForm from './pages/ConsultationForm'
import ConsultationView from './pages/ConsultationView'
import SharedRecords from './pages/SharedRecords'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

const DRAWER_WIDTH = 256

// Navigation for each role: [path, label, icon] links; a plain string starts a labelled group.
// Hospitals are both HIU (they request records) and HIP (their consultations can be shared).
const NAV = {
  ADMIN: [['/', 'Dashboard', DashboardOutlined], ['/admin', 'Users & facilities', AdminPanelSettingsOutlined],
    ['/patients', 'Patients', PeopleAltOutlined], ['/audit', 'Audit log', ReceiptLongOutlined]],
  LAB: [['/', 'Dashboard', DashboardOutlined], ['/patients', 'Patients', PeopleAltOutlined], ['/reports/new', 'New report', NoteAddOutlined],
    'Providing data (HIP)', ['/shared-records', 'Shared records', ShareOutlined]],
  HOSPITAL: [['/', 'Dashboard', DashboardOutlined], ['/patients', 'Find patient', PersonSearchOutlined],
    'Requesting data (HIU)', ['/access-requests', 'Access requests', AssignmentTurnedInOutlined],
    'Providing data (HIP)', ['/consultations', 'Consultations', MedicalServicesOutlined], ['/shared-records', 'Shared records', ShareOutlined]],
  PATIENT: [['/', 'My reports', DescriptionOutlined], ['/consultations', 'My consultations', MedicalServicesOutlined],
    ['/consents', 'Consent center', VerifiedUserOutlined], ['/audit', 'Access history', HistoryOutlined]],
}

function BackHome() {
  return <Button variant="contained" component={NavLink} to="/">Back to dashboard</Button>
}

// Which roles may open each page (the backend checks again on every request).
function Protected({ roles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) {
    return <EmptyState icon={LockOutlined} title="Access restricted" text="This page is not available for your role." action={<BackHome />} />
  }
  return children
}

function Brand({ inverse }) {
  return (
    <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5 }}>
      <Avatar variant="rounded" sx={{ bgcolor: inverse ? 'rgba(255,255,255,0.14)' : 'primary.main', width: 36, height: 36, borderRadius: 2 }}>
        <MonitorHeartOutlined fontSize="small" />
      </Avatar>
      <Box>
        <Typography sx={{ fontWeight: 700, lineHeight: 1.2, color: inverse ? '#fff' : 'text.primary' }}>ABDM Connect</Typography>
        <Typography variant="caption" sx={{ color: inverse ? 'rgba(255,255,255,0.75)' : 'text.secondary' }}>Health information exchange</Typography>
      </Box>
    </Stack>
  )
}

function NavItem({ item: [to, label, Icon], onNavigate }) {
  return (
    <ListItemButton component={NavLink} to={to} end={to === '/' || to === '/reports/new'} onClick={onNavigate}
      sx={(t) => ({
        borderRadius: 2, mb: 0.5, color: 'text.secondary', py: 1,
        '& .MuiListItemIcon-root': { color: 'inherit', minWidth: 36 },
        '&.active': { bgcolor: alpha(t.palette.primary.main, 0.08), color: 'primary.main', '& .MuiListItemText-primary': { fontWeight: 600 } },
      })}>
      <ListItemIcon><Icon fontSize="small" /></ListItemIcon>
      <ListItemText primary={label} slotProps={{ primary: { sx: { fontSize: 14.5, fontWeight: 500 } } }} />
    </ListItemButton>
  )
}

function Sidebar({ role, onNavigate }) {
  return (
    <Stack sx={{ height: '100%' }}>
      <Box sx={{ px: 2.5, height: 64, display: 'flex', alignItems: 'center' }}><Brand /></Box>
      <Typography variant="overline" color="text.secondary" sx={{ px: 3, pt: 2, fontSize: 11 }}>Menu</Typography>
      <List component="nav" aria-label="Main navigation" sx={{ px: 1.5, flexGrow: 1 }}>
        {NAV[role].map((item) => (typeof item === 'string' ? (
          <Typography key={item} variant="overline" color="text.secondary" component="div" sx={{ px: 1.5, pt: 1.5, pb: 0.5, fontSize: 11 }}>{item}</Typography>
        ) : (
          <NavItem key={item[0]} item={item} onNavigate={onNavigate} />
        )))}
      </List>
      <Box sx={{ m: 2, p: 1.5, borderRadius: 2, bgcolor: '#F8FAFC', border: 1, borderColor: 'divider' }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'flex-start' }}>
          <ShieldOutlined sx={{ fontSize: 18, color: 'secondary.main', mt: 0.25 }} />
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.5 }}>
            Test environment, not yet connected to ABDM. Do not enter real patient data.
          </Typography>
        </Stack>
      </Box>
    </Stack>
  )
}

function Shell({ user, logout, children }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const workspace = user.facility
    ? `${user.facility.name} · ${user.facility.facility_code}`
    : user.role === 'PATIENT' ? 'Patient portal' : 'Platform administration'
  const drawerPaper = { width: DRAWER_WIDTH, boxSizing: 'border-box', borderRight: 1, borderColor: 'divider' }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Box component="a" href="#main"
        sx={{ position: 'absolute', left: 8, top: -48, zIndex: 2000, bgcolor: 'primary.main', color: '#fff', px: 2, py: 1, borderRadius: 1, '&:focus': { top: 8 } }}>
        Skip to main content
      </Box>
      <Box sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)}
          sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': drawerPaper }}>
          <Sidebar role={user.role} onNavigate={() => setMobileOpen(false)} />
        </Drawer>
        <Drawer variant="permanent" open sx={{ display: { xs: 'none', md: 'block' }, '& .MuiDrawer-paper': drawerPaper }}>
          <Sidebar role={user.role} />
        </Drawer>
      </Box>

      <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <AppBar position="sticky" color="inherit" sx={{ bgcolor: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)', borderBottom: 1, borderColor: 'divider' }}>
          <Toolbar sx={{ gap: 1.5, minHeight: { xs: 64 } }}>
            <IconButton edge="start" aria-label="Open navigation" onClick={() => setMobileOpen(true)} sx={{ display: { md: 'none' } }}>
              <MenuIcon />
            </IconButton>
            <Box sx={{ display: { xs: 'block', md: 'none' } }}><Typography sx={{ fontWeight: 700 }}>ABDM Connect</Typography></Box>
            <Stack direction="row" sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1, minWidth: 0 }}>
              <ApartmentOutlined fontSize="small" sx={{ color: 'text.secondary' }} />
              <Typography variant="body2" color="text.secondary" noWrap>{workspace}</Typography>
            </Stack>
            <Box sx={{ flexGrow: 1 }} />
            <Tooltip title="Test environment, not yet connected to ABDM. Do not enter real patient data." describeChild>
              <Chip size="small" label="Test environment" variant="outlined" color="secondary" sx={{ display: { xs: 'none', sm: 'inline-flex' } }} />
            </Tooltip>
            <Stack direction="row" sx={{ alignItems: 'center', gap: 1.25 }}>
              <Avatar sx={{ width: 34, height: 34, fontSize: 14, fontWeight: 600, bgcolor: 'secondary.light', color: 'secondary.dark' }}>
                {initials(user.full_name)}
              </Avatar>
              <Box sx={{ display: { xs: 'none', sm: 'block' }, lineHeight: 1.2 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.3 }}>{user.full_name}</Typography>
                <Typography variant="caption" color="text.secondary">{ROLE_LABELS[user.role]}</Typography>
              </Box>
            </Stack>
            <Button color="inherit" size="small" startIcon={<LogoutOutlined />} onClick={logout} sx={{ color: 'text.secondary', ml: 0.5 }}>
              Log out
            </Button>
          </Toolbar>
        </AppBar>
        <Box component="main" id="main" tabIndex={-1}
          sx={{ flexGrow: 1, width: '100%', maxWidth: 1280, mx: 'auto', px: { xs: 2, sm: 3, md: 4 }, py: { xs: 3, md: 4 }, outline: 'none' }}>
          {children}
        </Box>
      </Box>
    </Box>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(Boolean(sessionStorage.getItem('token')))
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    if (!sessionStorage.getItem('token')) return
    api.get('/auth/me').then((r) => setUser(r.data)).catch(() => {}).finally(() => setChecking(false))
  }, [])

  // Start each page at the top.
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  const login = (token, userData) => {
    sessionStorage.setItem('token', token)
    setUser(userData)
    navigate('/')
  }
  const logout = async () => {
    try { await api.post('/auth/logout') } catch { /* token may already be expired */ }
    sessionStorage.removeItem('token')
    setUser(null)
    navigate('/login')
  }

  if (checking) {
    return <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><CircularProgress aria-label="Loading" /></Box>
  }

  if (!user) {
    return (
      <AuthContext.Provider value={{ user, login, logout }}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthContext.Provider>
    )
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <Shell user={user} logout={logout}>
        <Routes>
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/" element={<Protected><Dashboard /></Protected>} />
          <Route path="/patients" element={<Protected roles={['LAB', 'HOSPITAL', 'ADMIN']}><Patients /></Protected>} />
          <Route path="/patients/:id" element={<Protected roles={['LAB', 'HOSPITAL', 'ADMIN']}><PatientDetail /></Protected>} />
          <Route path="/reports/new" element={<Protected roles={['LAB']}><ReportForm /></Protected>} />
          <Route path="/reports/:id" element={<Protected roles={['LAB', 'PATIENT']}><ReportView /></Protected>} />
          <Route path="/consultations" element={<Protected roles={['HOSPITAL', 'PATIENT']}><Consultations /></Protected>} />
          <Route path="/consultations/new" element={<Protected roles={['HOSPITAL']}><ConsultationForm /></Protected>} />
          <Route path="/consultations/:id" element={<Protected roles={['HOSPITAL', 'PATIENT']}><ConsultationView /></Protected>} />
          <Route path="/shared-records" element={<Protected roles={['LAB', 'HOSPITAL']}><SharedRecords /></Protected>} />
          <Route path="/access-requests" element={<Protected roles={['HOSPITAL']}><AccessRequests /></Protected>} />
          <Route path="/consents" element={<Protected roles={['PATIENT']}><ConsentCenter /></Protected>} />
          <Route path="/audit" element={<Protected roles={['ADMIN', 'PATIENT']}><AuditLog /></Protected>} />
          <Route path="/admin" element={<Protected roles={['ADMIN']}><Admin /></Protected>} />
          <Route path="*" element={<EmptyState icon={SearchOffOutlined} title="Page not found" text="The page you are looking for does not exist." action={<BackHome />} />} />
        </Routes>
      </Shell>
    </AuthContext.Provider>
  )
}
