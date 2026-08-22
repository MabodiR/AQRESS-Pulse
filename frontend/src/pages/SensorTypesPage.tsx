import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorNotice, PageHeader, StatusBadge } from '../components/Ui'
import { api } from '../lib/api'
import type { InterfaceType, Paginated, SensorType } from '../lib/types'

export function SensorTypesPage() {
  const { user } = useAuth(); const [search, setSearch] = useState(''); const [interfaceType, setInterfaceType] = useState<InterfaceType | ''>(''); const [page, setPage] = useState(1)
  const catalogue = useQuery({ queryKey: ['sensor-types', search, interfaceType, page], queryFn: () => {
    const params = new URLSearchParams({ page: String(page), page_size: '25' }); if (search) params.set('search', search); if (interfaceType) params.set('interface_type', interfaceType)
    return api<Paginated<SensorType>>(`/sensor-types?${params}`)
  } })
  return <><PageHeader title="Sensor Types" description="Reusable sensor definitions, measurements, and configuration contracts." action={user?.role === 'ADMIN' ? <Link className="button-primary" to="/sensor-types/new">+ Add Sensor Type</Link> : undefined} /><div className="mb-5 grid gap-3 md:grid-cols-2"><input aria-label="Search Sensor Types" className="input" placeholder="Search name, code, manufacturer, or model…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /><select aria-label="Filter by interface" className="input" value={interfaceType} onChange={(event) => { setInterfaceType(event.target.value as InterfaceType | ''); setPage(1) }}><option value="">All interfaces</option>{['GPIO', 'ADC', 'I2C', 'ONE_WIRE'].map((value) => <option key={value}>{value}</option>)}</select></div>{catalogue.error ? <ErrorNotice error={catalogue.error} /> : null}{catalogue.isPending ? <div className="panel">Loading Sensor Types…</div> : catalogue.data?.items.length ? <div className="panel overflow-x-auto p-0"><table><thead><tr><th>Name</th><th>Code</th><th>Manufacturer</th><th>Interface</th><th>Measurements</th><th>Status</th></tr></thead><tbody>{catalogue.data.items.map((item) => <tr key={item.id}><td><Link className="font-semibold text-cyan-300" to={`/sensor-types/${item.id}`}>{item.name}</Link></td><td>{item.code}</td><td>{item.manufacturer || '—'}</td><td>{item.interface_type}</td><td>{item.measurements.length}</td><td><StatusBadge active={item.is_active} /></td></tr>)}</tbody></table></div> : <Empty>No Sensor Types match the current filters.</Empty>}<div className="mt-5 flex justify-between text-sm text-slate-400"><span>{catalogue.data?.pagination.total_items ?? 0} Sensor Types</span><div className="flex gap-2"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><button className="button-secondary" disabled={!catalogue.data || page >= catalogue.data.pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></div></>
}
