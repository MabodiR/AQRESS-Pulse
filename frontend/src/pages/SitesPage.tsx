import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorNotice, PageHeader, StatusBadge, formatDate } from '../components/Ui'
import { api } from '../lib/api'
import type { Paginated, Site } from '../lib/types'

export function SitesPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery({ queryKey: ['sites', search, page], queryFn: () => api<Paginated<Site>>(`/sites?page=${page}&page_size=25&search=${encodeURIComponent(search)}`) })
  return <><PageHeader title="Sites" description="Manage every physical location in your IoT estate." action={user?.role !== 'VIEWER' ? <Link className="button-primary" to="/sites/new">+ Add Site</Link> : undefined} /><div className="mb-5"><input aria-label="Search sites" className="input max-w-md" placeholder="Search sites…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></div>{query.error ? <ErrorNotice error={query.error} /> : null}{query.isPending ? <div className="panel">Loading sites…</div> : query.data?.items.length ? <div className="panel overflow-x-auto p-0"><table><thead><tr><th>Site name</th><th>Description</th><th>Status</th><th>Created</th></tr></thead><tbody>{query.data.items.map((site) => <tr key={site.id}><td><Link className="font-semibold text-cyan-300 hover:underline" to={`/sites/${site.id}`}>{site.name}</Link></td><td>{site.description || '—'}</td><td><StatusBadge active={site.is_active} /></td><td>{formatDate(site.created_at)}</td></tr>)}</tbody></table></div> : <Empty>No sites found. Add your first site to begin.</Empty>}<div className="mt-5 flex items-center justify-between text-sm text-slate-400"><span>{query.data?.pagination.total_items ?? 0} sites</span><div className="flex gap-2"><button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><button className="button-secondary" disabled={!query.data || page >= query.data.pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></div></>
}
