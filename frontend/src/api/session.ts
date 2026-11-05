import type { GuestSession } from '../types'

const STORAGE_KEY = 'dormwrapper.session.v1'
export const SESSION_ENDED = 'dormwrapper:session-ended'

function restore(): GuestSession | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null') as GuestSession | null
    return value && typeof value.token === 'string' && typeof value.handle === 'string'
      && Date.parse(value.expires_at) > Date.now() ? value : null
  } catch {
    return null
  }
}

let session = restore()

export function getSession(): GuestSession | null {
  return session
}

export function setSession(value: GuestSession | null): void {
  session = value
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage may be unavailable; this tab can continue using memory.
  }
}

export function endSession(): void {
  setSession(null)
  window.dispatchEvent(new Event(SESSION_ENDED))
}

export function authHeaders(): HeadersInit {
  return session ? { Authorization: `Bearer ${session.token}` } : {}
}
