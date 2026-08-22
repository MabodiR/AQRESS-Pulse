import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

const nav = [{ to: '/sites', label: 'Sites' }, { to: '/devices', label: 'Devices' }]

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/95">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <NavLink to="/sites" className="text-xl font-bold"><span className="text-cyan-400">AQRESS</span> Pulse</NavLink>
          <div className="flex items-center gap-4 text-sm"><span className="hidden text-slate-400 sm:inline">{user?.first_name} · {user?.role}</span><button className="button-secondary" onClick={() => void logout().then(() => navigate('/login'))}>Log out</button></div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl md:grid-cols-[220px_1fr]">
        <aside className="border-b border-slate-800 p-4 md:min-h-[calc(100vh-73px)] md:border-b-0 md:border-r">
          <nav className="flex gap-2 md:flex-col">{nav.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => `rounded-lg px-4 py-3 text-sm font-medium ${isActive ? 'bg-cyan-500/15 text-cyan-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'}`}>{item.label}</NavLink>)}</nav>
        </aside>
        <main className="min-w-0 p-5 sm:p-8"><Outlet /></main>
      </div>
    </div>
  )
}
