"""Opaque bearer sessions, ownership checks, and shared SQLite abuse limits."""
import hashlib
import sqlite3
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import get_db, utcnow_iso

bearer = HTTPBearer(auto_error=False)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = None
    if credentials and len(credentials.credentials) <= 256:
        row = db.execute(
            "SELECT u.id, u.handle, u.created_at, u.email FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.revoked = 0 AND s.expires_at > ?",
            (token_hash(credentials.credentials), utcnow_iso()),
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Session expired or invalid. Sign in with your email to continue.",
                            headers={"WWW-Authenticate": "Bearer"})
    return dict(row)


def owned_submission(db: sqlite3.Connection, submission_id: int, user_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM submissions WHERE id = ? AND user_id = ?",
                     (submission_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Submission not found")
    return row


def enforce_limit(db: sqlite3.Connection, scope: str, subject: str, limit: int,
                  window_seconds: int = 3600) -> None:
    # Separate short transaction: failed requests still count, across workers.
    now = time.time()
    db.execute("BEGIN IMMEDIATE")
    count = db.execute(
        "SELECT COUNT(*) FROM rate_attempts WHERE scope = ? AND subject = ? AND attempted_at > ?",
        (scope, subject, now - window_seconds),
    ).fetchone()[0]
    if count >= limit:
        db.rollback()
        raise HTTPException(429, "Too many requests. Try again later.",
                            headers={"Retry-After": str(window_seconds)})
    db.execute("INSERT INTO rate_attempts VALUES (?, ?, ?)", (scope, subject, now))
    db.commit()


def private_paths(data: dict, submission_id: int) -> dict:
    """Keep internal filesystem locations out of API responses."""
    if "room_image_path" in data:
        data["room_image_path"] = f"/api/media/{submission_id}/room"
    if "generated_image_path" in data and data["generated_image_path"]:
        data["generated_image_path"] = f"/api/media/{submission_id}/generated"
    return data
