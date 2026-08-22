import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { ErrorNotice, PageHeader } from '../components/Ui'
import { api } from '../lib/api'
import type { InterfaceType, SensorType } from '../lib/types'

const DEFAULT_SCHEMA = JSON.stringify({ type: 'object', properties: { sample_interval_seconds: { type: 'integer', title: 'Sampling Interval', minimum: 1, default: 10 } }, required: ['sample_interval_seconds'], additionalProperties: false }, null, 2)
const schema = z.object({ name: z.string().min(1), code: z.string().min(1), manufacturer: z.string(), model: z.string(), interface_type: z.enum(['GPIO', 'ADC', 'I2C', 'ONE_WIRE']), driver_key: z.string().min(1), configuration_schema: z.string().refine((value) => { try { const parsed = JSON.parse(value) as unknown; return Boolean(parsed && typeof parsed === 'object') } catch { return false } }, 'Enter valid JSON') })
type Values = z.infer<typeof schema>

export function SensorTypeFormPage() {
  const { sensorTypeId } = useParams(); const editing = Boolean(sensorTypeId); const navigate = useNavigate(); const client = useQueryClient()
  const query = useQuery({ queryKey: ['sensor-type', sensorTypeId], queryFn: () => api<SensorType>(`/sensor-types/${sensorTypeId}`), enabled: editing })
  const blank = { name: '', code: '', manufacturer: '', model: '', interface_type: 'GPIO' as InterfaceType, driver_key: '', configuration_schema: DEFAULT_SCHEMA }
  const { register, handleSubmit, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), values: query.data ? { name: query.data.name, code: query.data.code, manufacturer: query.data.manufacturer ?? '', model: query.data.model ?? '', interface_type: query.data.interface_type, driver_key: query.data.driver_key, configuration_schema: JSON.stringify(query.data.configuration_schema, null, 2) } : undefined, defaultValues: blank })
  const mutation = useMutation({ mutationFn: (values: Values) => api<SensorType>(editing ? `/sensor-types/${sensorTypeId}` : '/sensor-types', { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ ...values, manufacturer: values.manufacturer || null, model: values.model || null, configuration_schema: JSON.parse(values.configuration_schema) as unknown }) }), onSuccess: async (item) => { await client.invalidateQueries({ queryKey: ['sensor-types'] }); navigate(`/sensor-types/${item.id}`) } })
  return <><PageHeader title={editing ? 'Edit Sensor Type' : 'Add Sensor Type'} description="Define a stable integration identity and JSON Schema configuration contract." />{mutation.error ? <ErrorNotice error={mutation.error} /> : null}<form className="panel max-w-3xl space-y-5" onSubmit={handleSubmit((values) => mutation.mutate(values))}><div className="grid gap-5 sm:grid-cols-2"><label className="field-label">Name<input className="input" {...register('name')} /></label><label className="field-label">Code<input className="input" placeholder="BME280" {...register('code')} /></label><label className="field-label">Manufacturer<input className="input" {...register('manufacturer')} /></label><label className="field-label">Model<input className="input" {...register('model')} /></label><label className="field-label">Interface<select className="input" {...register('interface_type')}>{['GPIO', 'ADC', 'I2C', 'ONE_WIRE'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="field-label">Driver key<input className="input" placeholder="bme280" {...register('driver_key')} /></label></div><label className="field-label">Configuration schema<textarea className="input min-h-80 font-mono text-sm" spellCheck={false} {...register('configuration_schema')} /><span className="field-error">{errors.configuration_schema?.message}</span></label><div className="flex gap-3"><button className="button-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save Sensor Type'}</button><Link className="button-secondary" to={editing ? `/sensor-types/${sensorTypeId}` : '/sensor-types'}>Cancel</Link></div></form></>
}
