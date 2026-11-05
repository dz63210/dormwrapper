import { Link, Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { useUser } from './context/UserContext'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import DesignPage from './pages/DesignPage'

function RequireUser({ children }: { children: ReactNode }) {
  const { user } = useUser()
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function TopBar() {
  const { user, signOut } = useUser()
  const [error, setError] = useState('')
  if (!user) return null
  return (
    <div className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-2 text-sm">
        <Link to="/" className="font-semibold text-neutral-900">
          DormWrapper
        </Link>
        <span className="flex items-center gap-3 text-neutral-500">
          @{user.handle}
          {!user.email && <Link to="/login" className="underline">Verify email to keep designs</Link>}
          <button
            type="button"
            onClick={() => { void signOut().catch(() => setError('Could not sign out. Please try again.')) }}
            className="rounded-md border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-50"
          >
            Sign out
          </button>
          {error && <span role="alert" className="text-red-600">{error}</span>}
        </span>
      </div>
    </div>
  )
}

export default function App() {
  const { user } = useUser()

  return (
    <>
      <TopBar />
      <Routes>
        <Route path="/login" element={user?.email ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route
          path="/"
          element={
            <RequireUser>
              <HomePage />
            </RequireUser>
          }
        />
        <Route
          path="/new"
          element={
            <RequireUser>
              <DesignPage />
            </RequireUser>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
