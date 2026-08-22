/* eslint-disable react-refresh/only-export-components -- UI helpers intentionally colocated */
import type { ConfigurationStatus, DeviceStatus, SensorStatus } from '../lib/types'

export const formatDate = (value: string | null) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Never'

export function StatusBadge({ active, status }: { active?: boolean; status?: DeviceStatus | SensorStatus | ConfigurationStatus }) {
  const text = status ?? (active ? 'ACTIVE' : 'INACTIVE')
  const positive = status === 'ONLINE' || status === 'REGISTERED' || status === 'APPLIED' || (!status && active)
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${positive ? 'bg-emerald-500/15 text-emerald-300' : status === 'ERROR' ? 'bg-red-500/15 text-red-300' : 'bg-amber-500/15 text-amber-300'}`}>{text}</span>
}

export function PageHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-400">AQRESS Pulse</p><h1 className="mt-2 text-3xl font-bold">{title}</h1><p className="mt-2 text-slate-400">{description}</p></div>{action}</div>
}

export function Empty({ children }: { children: React.ReactNode }) { return <div className="panel py-14 text-center text-slate-400">{children}</div> }
export function ErrorNotice({ error }: { error: unknown }) { return <div role="alert" className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error instanceof Error ? error.message : 'Something went wrong.'}</div> }
