import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { DynamicConfigurationForm } from '../components/DynamicConfigurationForm'
import { ErrorNotice, PageHeader } from '../components/Ui'
import { validateConfiguration, type Configuration, type ConfigurationErrors } from '../lib/configuration'
import { api } from '../lib/api'
import type { Sensor, SensorConfiguration, SensorType } from '../lib/types'

function ConfigurationEditor({ sensor, sensorType }: { sensor: Sensor; sensorType: SensorType }) {
  const navigate = useNavigate(); const queryClient = useQueryClient(); const [values, setValues] = useState<Configuration>(sensor.current_configuration.configuration); const [errors, setErrors] = useState<ConfigurationErrors>({})
  const mutation = useMutation({ mutationFn: () => api<SensorConfiguration>(`/sensors/${sensor.id}/configuration`, { method: 'PUT', body: JSON.stringify({ configuration: values }) }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['sensor', sensor.id] }); await queryClient.invalidateQueries({ queryKey: ['sensor-configurations', sensor.id] }); navigate(`/sensors/${sensor.id}`) } })
  const submit = () => { const result = validateConfiguration(sensorType, values); setErrors(result); if (!Object.keys(result).length) mutation.mutate() }
  return <>{mutation.error ? <ErrorNotice error={mutation.error} /> : null}<section className="panel max-w-3xl"><p className="mb-5 text-sm text-slate-400">Saving creates version {sensor.current_configuration.config_version + 1}; version {sensor.current_configuration.config_version} remains immutable in history.</p><DynamicConfigurationForm sensorType={sensorType} values={values} errors={errors} onChange={setValues} /><div className="mt-7 flex gap-3 border-t border-slate-800 pt-5"><button className="button-primary" disabled={mutation.isPending} onClick={submit}>{mutation.isPending ? 'Creating version…' : 'Save New Version'}</button><Link className="button-secondary" to={`/sensors/${sensor.id}`}>Cancel</Link></div></section></>
}

export function SensorConfigurationEditPage() {
  const { sensorId } = useParams(); const sensor = useQuery({ queryKey: ['sensor', sensorId], queryFn: () => api<Sensor>(`/sensors/${sensorId}`) }); const typeId = sensor.data?.sensor_type.id; const sensorType = useQuery({ queryKey: ['sensor-type', typeId], queryFn: () => api<SensorType>(`/sensor-types/${typeId}`), enabled: Boolean(typeId) })
  if (sensor.isPending || sensorType.isPending) return <div className="panel">Loading configuration…</div>
  if (sensor.error || sensorType.error || !sensor.data || !sensorType.data) return <ErrorNotice error={sensor.error ?? sensorType.error} />
  return <><PageHeader title="Edit Configuration" description={`${sensor.data.name} · schema-driven configuration versioning.`} /><ConfigurationEditor sensor={sensor.data} sensorType={sensorType.data} /></>
}
