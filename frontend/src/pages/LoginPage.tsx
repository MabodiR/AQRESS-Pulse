import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from '../auth/AuthContext'

const schema = z.object({ email: z.string().email(), password: z.string().min(1, 'Password is required') })
type Values = z.infer<typeof schema>

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: 'admin@aqress.dev', password: '' } })
  if (user) return <Navigate to="/sites" replace />
  const submit = async (values: Values) => {
    setError('')
    try { await login(values.email, values.password); navigate((location.state as { from?: string } | null)?.from ?? '/sites', { replace: true }) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Login failed.') }
  }
  return <main className="grid min-h-screen place-items-center bg-slate-950 p-5 text-slate-100"><section className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl"><p className="font-bold tracking-[0.24em] text-cyan-400">AQRESS</p><h1 className="mt-3 text-4xl font-bold">Welcome to Pulse</h1><p className="mt-3 text-slate-400">Sign in to manage your sites and connected devices.</p><form className="mt-8 space-y-5" onSubmit={handleSubmit(submit)}><label className="field-label">Email<input className="input" type="email" autoComplete="email" {...register('email')} /><span className="field-error">{errors.email?.message}</span></label><label className="field-label">Password<input className="input" type="password" autoComplete="current-password" {...register('password')} /><span className="field-error">{errors.password?.message}</span></label>{error ? <p role="alert" className="text-sm text-red-300">{error}</p> : null}<button className="button-primary w-full" disabled={isSubmitting}>{isSubmitting ? 'Signing in…' : 'Sign in'}</button></form></section></main>
}
