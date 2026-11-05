import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { requestEmailCode, verifyEmailCode } from '../api/client'
import { useUser } from '../context/UserContext'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [sentEmail, setSentEmail] = useState('')
  const [code, setCode] = useState('')
  const [cooldown, setCooldown] = useState(0)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { signIn, user } = useUser()
  const navigate = useNavigate()

  const trimmed = email.trim().toLowerCase()
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)
  const validCode = /^[0-9]{6}$/.test(code)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = window.setTimeout(() => setCooldown(cooldown - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [cooldown])

  async function sendCode() {
    setError('')
    setSubmitting(true)
    try {
      await requestEmailCode(sentEmail || trimmed)
      setSentEmail(sentEmail || trimmed)
      setCode('')
      setCooldown(60)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send a code. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!sentEmail) {
      if (valid) await sendCode()
      else setError('Enter a valid email address.')
      return
    }
    if (!validCode) {
      setError('Enter the six-digit code from your email.')
      return
    }
    setSubmitting(true)
    try {
      const session = await verifyEmailCode(sentEmail, code)
      signIn(session)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden font-montreal md:grid-cols-2">
      <div className="hidden flex-col items-center justify-center bg-[#f2f2f0] px-16 md:flex">
        <div className="max-w-lg">
          <p className="mb-6 text-xl font-bold tracking-tight text-brand-blue">DormWrapper</p>
          <h1 className="mb-5 text-6xl font-bold leading-[0.98] tracking-tight text-neutral-900 text-balance lg:text-7xl">
            Customise your dorm.
          </h1>
          <p className="max-w-sm text-lg leading-relaxed text-neutral-500">
            Match your room, your budget, and your style — see it before you buy it.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center bg-neutral-50 px-4">
        <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm ring-1 ring-neutral-200">
          <h2 className="text-xl font-bold text-neutral-900">DormWrapper</h2>
          <p className="mt-1 text-sm text-neutral-500">
            {sentEmail ? `Enter the code sent to ${sentEmail}. Check your spam folder too.`
              : 'Sign in or create an account with your email. No password needed.'}
          </p>

          <form onSubmit={handleSubmit} className="mt-6" noValidate>
            <label htmlFor={sentEmail ? 'code' : 'email'} className="block text-sm font-medium text-neutral-700">
              {sentEmail ? 'Verification code' : 'Email address'}
            </label>
            <input
              key={sentEmail ? 'code' : 'email'}
              id={sentEmail ? 'code' : 'email'}
              name={sentEmail ? 'code' : 'email'}
              type={sentEmail ? 'text' : 'email'}
              inputMode={sentEmail ? 'numeric' : 'email'}
              maxLength={sentEmail ? 6 : 254}
              autoComplete={sentEmail ? 'one-time-code' : 'email'}
              autoFocus
              placeholder={sentEmail ? '123456' : 'you@example.com'}
              value={sentEmail ? code : email}
              onChange={(e) => sentEmail ? setCode(e.target.value.replace(/\D/g, '')) : setEmail(e.target.value)}
              aria-invalid={Boolean(error)}
              aria-describedby="login-hint"
              disabled={submitting}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
                error
                  ? 'border-red-400 focus:border-red-500'
                  : 'border-neutral-200 focus:border-neutral-500'
              }`}
            />
            <p id="login-hint" className="mt-1 text-xs text-neutral-500">
              {sentEmail ? 'Codes can only be used once.' : 'We will email you a one-time sign-in code.'}
            </p>

            {error && (
              <p role="alert" className="mt-2 text-xs text-red-600">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting || (sentEmail ? !validCode : !valid)}
              className="mt-4 w-full rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {submitting ? 'Please wait…' : sentEmail ? 'Verify and sign in' : 'Send sign-in code'}
            </button>
          </form>

          {sentEmail && <div className="mt-3 flex justify-between text-xs">
            <button type="button" onClick={() => { void sendCode() }} disabled={submitting || cooldown > 0}
              className="underline disabled:opacity-50">
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
            </button>
            <button type="button" disabled={submitting}
              onClick={() => { setSentEmail(''); setCode(''); setError('') }} className="underline">
              Change email
            </button>
          </div>}

          <p className="mt-5 text-center text-xs text-neutral-400">
            {user ? 'Verify your email to keep your current designs and access them on future visits.'
              : 'Your saved designs will be here when you sign in again with the same email.'}
          </p>
        </div>
      </div>
    </div>
  )
}
