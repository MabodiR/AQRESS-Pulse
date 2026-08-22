import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { AppShell } from './components/AppShell'
import { DeviceDetailPage } from './pages/DeviceDetailPage'
import { DeviceFormPage } from './pages/DeviceFormPage'
import { DevicesPage } from './pages/DevicesPage'
import { LoginPage } from './pages/LoginPage'
import { SiteDetailPage } from './pages/SiteDetailPage'
import { SiteFormPage } from './pages/SiteFormPage'
import { SitesPage } from './pages/SitesPage'

function Protected() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <main className="grid min-h-screen place-items-center bg-slate-950 text-slate-300">Restoring your session…</main>
  return user ? <AppShell /> : <Navigate to="/login" replace state={{ from: location.pathname }} />
}

function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<Protected />}><Route path="/sites" element={<SitesPage />} /><Route path="/sites/new" element={<SiteFormPage />} /><Route path="/sites/:siteId" element={<SiteDetailPage />} /><Route path="/sites/:siteId/edit" element={<SiteFormPage />} /><Route path="/devices" element={<DevicesPage />} /><Route path="/devices/new" element={<DeviceFormPage />} /><Route path="/devices/:deviceId" element={<DeviceDetailPage />} /><Route path="/devices/:deviceId/edit" element={<DeviceFormPage />} /></Route><Route path="*" element={<Navigate to="/sites" replace />} /></Routes>
}

export default App
