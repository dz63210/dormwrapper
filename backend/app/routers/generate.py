"""POST /api/generate/{submission_id}: the two-stage "generate design" flow.

Stage 1  furniture recommendation (room photo + text -> structured JSON, app-facing)
Stage 2  image generation         (recommendation -> room image, user-facing)

One blocking request runs both and persists a single ``suggestions`` row.
Stage 1 failing fails the request; Stage 2 failing still returns the
recommendation (with no image) so it isn't lost.
"""
import json
import logging
import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.database import get_db, utcnow_iso
from app.models import CatalogueItem
from app.schemas import SuggestionOut
from app.security import current_user, owned_submission, enforce_limit, private_paths
from app.services.image_generation import ImageGenRequest, get_image_generator
from app.services.prompts import load_prompt
from app.services.recommendation import RecommendationRequest, get_recommender
from app.services.catalogue_repository import search_catalogue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])

# Cap on how many catalogue rows we hand to Stage 1 (keeps the prompt bounded).
CANDIDATE_LIMIT = 80


@router.post("/{submission_id}", response_model=SuggestionOut)
def generate_suggestion(submission_id: int, user: dict = Depends(current_user),
                        db: sqlite3.Connection = Depends(get_db)) -> dict:
    submission = owned_submission(db, submission_id, user["id"])

    existing = db.execute(
        "SELECT * FROM suggestions WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    if existing is not None:
        return _serialize(existing, db)

    enforce_limit(db, "generation", str(user["id"]), settings.generations_per_hour)

    style_value = submission["style"]
    candidate_items = search_catalogue(db, style=style_value,
                                      max_price=submission["budget"], currency="USD",
                                      limit=CANDIDATE_LIMIT)
    if not candidate_items:
        candidate_items = search_catalogue(db, max_price=submission["budget"],
                                          currency="USD", limit=CANDIDATE_LIMIT)
    by_id = {c.id: c for c in candidate_items}

    # --- Stage 1: furniture recommendation (required) --------------------------
    try:
        recommendation = get_recommender().recommend(
            RecommendationRequest(
                budget=submission["budget"],
                style=style_value,
                notes=submission["notes"],
                candidate_items=candidate_items,
                instructions=load_prompt(settings.recommendation_prompt_path),
                room_image_path=submission["room_image_path"],
            )
        )
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the client
        raise HTTPException(
            status_code=502, detail="Furniture recommendation failed. Please try again later."
        ) from exc

    recommended_lines = [
        (by_id[r.item_id], r.quantity, r.placement, r.reason)
        for r in recommendation.items
        if r.item_id in by_id
    ]

    # --- Stage 2: image generation (best effort) ------------------------------
    generated_image_path = ""
    try:
        generated_image_path = get_image_generator().generate(
            ImageGenRequest(
                room_image_path=submission["room_image_path"],
                style=style_value,
                notes=submission["notes"],
                recommended_items=recommended_lines,
                summary=recommendation.summary,
                instructions=load_prompt(settings.image_gen_context_path),
            )
        ).generated_image_path
    except Exception as exc:  # noqa: BLE001 - keep the recommendation even if the image fails
        logger.warning("Image generation failed for submission %s (%s)", submission_id, type(exc).__name__)

    # item_ids repeats an id per unit so the hydrated items list reflects quantity.
    item_ids = ",".join(
        str(r.item_id) for r in recommendation.items for _ in range(r.quantity)
    )
    cursor = db.execute(
        "INSERT INTO suggestions "
        "(submission_id, generated_image_path, total_price, item_ids, "
        "recommendation_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            submission_id,
            generated_image_path,
            recommendation.total_price,
            item_ids,
            json.dumps(recommendation.to_dict()),
            utcnow_iso(),
        ),
    )
    row = db.execute("SELECT * FROM suggestions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row, db)


def _serialize(suggestion_row: sqlite3.Row, db: sqlite3.Connection) -> dict:
    """Attach the full CatalogueItem rows named in item_ids, plus the Stage 1 plan."""
    data = dict(suggestion_row)
    ids = [int(i) for i in data["item_ids"].split(",") if i]
    items: list[dict] = []
    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = db.execute(
            f"SELECT * FROM catalogue_items WHERE id IN ({placeholders})", ids
        ).fetchall()
        by_id = {row["id"]: asdict(CatalogueItem.from_row(row)) for row in rows}
        items = [by_id[i] for i in ids if i in by_id]
    data["items"] = items
    data["recommendation"] = _load_recommendation(data.get("recommendation_json"))
    return private_paths(data, data["submission_id"])


def _load_recommendation(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
