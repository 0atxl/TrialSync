import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

import { apiRequest, type AuthResponse, type User } from '../api/client'

type AuthContextValue = {
  token: string | null
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, displayName: string, password: string) => Promise<void>
  logout: () => void
}

const TOKEN_KEY = 'trialsync_access_token'
const USER_KEY = 'trialsync_user'
const AuthContext = createContext<AuthContextValue | null>(null)

function storedUser(): User | null {
  try {
    const value = sessionStorage.getItem(USER_KEY)
    return value ? (JSON.parse(value) as User) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(storedUser)

  const save = (response: AuthResponse) => {
    sessionStorage.setItem(TOKEN_KEY, response.access_token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(response.user))
    setToken(response.access_token)
    setUser(response.user)
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      login: async (email, password) => {
        save(
          await apiRequest<AuthResponse>('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
          }),
        )
      },
      register: async (email, displayName, password) => {
        save(
          await apiRequest<AuthResponse>('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, display_name: displayName, password }),
          }),
        )
      },
      logout: () => {
        sessionStorage.removeItem(TOKEN_KEY)
        sessionStorage.removeItem(USER_KEY)
        setToken(null)
        setUser(null)
      },
    }),
    [token, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Context hooks intentionally share this module with their provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
