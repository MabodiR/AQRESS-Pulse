import type { SensorType } from './types'

export type Configuration = Record<string, unknown>
export type ConfigurationErrors = Record<string, string>

export function configurationDefaults(sensorType?: SensorType): Configuration {
  if (!sensorType) return {}
  return Object.fromEntries(Object.entries(sensorType.configuration_schema.properties)
    .filter(([, field]) => field.default !== undefined)
    .map(([key, field]) => [key, field.default]))
}

export function validateConfiguration(sensorType: SensorType, values: Configuration): ConfigurationErrors {
  const errors: ConfigurationErrors = {}
  const required = new Set(sensorType.configuration_schema.required ?? [])
  Object.entries(sensorType.configuration_schema.properties).forEach(([key, field]) => {
    const value = values[key]
    if (required.has(key) && (value === undefined || value === null || value === '')) errors[key] = 'This field is required.'
    if (typeof value === 'number' && field.minimum !== undefined && value < field.minimum) errors[key] = `Minimum value is ${field.minimum}.`
    if (typeof value === 'number' && field.maximum !== undefined && value > field.maximum) errors[key] = `Maximum value is ${field.maximum}.`
  })
  return errors
}
