import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorNotice, PageHeader, StatusBadge, formatDate } from '../components/Ui'
import { api } from '../lib/api'
import type { Device, Paginated, Sensor } from '../lib/types'

export function DeviceDetailPage() {
  const { deviceId } = useParams(); const { user } = useAuth(); const client = useQueryClient()
  const query = useQuery({ queryKey: ['device', deviceId], queryFn: () => api<Device>(`/devices/${deviceId}`) })
  const sensors = useQuery({ queryKey: ['device-sensors', deviceId], queryFn: () => api<Paginated<Sensor>>(`/devices/${deviceId}/sensors?page_size=100`) })
  const status = useMutation({ mutationFn: (active: boolean) => api<Device>(`/devices/${deviceId}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) }), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['device', deviceId] }) } })
  if (query.isPending) return <div className="panel">Loading device…</div>
  if (query.error || !query.data) return <ErrorNotice error={query.error} />
  const device = query.data
  const details = [['Device UID', device.device_uid], ['Site', device.site.name], ['Device type', device.device_type], ['Manufacturer', device.manufacturer || '—'], ['Model', device.model || '—'], ['Firmware', device.firmware_version || '—'], ['Connection', device.connection_type], ['Last seen', formatDate(device.last_seen_at)], ['Created', formatDate(device.created_at)], ['Updated', formatDate(device.updated_at)]]
  return <><PageHeader title={device.name} description={device.description || 'No description provided.'} action={user?.role !== 'VIEWER' ? <Link className="button-primary" to={`/devices/${device.id}/edit`}>Edit Device</Link> : undefined} /><div className="mb-6 flex items-center gap-3"><StatusBadge status={device.status} />{user?.role !== 'VIEWER' ? <button className="button-secondary" onClick={() => status.mutate(!device.is_active)}>{device.is_active ? 'Disable device' : 'Enable device'}</button> : null}</div><dl className="panel grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">{details.map(([label, value]) => <div key={label}><dt className="meta">{label}</dt><dd className="mt-1 font-medium">{value}</dd></div>)}</dl><section className="panel mt-7"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Sensors</h2><p className="mt-1 text-sm text-slate-400">Physical Sensors attached to this Device.</p></div>{user?.role !== 'VIEWER' && device.is_active ? <Link className="button-primary" to={`/devices/${device.id}/sensors/new`}>+ Add Sensor</Link> : null}</div>{sensors.error ? <div className="mt-5"><ErrorNotice error={sensors.error} /></div> : null}{sensors.isPending ? <p className="mt-5 text-slate-400">Loading Sensors…</p> : sensors.data?.items.length ? <div className="mt-5 overflow-x-auto"><table><thead><tr><th>Sensor</th><th>UID</th><th>Type</th><th>Channels</th><th>Status</th><th>Configuration</th></tr></thead><tbody>{sensors.data.items.map((sensor) => <tr key={sensor.id}><td><Link className="font-semibold text-cyan-300" to={`/sensors/${sensor.id}`}>{sensor.name}</Link></td><td>{sensor.sensor_uid}</td><td>{sensor.sensor_type.code}</td><td>{sensor.channels.length}</td><td><StatusBadge status={sensor.status} /></td><td><StatusBadge status={sensor.current_configuration.status} /></td></tr>)}</tbody></table></div> : <div className="mt-5"><Empty>No Sensors are attached to this Device yet.</Empty></div>}</section></>
}
