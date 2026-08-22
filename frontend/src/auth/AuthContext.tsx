/* eslint-disable react-refresh/only-export-components -- provider and hook share one context */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { authApi, hasRefreshToken, setTokens } from '../lib/api'
import type { User } from '../lib/types'

type AuthValue = { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(hasRefreshToken())

  useEffect(() => {
    if (!hasRefreshToken()) return
    authApi.me<User>().then(setUser).catch(() => setTokens(null)).finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setTokens(await authApi.login(email, password))
    setUser(await authApi.me<User>())
  }, [])
  const logout = useCallback(async () => { await authApi.logout(); setUser(null) }, [])
  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
