"""Stage 1 of "generate design": pick furniture for the room.

The student's current-room photo + text inputs (budget, style, notes) + a list
of candidate catalogue items go in; a structured recommendation comes out -
which items, how many, where they go and why. This output is for the app (it
drives Stage 2 image generation and is persisted for later); the student only
ever sees the Stage 2 image.

Provider-agnostic, same shape as ``image_generation``: swap ``MockRecommender``
for ``GeminiRecommender`` via ``RECOMMENDATION_PROVIDER`` without touching the
caller. Whatever a provider returns is validated and hard-clamped to the budget
here, so a bad model response can never blow the budget or name a phantom item.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import settings
from app.models import CatalogueItem
from app.services.gemini_logging import log_gemini_request

logger = logging.getLogger(__name__)


@dataclass
class RecommendedItem:
    item_id: int
    quantity: int
    placement: str = ""   # where in the room it goes
    reason: str = ""       # why it was picked


@dataclass
class RecommendationRequest:
    budget: float
    style: str
    notes: str
    candidate_items: list[CatalogueItem]
    instructions: str = ""       # Stage 1 prompt document
    room_image_path: str = ""    # the student's current-room photo, if available


@dataclass
class RecommendationResult:
    items: list[RecommendedItem] = field(default_factory=list)
    total_price: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "items": [vars(i) for i in self.items],
            "total_price": round(self.total_price, 2),
            "summary": self.summary,
        }


class Recommender(ABC):
    @abstractmethod
    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """Choose catalogue items that fit the room's style and budget."""
        raise NotImplementedError


def clamp_to_budget(
    items: list[RecommendedItem],
    by_id: dict[int, CatalogueItem],
    budget: float,
) -> tuple[list[RecommendedItem], float]:
    """Keep items (in order) while the running total stays within budget.

    Drops any item that would push the total over, and any item whose id isn't
    in ``by_id`` (the candidate set). Quantities are coerced to >= 1.
    """
    kept: list[RecommendedItem] = []
    total = 0.0
    for item in items:
        product = by_id.get(item.item_id)
        if product is None:
            logger.warning("Recommendation named unknown item id %s; dropping.", item.item_id)
            continue
        qty = max(1, int(item.quantity or 1))
        line = product.price * qty
        if total + line > budget:
            continue
        kept.append(RecommendedItem(item.item_id, qty, item.placement, item.reason))
        total += line
    return kept, round(total, 2)


class MockRecommender(Recommender):
    """Deterministic stand-in: greedy cheapest-first fill, one of each.

    Keeps the flow (and the tests) working with no API key. Mirrors the old
    in-image-generator selection so behaviour is unchanged when no real
    recommender is configured.
    """

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        chosen: list[RecommendedItem] = []
        total = 0.0
        for product in sorted(request.candidate_items, key=lambda i: i.price):
            if total + product.price <= request.budget:
                chosen.append(
                    RecommendedItem(
                        item_id=product.id,
                        quantity=1,
                        placement="",
                        reason="Fits the room's style and stays within budget.",
                    )
                )
                total += product.price
        summary = (
            f"Selected {len(chosen)} {request.style} items for a total of "
            f"${total:,.2f} (budget ${request.budget:,.0f})."
        )
        return RecommendationResult(items=chosen, total_price=round(total, 2), summary=summary)


