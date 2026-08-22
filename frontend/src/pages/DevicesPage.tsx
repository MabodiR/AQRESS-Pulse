import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorNotice, PageHeader, StatusBadge, formatDate } from '../components/Ui'
import { api } from '../lib/api'
import type { Device, DeviceStatus, Paginated, Site } from '../lib/types'

export function DevicesPage() {
  const { user } = useAuth(); const [search, setSearch] = useState(''); const [siteId, setSiteId] = useState(''); const [status, setStatus] = useState<DeviceStatus | ''>(''); const [page, setPage] = useState(1)
  const sites = useQuery({ queryKey: ['sites', 'filter'], queryFn: () => api<Paginated<Site>>('/sites?page_size=100') })
  const devices = useQuery({ queryKey: ['devices', search, siteId, status, page], queryFn: () => {
    const params = new URLSearchParams({ page: String(page), page_size: '25' })
    if (search) params.set('search', search)
    if (siteId) params.set('site_id', siteId)
    if (status) params.set('status', status)
    return api<Paginated<Device>>(`/devices?${params}`)
  } })
  return <><PageHeader title="Devices" description="Register, inspect, and maintain hardware across your sites." action={user?.role !== 'VIEWER' ? <Link className="button-primary" to="/devices/new">+ Add Device</Link> : undefined} /><div className="mb-5 grid gap-3 md:grid-cols-3"><input aria-label="Search devices" className="input" placeholder="Search name or UID…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /><select aria-label="Filter by site" className="input" value={siteId} onChange={(event) => { setSiteId(event.target.value); setPage(1) }}><option value="">All sites</option>{sites.data?.items.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select><select aria-label="Filter by status" className="input" value={status} onChange={(event) => { setStatus(event.target.value as DeviceStatus | ''); setPage(1) }}><option value="">All statuses</option>{['PROVISIONING', 'ONLINE', 'OFFLINE', 'DISABLED', 'ERROR'].map((value) => <option key={value}>{value}</option>)}</select></div>{devices.error ? <ErrorNotice error={devices.error} /> : null}{devices.isPending ? <div className="panel">Loading devices…</div> : devices.data?.items.length ? <div className="panel overflow-x-auto p-0"><table><thead><tr><th>Device</th><th>Device UID</th><th>Site</th><th>Type</th><th>Connection</th><th>Status</th><th>Last seen</th></tr></thead><tbody>{devices.data.items.map((device) => <tr key={device.id}><td><Link className="font-semibold text-cyan-300" to={`/devices/${device.id}`}>{device.name}</Link></td><td>{device.device_uid}</td><td>{device.site.name}</td><td>{device.device_type}</td><td>{device.connection_type}</td><td><StatusBadge status={device.status} /></td><td>{formatDate(device.last_seen_at)}</td></tr>)}</tbody></table></div> : <Empty>No devices match the current filters.</Empty>}<div className="mt-5 flex justify-between text-sm text-slate-400"><span>{devices.data?.pagination.total_items ?? 0} devices</span><div className="flex gap-2"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((v) => v - 1)}>Previous</button><button className="button-secondary" disabled={!devices.data || page >= devices.data.pagination.total_pages} onClick={() => setPage((v) => v + 1)}>Next</button></div></div></>
}
