import type { ApiErrorBody, TokenPair } from './types'

const API_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
let accessToken: string | null = null
let refreshToken: string | null = localStorage.getItem('aqress_refresh_token')
let refreshPromise: Promise<boolean> | null = null

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message) }
}

export function setTokens(tokens: TokenPair | null) {
  accessToken = tokens?.access_token ?? null
  refreshToken = tokens?.refresh_token ?? null
  if (refreshToken) localStorage.setItem('aqress_refresh_token', refreshToken)
  else localStorage.removeItem('aqress_refresh_token')
}

export const hasRefreshToken = () => Boolean(refreshToken)

async function refreshAccess(): Promise<boolean> {
  if (!refreshToken) return false
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_URL}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshToken }) })
      .then(async (response) => {
        if (!response.ok) { setTokens(null); return false }
        setTokens(await response.json() as TokenPair)
        return true
      })
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const response = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (response.status === 401 && retry && await refreshAccess()) return api<T>(path, init, false)
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as ApiErrorBody
    throw new ApiError(response.status, body.error?.code ?? 'REQUEST_FAILED', body.error?.message ?? 'Request failed.')
  }
  return response.json() as Promise<T>
}

export const authApi = {
  login: (email: string, password: string) => api<TokenPair>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }, false),
  me: <T,>() => api<T>('/auth/me'),
  logout: async () => {
    if (refreshToken) await api('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }).catch(() => undefined)
    setTokens(null)
  },
}
