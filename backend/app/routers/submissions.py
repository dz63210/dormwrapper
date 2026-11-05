"""Endpoints for students uploading a room photo + budget/style."""
import os
import sqlite3
import uuid
import io
import warnings

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.database import get_db, utcnow_iso
from app.models import DecorStyle
from app.schemas import SubmissionOut
from app.security import current_user, enforce_limit, owned_submission, private_paths

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("", response_model=SubmissionOut)
async def create_submission(
    budget: float = Form(..., gt=0, le=100000),
    style: DecorStyle = Form(...),
    notes: str = Form("", max_length=2000),
    room_width_ft: float | None = Form(default=None, gt=0, le=1000),
    room_length_ft: float | None = Form(default=None, gt=0, le=1000),
    image: UploadFile = File(...),
    user: dict = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {image.content_type}")

    enforce_limit(db, "upload", str(user["id"]), settings.uploads_per_hour)
    try:
        contents = await image.read(settings.max_upload_bytes + 1)
    finally:
        await image.close()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(413, "Image exceeds the upload size limit")
    formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    # Decode and re-encode; never trust a filename or a declared MIME type.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(contents)) as photo:
                if photo.format != formats[image.content_type]:
                    raise ValueError("Image format mismatch")
                if photo.width * photo.height > settings.max_image_pixels:
                    raise ValueError("Image dimensions too large")
                photo.load()
                clean = ImageOps.exif_transpose(photo).convert("RGB")
                clean.info.clear()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(400, "Invalid image. Upload a valid JPEG, PNG, or WebP within the size limits.") from exc
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.jpg")
    clean.save(stored_path, format="JPEG", quality=90)

    cursor = db.execute(
        "INSERT INTO submissions "
        "(created_at, room_image_path, budget, style, notes, room_width_ft, room_length_ft, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (utcnow_iso(), stored_path, budget, style.value, notes, room_width_ft, room_length_ft, user["id"]),
    )
    row = db.execute("SELECT * FROM submissions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return private_paths(dict(row), row["id"])


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, user: dict = Depends(current_user),
                   db: sqlite3.Connection = Depends(get_db)) -> dict:
    row = owned_submission(db, submission_id, user["id"])
    return private_paths(dict(row), submission_id)
