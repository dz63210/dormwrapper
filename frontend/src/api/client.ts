import type { DecorStyle, SavedDesign, Submission, Suggestion, User, GuestSession } from '../types'
import { authHeaders, endSession } from './session'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    endSession()
    throw new Error('Your session ended. Sign in with your email to continue.')
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

/**
 * Create a new guest account. Existing handles cannot authenticate an account.
 */
export async function login(handleValue: string): Promise<GuestSession> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ handle: handleValue }),
    })
  } catch {
    throw new Error("Can't reach the server. Is the backend running?")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = (body as { detail?: unknown } | null)?.detail
    const message = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg).join(' ')
      : typeof detail === 'string'
        ? detail
        : 'Login failed. Please try again.'
    throw new Error(message)
  }
  return res.json() as Promise<GuestSession>
}

export async function currentUser(): Promise<User> {
  return handle<User>(await fetch(`${API_BASE_URL}/api/me`, { headers: authHeaders(), cache: 'no-store' }))
}

async function emailAuthRequest<T>(path: string, payload: object, authenticated = false): Promise<T> {
  const res = await fetch(`${API_BASE_URL}/api/auth/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(authenticated ? authHeaders() : {}) },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    if (res.status === 401) endSession()
    const body = await res.json().catch(() => null)
    const detail = body?.detail
    throw new Error(typeof detail === 'string' ? detail : 'Unable to sign in. Please check your email and try again.')
  }
  return res.json() as Promise<T>
}

export function requestEmailCode(email: string): Promise<{ message: string }> {
  return emailAuthRequest('request-code', { email })
}

export function verifyEmailCode(email: string, code: string): Promise<GuestSession> {
  return emailAuthRequest('verify-code', { email, code }, true)
}

export async function logout(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/logout`, { method: 'POST', headers: authHeaders() })
  if (res.status !== 204) await handle<never>(res)
}

export async function createSubmission(
  params: {
    image: File
    budget: number
    style: DecorStyle
    notes?: string
  },
): Promise<Submission> {
  const form = new FormData()
  form.append('image', params.image)
  form.append('budget', String(params.budget))
  form.append('style', params.style)
  form.append('notes', params.notes ?? '')

  const res = await fetch(`${API_BASE_URL}/api/submissions`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  return handle<Submission>(res)
}

export async function generateSuggestion(submissionId: number): Promise<Suggestion> {
  const res = await fetch(`${API_BASE_URL}/api/generate/${submissionId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return handle<Suggestion>(res)
}

/** The current user's saved designs, newest first. */
export async function listSavedDesigns(): Promise<SavedDesign[]> {
  const res = await fetch(`${API_BASE_URL}/api/designs`, {
    headers: authHeaders(),
  })
  return handle<SavedDesign[]>(res)
}

/** Mark a generated design as saved so it shows up on the home page. */
export async function saveDesign(submissionId: number): Promise<SavedDesign> {
  const res = await fetch(`${API_BASE_URL}/api/designs/${submissionId}/save`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return handle<SavedDesign>(res)
}

/** Remove a design from the saved list. */
export async function unsaveDesign(submissionId: number): Promise<SavedDesign> {
  const res = await fetch(`${API_BASE_URL}/api/designs/${submissionId}/save`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return handle<SavedDesign>(res)
}

export async function fetchPrivateImage(path: string, signal: AbortSignal): Promise<Blob> {
  // Only send credentials to our API and its known media route.
  if (!/^\/api\/media\/\d+\/(room|generated)$/.test(path)) throw new Error('Invalid image path')
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: authHeaders(), signal, cache: 'no-store', redirect: 'error',
  })
  if (!res.ok) await handle<never>(res)
  return res.blob()
}

/** CatalogueItem.image_url is already a server-relative path (e.g. /catalogue-images/123.jpg). */
export function catalogueImageUrl(path: string): string {
  if (/^https:\/\//i.test(path)) return path
  if (!path.startsWith('/catalogue-images/')) return ''
  return `${API_BASE_URL}${path}`
}
