import type { Configuration, ConfigurationErrors } from '../lib/configuration'
import type { SensorType } from '../lib/types'

type Props = { sensorType: SensorType; values: Configuration; errors?: ConfigurationErrors; onChange: (values: Configuration) => void; disabled?: boolean }

export function DynamicConfigurationForm({ sensorType, values, errors = {}, onChange, disabled = false }: Props) {
  const required = new Set(sensorType.configuration_schema.required ?? [])
  const setValue = (key: string, value: unknown) => onChange({ ...values, [key]: value })
  return <div className="grid gap-5 sm:grid-cols-2">{Object.entries(sensorType.configuration_schema.properties).map(([key, field]) => {
    const label = field.title || key.replace(/_/g, ' ')
    const common = { id: `configuration-${key}`, disabled, required: required.has(key), 'aria-describedby': errors[key] ? `configuration-${key}-error` : undefined }
    let input: React.ReactNode
    if (field.enum) input = <select className="input" value={String(values[key] ?? '')} onChange={(event) => setValue(key, event.target.value)} {...common}><option value="">Select…</option>{field.enum.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select>
    else if (field.type === 'boolean') input = <select className="input" value={values[key] === undefined ? '' : String(values[key])} onChange={(event) => setValue(key, event.target.value === '' ? undefined : event.target.value === 'true')} {...common}><option value="">Select…</option><option value="true">True</option><option value="false">False</option></select>
    else if (field.type === 'integer' || field.type === 'number') input = <input className="input" type="number" step={field.type === 'integer' ? 1 : 'any'} min={field.minimum} max={field.maximum} value={values[key] === undefined ? '' : String(values[key])} onChange={(event) => setValue(key, event.target.value === '' ? undefined : Number(event.target.value))} {...common} />
    else input = <input className="input" type="text" value={String(values[key] ?? '')} onChange={(event) => setValue(key, event.target.value)} {...common} />
    return <label className="field-label" htmlFor={`configuration-${key}`} key={key}>{label}{required.has(key) ? <span className="text-cyan-400"> *</span> : null}{input}{field.description ? <span className="mt-1 block text-xs font-normal text-slate-500">{field.description}</span> : null}<span id={`configuration-${key}-error`} className="field-error">{errors[key]}</span></label>
  })}</div>
}
