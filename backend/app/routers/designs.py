"""Saving designs, and listing a user's saved designs.

A "design" is a submission that has a generated suggestion. Saving is
explicit (SPEC: after a design is generated the user picks Save vs. keep
iterating) and flips ``suggestions.saved``. Bearer sessions establish ownership.
"""
import json
import sqlite3
from dataclasses import asdict
from app.models import CatalogueItem

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.schemas import DesignOut
from app.security import current_user, owned_submission, private_paths

router = APIRouter(prefix="/api/designs", tags=["designs"])

# submission fields + its suggestion's fields, for one design.
_DESIGN_SELECT = """
    SELECT s.id AS submission_id, s.created_at, s.style, s.budget, s.room_image_path,
           g.generated_image_path, g.total_price, g.item_ids, g.recommendation_json
    FROM submissions s
    JOIN suggestions g ON g.submission_id = s.id
"""


@router.get("", response_model=list[DesignOut])
def list_saved_designs(
    user: dict = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        _DESIGN_SELECT + " WHERE s.user_id = ? AND g.saved = 1 ORDER BY g.created_at DESC",
        (user["id"],),
    ).fetchall()
    return [_with_items(dict(row), db) for row in rows]


@router.post("/{submission_id}/save", response_model=DesignOut)
def save_design(
    submission_id: int,
    user: dict = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    return _set_saved(submission_id, user["id"], 1, db)


@router.delete("/{submission_id}/save", response_model=DesignOut)
def unsave_design(
    submission_id: int,
    user: dict = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    return _set_saved(submission_id, user["id"], 0, db)


def _set_saved(
    submission_id: int, user_id: int, value: int, db: sqlite3.Connection
) -> dict:
    owned_submission(db, submission_id, user_id)

    updated = db.execute(
        "UPDATE suggestions SET saved = ? WHERE submission_id = ?", (value, submission_id)
    )
    if updated.rowcount == 0:
        raise HTTPException(
            status_code=409, detail="This submission has no generated design yet"
        )

    row = db.execute(_DESIGN_SELECT + " WHERE s.id = ?", (submission_id,)).fetchone()
    return _with_items(dict(row), db)


def _with_items(design: dict, db: sqlite3.Connection) -> dict:
    """Replace item_ids with full CatalogueItem rows, and parse the Stage 1 plan."""
    ids = [int(i) for i in design.pop("item_ids", "").split(",") if i]
    items: list[dict] = []
    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = db.execute(
            f"SELECT * FROM catalogue_items WHERE id IN ({placeholders})", ids
        ).fetchall()
        by_id = {row["id"]: asdict(CatalogueItem.from_row(row)) for row in rows}
        items = [by_id[i] for i in ids if i in by_id]
    design["items"] = items

    raw = design.pop("recommendation_json", "") or ""
    try:
        design["recommendation"] = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        design["recommendation"] = None
    return private_paths(design, design["submission_id"])
