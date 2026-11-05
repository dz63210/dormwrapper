import { useState } from 'react'
import type { FormEvent } from 'react'
import { login } from '../api/client'
import { useUser } from '../context/UserContext'

export default function LocalLoginPage() {
  const { signIn } = useUser()
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      signIn(await login(username.trim()))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start your session.')
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-neutral-50 px-4 font-montreal">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm ring-1 ring-neutral-200">
        <h1 className="text-2xl font-bold">DormWrapper</h1>
        <p className="my-4 text-sm text-neutral-600">Choose a new username to start a local demo session.</p>
        <label htmlFor="username" className="block text-sm font-medium">Username</label>
        <input id="username" required pattern="[A-Za-z0-9_]{3,20}" maxLength={20}
          autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value)}
          aria-describedby="username-hint" className="mt-1 w-full rounded-lg border px-3 py-2" />
        <p id="username-hint" className="mt-1 text-xs text-neutral-500">Use 3–20 letters, numbers, or underscores.</p>
        {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
        <button disabled={pending} className="mt-4 w-full rounded-lg bg-neutral-900 py-2 text-white disabled:opacity-50">
          {pending ? 'Starting…' : 'Continue'}
        </button>
      </form>
    </main>
  )
}
