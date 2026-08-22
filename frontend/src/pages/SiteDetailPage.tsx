import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorNotice, PageHeader, StatusBadge, formatDate } from '../components/Ui'
import { api } from '../lib/api'
import type { Device, Paginated, Site } from '../lib/types'

export function SiteDetailPage() {
  const { siteId } = useParams(); const { user } = useAuth(); const queryClient = useQueryClient()
  const site = useQuery({ queryKey: ['site', siteId], queryFn: () => api<Site>(`/sites/${siteId}`) })
  const devices = useQuery({ queryKey: ['site-devices', siteId], queryFn: () => api<Paginated<Device>>(`/sites/${siteId}/devices`) })
  const status = useMutation({ mutationFn: (active: boolean) => api<Site>(`/sites/${siteId}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['site', siteId] }) } })
  if (site.isPending) return <div className="panel">Loading site…</div>
  if (site.error || !site.data) return <ErrorNotice error={site.error} />
  const value = site.data
  return <><PageHeader title={value.name} description={value.description || 'No description provided.'} action={<div className="flex gap-2">{user?.role !== 'VIEWER' ? <><Link className="button-secondary" to={`/sites/${value.id}/edit`}>Edit Site</Link><Link className="button-primary" to={`/devices/new?site_id=${value.id}`}>+ Add Device</Link></> : null}</div>} /><div className="mb-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><div className="panel"><span className="meta">Status</span><div className="mt-2"><StatusBadge active={value.is_active} /></div></div><div className="panel"><span className="meta">Coordinates</span><p>{value.latitude && value.longitude ? `${value.latitude}, ${value.longitude}` : 'Not specified'}</p></div><div className="panel"><span className="meta">Created</span><p>{formatDate(value.created_at)}</p></div><div className="panel"><span className="meta">Updated</span><p>{formatDate(value.updated_at)}</p></div></div>{user?.role !== 'VIEWER' ? <button className="button-secondary mb-7" onClick={() => status.mutate(!value.is_active)}>{value.is_active ? 'Deactivate site' : 'Reactivate site'}</button> : null}<h2 className="mb-4 text-xl font-bold">Registered devices</h2>{devices.data?.items.length ? <div className="panel p-0"><table><thead><tr><th>Device</th><th>UID</th><th>Status</th></tr></thead><tbody>{devices.data.items.map((device) => <tr key={device.id}><td><Link className="text-cyan-300" to={`/devices/${device.id}`}>{device.name}</Link></td><td>{device.device_uid}</td><td><StatusBadge status={device.status} /></td></tr>)}</tbody></table></div> : <Empty>No devices are registered at this site yet.</Empty>}</>
}
