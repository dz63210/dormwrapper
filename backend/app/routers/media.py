"""Private media is authorized by submission ownership, never by filename."""
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.database import get_db
from app.security import current_user, owned_submission

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{submission_id}/{kind}")
def read_media(submission_id: int, kind: Literal["room", "generated"],
               user: dict = Depends(current_user),
               db: sqlite3.Connection = Depends(get_db)) -> FileResponse:
    submission = owned_submission(db, submission_id, user["id"])
    raw_path = submission["room_image_path"]
    if kind == "generated":
        suggestion = db.execute("SELECT generated_image_path FROM suggestions WHERE submission_id = ?",
                                (submission_id,)).fetchone()
        raw_path = suggestion[0] if suggestion else ""
    if not raw_path:
        raise HTTPException(404, "Image not found")
    root = Path(settings.upload_dir).resolve()
    path = Path(raw_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, headers={"Cache-Control": "private, no-store",
                                      "X-Content-Type-Options": "nosniff"})