class GeminiRecommender(Recommender):
    """Google Gemini multimodal model: reasons over the candidates and returns JSON.

    Sees the student's current-room photo (when one is supplied) alongside the
    text inputs, so it can recommend improvements on top of what's already
    there. Needs ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``). The model is asked
    for strict JSON; we parse defensively and then ``clamp_to_budget`` so the
    result is always safe regardless of what came back.
    """

    MODEL = "gemini-3.6-flash"
    MAX_CANDIDATES = 80

    def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        from google import genai
        from google.genai import types

        api_key = settings.gemini_api_key or settings.google_api_key
        if not api_key:
            raise RuntimeError(
                "Furniture recommendation needs GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "set in backend/.env"
            )

        by_id = {c.id: c for c in request.candidate_items}

        # The room photo goes first so the prompt's "read the room first"
        # instructions have something to refer to; a missing/unset path just
        # falls back to a text-only request.
        contents: list = []
        room_part = _room_image_part(request.room_image_path, types)
        if room_part is not None:
            contents.append(room_part)
        contents.append(_build_prompt(request, self.MAX_CANDIDATES))

        config = types.GenerateContentConfig(
            system_instruction=request.instructions or None,
            response_mime_type="application/json",
            temperature=0.4,
        )
        log_gemini_request(
            label="Gemini recommender request",
            model=self.MODEL,
            contents=contents,
            config=config,
        )

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=config,
        )

        raw_items, summary = _parse_response(getattr(response, "text", "") or "")
        items, total = clamp_to_budget(raw_items, by_id, request.budget)
        if not items:
            logger.warning(
                "Gemini recommendation produced no usable items; "
                "falling back to greedy selection."
            )
            return MockRecommender().recommend(request)
        return RecommendationResult(items=items, total_price=total, summary=summary)


def _room_image_part(room_image_path: str, types):
    """Load the student's room photo as a Gemini image Part, or None.

    A missing or unreadable file is tolerated: we log and return None so the
    recommender still runs as a text-only request.
    """
    if not room_image_path:
        return None
    try:
        with open(room_image_path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        logger.warning("Room photo not readable at %s (%s); recommending text-only.", room_image_path, exc)
        return None
    mime = mimetypes.guess_type(room_image_path)[0] or "image/jpeg"
    return types.Part.from_bytes(data=data, mime_type=mime)


def _build_prompt(request: RecommendationRequest, max_candidates: int) -> str:
    if request.room_image_path:
        opening = (
            "Improve this college dorm room for a student. A photo of the room "
            "as it looks now is included above; recommend items that build on "
            "what is already there."
        )
    else:
        opening = (
            "Furnish a college dorm room for a student. No room photo is "
            "available; assume the basics (bed, desk, wardrobe) may already be "
            "in place and favour versatile pieces."
        )
    lines = [
        opening,
        f"Style: {request.style.replace('_', ' ')}.",
        f"Total budget: ${request.budget:.0f} (hard limit).",
    ]
    if request.notes.strip():
        lines.append(f"Student's notes: {request.notes.strip()}")
    lines += [
        "",
        "Choose from ONLY these catalogue items (use the exact id). You may pick "
        "the same item more than once via quantity. Keep the summed "
        "price * quantity within budget.",
        "",
    ]
    for c in request.candidate_items[:max_candidates]:
        lines.append(
            f"id={c.id} | retailer={c.retailer} | {c.name} | {c.category} | {c.currency} {c.price:.2f} "
            f"| {c.dominant_color} | {c.description[:160]}"
        )
    lines += [
        "",
        "Respond with JSON only, no prose, in exactly this shape:",
        '{"items":[{"item_id":<int>,"quantity":<int>,"placement":"<short>",'
        '"reason":"<short>"}],"summary":"<one or two sentences>"}',
    ]
    return "\n".join(lines)


def _parse_response(text: str) -> tuple[list[RecommendedItem], str]:
    """Pull items + summary out of the model's (hopefully JSON) reply."""
    payload = _loads_lenient(text)
    if not isinstance(payload, dict):
        return [], ""
    items: list[RecommendedItem] = []
    for entry in payload.get("items", []) or []:
        try:
            items.append(
                RecommendedItem(
                    item_id=int(entry["item_id"]),
                    quantity=max(1, int(entry.get("quantity", 1))),
                    placement=str(entry.get("placement", "")).strip(),
                    reason=str(entry.get("reason", "")).strip(),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return items, str(payload.get("summary", "")).strip()


def _loads_lenient(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def get_recommender() -> Recommender:
    """Factory: picks the recommender based on RECOMMENDATION_PROVIDER."""
    provider = settings.recommendation_provider.lower()
    if provider == "gemini":
        return GeminiRecommender()
    return MockRecommender()
