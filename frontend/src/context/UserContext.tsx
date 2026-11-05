import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { User } from '../types'
import type { GuestSession } from '../types'
import { currentUser, logout } from '../api/client'
import { getSession, setSession, endSession, SESSION_ENDED } from '../api/session'

interface UserContextValue {
  user: User | null
  signIn: (session: GuestSession) => void
  signOut: () => Promise<void>
}

const UserContext = createContext<UserContextValue | null>(null)

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getSession)

  useEffect(() => {
    const ended = () => setUser(null)
    window.addEventListener(SESSION_ENDED, ended)
    if (getSession()) void currentUser().then((verifiedUser) => {
      const session = getSession()
      if (session && session.id === verifiedUser.id) {
        setSession({ ...session, ...verifiedUser })
        setUser(verifiedUser)
      }
    }).catch(() => {
      // A network failure keeps the session available for a subsequent retry;
      // a 401 is handled centrally and clears it.
    })
    return () => window.removeEventListener(SESSION_ENDED, ended)
  }, [])

  useEffect(() => {
    const session = getSession()
    if (!session || !user) return
    const timer = window.setTimeout(endSession, Math.max(0, Date.parse(session.expires_at) - Date.now()))
    return () => window.clearTimeout(timer)
  }, [user])

  const value = useMemo<UserContextValue>(
    () => ({ user,
      signIn: (session: GuestSession) => { setSession(session); setUser(session) },
      signOut: async () => {
        await logout()
        endSession()
      },
    }),
    [user],
  )

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useUser(): UserContextValue {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error('useUser must be used within a UserProvider')
  return ctx
}
