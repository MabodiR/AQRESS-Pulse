import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { ErrorNotice, PageHeader } from '../components/Ui'
import { api } from '../lib/api'
import type { Site } from '../lib/types'

const optionalCoordinate = (min: number, max: number) => z.union([z.literal(''), z.coerce.number().min(min).max(max)])
const schema = z.object({ name: z.string().min(1, 'Name is required').max(200), description: z.string(), latitude: optionalCoordinate(-90, 90), longitude: optionalCoordinate(-180, 180) })
type Values = z.infer<typeof schema>

export function SiteFormPage() {
  const { siteId } = useParams(); const editing = Boolean(siteId); const navigate = useNavigate(); const queryClient = useQueryClient()
  const site = useQuery({ queryKey: ['site', siteId], queryFn: () => api<Site>(`/sites/${siteId}`), enabled: editing })
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), values: site.data ? { name: site.data.name, description: site.data.description ?? '', latitude: site.data.latitude === null ? '' : Number(site.data.latitude), longitude: site.data.longitude === null ? '' : Number(site.data.longitude) } : undefined, defaultValues: { name: '', description: '', latitude: '', longitude: '' } })
  const mutation = useMutation({ mutationFn: (values: Values) => api<Site>(editing ? `/sites/${siteId}` : '/sites', { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ ...values, latitude: values.latitude === '' ? null : values.latitude, longitude: values.longitude === '' ? null : values.longitude }) }), onSuccess: async (result) => { await queryClient.invalidateQueries({ queryKey: ['sites'] }); navigate(`/sites/${result.id}`) } })
  return <><PageHeader title={editing ? 'Edit site' : 'Add site'} description="Capture the location and optional geographic coordinates." />{mutation.error ? <ErrorNotice error={mutation.error} /> : null}<form className="panel max-w-2xl space-y-5" onSubmit={handleSubmit((values) => mutation.mutate(values))}><label className="field-label">Site name<input className="input" {...register('name')} /><span className="field-error">{errors.name?.message}</span></label><label className="field-label">Description<textarea className="input min-h-28" {...register('description')} /></label><div className="grid gap-5 sm:grid-cols-2"><label className="field-label">Latitude<input className="input" type="number" step="any" {...register('latitude')} /><span className="field-error">{errors.latitude?.message}</span></label><label className="field-label">Longitude<input className="input" type="number" step="any" {...register('longitude')} /><span className="field-error">{errors.longitude?.message}</span></label></div><div className="flex gap-3"><button className="button-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save site'}</button><Link className="button-secondary" to={editing ? `/sites/${siteId}` : '/sites'} onClick={() => reset()}>Cancel</Link></div></form></>
}
