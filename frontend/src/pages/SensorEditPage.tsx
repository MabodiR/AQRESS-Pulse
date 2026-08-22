import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ErrorNotice, PageHeader } from '../components/Ui'
import { api } from '../lib/api'
import type { Sensor } from '../lib/types'

function SensorEditForm({ sensor }: { sensor: Sensor }) {
  const navigate = useNavigate(); const queryClient = useQueryClient(); const [values, setValues] = useState({ name: sensor.name, description: sensor.description ?? '', enabled: sensor.enabled })
  const mutation = useMutation({ mutationFn: () => api<Sensor>(`/sensors/${sensor.id}`, { method: 'PUT', body: JSON.stringify({ ...values, description: values.description || null }) }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['sensor', sensor.id] }); navigate(`/sensors/${sensor.id}`) } })
  return <>{mutation.error ? <ErrorNotice error={mutation.error} /> : null}<form className="panel max-w-2xl space-y-5" onSubmit={(event) => { event.preventDefault(); mutation.mutate() }}><label className="field-label">Name<input required className="input" value={values.name} onChange={(event) => setValues((value) => ({ ...value, name: event.target.value }))} /></label><label className="field-label">Description<textarea className="input min-h-32" value={values.description} onChange={(event) => setValues((value) => ({ ...value, description: event.target.value }))} /></label><label className="flex items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={values.enabled} onChange={(event) => setValues((value) => ({ ...value, enabled: event.target.checked }))} /> Sensor enabled</label><p className="text-sm text-slate-500">UID, Device, and Sensor Type are immutable after registration.</p><div className="flex gap-3"><button className="button-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save Sensor'}</button><Link className="button-secondary" to={`/sensors/${sensor.id}`}>Cancel</Link></div></form></>
}

export function SensorEditPage() {
  const { sensorId } = useParams(); const query = useQuery({ queryKey: ['sensor', sensorId], queryFn: () => api<Sensor>(`/sensors/${sensorId}`) })
  if (query.isPending) return <div className="panel">Loading Sensor…</div>
  if (query.error || !query.data) return <ErrorNotice error={query.error} />
  return <><PageHeader title="Edit Sensor" description={`${query.data.sensor_uid} · identity and attachment remain unchanged.`} /><SensorEditForm sensor={query.data} /></>
}
