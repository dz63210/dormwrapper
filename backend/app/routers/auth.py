"""Verified email accounts and optional legacy guest sessions."""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.database import get_db, utcnow_iso
from app.schemas import LoginRequest, SessionOut, UserOut, EmailLoginRequest, EmailVerifyRequest
from app.security import bearer, current_user, enforce_limit, token_hash
from app.services.email_auth import request_code, verify_code

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login", response_model=SessionOut)
def login(payload: LoginRequest, request: Request, response: Response,
          db: sqlite3.Connection = Depends(get_db)) -> dict:
    if not settings.allow_guest_login:
        raise HTTPException(403, "Please sign in with your verified email.")
    subject = token_hash(request.client.host if request.client else "unknown")
    enforce_limit(db, "login", subject, settings.login_attempts_per_hour)
    handle = payload.handle.lower()
    created_at = utcnow_iso()
    try:
        cursor = db.execute("INSERT INTO users (handle, created_at) VALUES (?, ?)",
                            (handle, created_at))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Handle unavailable. Choose a new handle for your guest session.") from exc
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)).isoformat(timespec="seconds")
    db.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
               (token_hash(token), cursor.lastrowid, expires_at))
    response.headers["Cache-Control"] = "no-store"
    return {"id": cursor.lastrowid, "handle": handle, "created_at": created_at,
            "token": token, "expires_at": expires_at}


@router.post('/auth/request-code')
def send_email_code(payload: EmailLoginRequest, request: Request,
                    db: sqlite3.Connection = Depends(get_db)) -> dict:
    email = str(payload.email)
    subject = token_hash(request.client.host if request.client else 'unknown')
    enforce_limit(db, 'email-request-ip', subject, settings.login_attempts_per_hour)
    enforce_limit(db, 'email-request-address', token_hash(email), settings.email_requests_per_hour)
    enforce_limit(db, 'email-request-cooldown', token_hash(email), 1, window_seconds=60)
    request_code(email)
    return {'message': 'Check your inbox for a sign-in code.'}


@router.post('/auth/verify-code', response_model=SessionOut)
def verify_email_code(payload: EmailVerifyRequest, request: Request, response: Response,
                      credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                      db: sqlite3.Connection = Depends(get_db)) -> dict:
    email = str(payload.email)
    subject = token_hash(request.client.host if request.client else 'unknown')
    enforce_limit(db, 'email-verify-ip', subject, settings.login_attempts_per_hour)
    enforce_limit(db, 'email-verify-address', token_hash(email), settings.email_verifications_per_hour)
    previous = current_user(credentials, db) if credentials else None
    identity = verify_code(email, payload.code)
    # Serialize account creation and guest conversion to prevent concurrent claims.
    db.execute('BEGIN IMMEDIATE')
    account = db.execute('SELECT * FROM users WHERE auth_subject = ?', (identity['subject'],)).fetchone()
    if previous and previous['email'] is not None and (account is None or account['id'] != previous['id']):
        raise HTTPException(409, 'Sign out before signing in to a different email account.')
    try:
        if account is None:
            if previous:
                user_id = previous['id']
                db.execute('UPDATE users SET email = ?, auth_subject = ? WHERE id = ?',
                           (identity['email'], identity['subject'], user_id))
            else:
                cursor = db.execute('INSERT INTO users (handle, created_at, email, auth_subject) VALUES (?, ?, ?, ?)',
                                    ('user_' + secrets.token_hex(6), utcnow_iso(), identity['email'], identity['subject']))
                user_id = cursor.lastrowid
        else:
            user_id = account['id']
            db.execute('UPDATE users SET email = ? WHERE id = ?', (identity['email'], user_id))
            if previous and previous['id'] != user_id:
                # Both the guest credential and verified email authorize this transfer.
                db.execute('UPDATE submissions SET user_id = ? WHERE user_id = ?', (user_id, previous['id']))
        if previous:
            db.execute('UPDATE sessions SET revoked = 1 WHERE user_id = ?', (previous['id'],))
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=settings.verified_session_hours)).isoformat(timespec='seconds')
        db.execute('INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)',
                   (token_hash(token), user_id, expires_at))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, 'Unable to link this account. Please contact support.') from exc
    account = dict(db.execute('SELECT id, handle, created_at, email FROM users WHERE id = ?', (user_id,)).fetchone())
    response.headers['Cache-Control'] = 'no-store'
    return {**account, 'token': token, 'expires_at': expires_at}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> dict:
    return user


@router.post("/logout", status_code=204)
def logout(user: dict = Depends(current_user),
           credentials: HTTPAuthorizationCredentials = Depends(bearer),
           db: sqlite3.Connection = Depends(get_db)) -> Response:
    db.execute("UPDATE sessions SET revoked = 1 WHERE token_hash = ? AND user_id = ?",
               (token_hash(credentials.credentials), user["id"]))
    return Response(status_code=204)
