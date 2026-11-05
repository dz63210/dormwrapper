"""Supabase owns OTP generation, delivery, expiry, and single-use verification."""
from uuid import UUID
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.config import settings


def provider_url() -> str:
    base = settings.supabase_url.rstrip('/')
    parsed = urlsplit(base)
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.path
            or parsed.query or parsed.fragment or not settings.supabase_publishable_key):
        raise HTTPException(503, 'Email sign-in is not configured yet. Please try again later.')
    return base + '/auth/v1'


def provider_client() -> httpx.Client:
    return httpx.Client(timeout=10.0, follow_redirects=False)


def provider_request(path: str, payload: dict, *, verification: bool = False) -> dict:
    url = provider_url() + path
    try:
        with provider_client() as client:
            result = client.post(url, headers={'apikey': settings.supabase_publishable_key}, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(503, 'Email sign-in is temporarily unavailable. Please try again.') from exc
    if result.status_code == 429:
        raise HTTPException(429, 'Please wait before trying again.', headers={'Retry-After': '60'})
    if verification and result.status_code in {400, 401, 403, 422}:
        raise HTTPException(400, 'This code is invalid or expired. Request a new code and try again.')
    if not result.is_success:
        raise HTTPException(503, 'Email sign-in is temporarily unavailable. Please try again.')
    try:
        return result.json()
    except ValueError as exc:
        raise HTTPException(503, 'Email sign-in is temporarily unavailable. Please try again.') from exc


def request_code(email: str) -> None:
    provider_request('/otp', {'email': email, 'create_user': True})


def verify_code(email: str, code: str) -> dict:
    body = provider_request('/verify', {'email': email, 'token': code, 'type': 'email'}, verification=True)
    try:
        user = body['user']
        subject = str(UUID(user['id']))
        confirmed_email = user['email'].strip().lower()
        if (confirmed_email != email or not user.get('email_confirmed_at')
                or not body.get('access_token')):
            raise ValueError('Unconfirmed or mismatched identity')
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(400, 'Email verification failed. Request a new code and try again.') from exc
    # Provider tokens and refresh tokens are never forwarded or stored.
    return {'subject': subject, 'email': confirmed_email}
