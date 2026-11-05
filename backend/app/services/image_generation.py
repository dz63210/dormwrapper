"""Stage 2 of "generate design": turn a furniture recommendation into an image.

Stage 1 (``app.services.recommendation``) has already decided which catalogue
items go in the room, how many and where. This stage only renders: it takes the
student's room photo + that recommendation and produces a single restyled
image. It does no selection and no budgeting.

Provider-agnostic: swap ``MockImageGenerator`` for ``GeminiImageGenerator`` via
``IMAGE_GEN_PROVIDER`` without touching the caller.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops

from app.config import settings
from app.models import CatalogueItem
from app.services.gemini_logging import log_gemini_request
from app.services.prompts import load_prompt

logger = logging.getLogger(__name__)

# backend/ -- app/services/image_generation.py -> parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[2]

# One (product, quantity, placement, reason) line of the recommendation to
# render. `reason` is the Stage 1 note on why the item was chosen; it signals
# whether the piece is an addition or a replacement.
RecommendedLine = tuple[CatalogueItem, int, str, str]


@dataclass
class _ItemPhoto:
    """A recommended item's product photo, attached to the Gemini request."""

    image_no: int           # 1-based position among the request's images (room = 1)
    product: CatalogueItem
    data: bytes
    mime: str


def _catalogue_images_dir() -> Path:
    """Absolute path of the product-photo folder (settings.catalogue_images_dir)."""
    path = Path(settings.catalogue_images_dir)
    return path if path.is_absolute() else (_BACKEND_DIR / path).resolve()


def _load_item_photo(product: CatalogueItem) -> tuple[bytes, str] | None:
    """Read a product's photo from disk, or None if it isn't there / unreadable.

    The filename matches the served ``image_url`` (``/catalogue-images/<file>``),
    which keeps the catalogue's zero-padded product id -- not ``product.id``.
    """
    if not product.image_url.startswith("/catalogue-images/"):
        return None
    name = os.path.basename(product.image_url)
    file_path = _catalogue_images_dir() / name
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        logger.info("No product photo for item %s at %s (%s); using text only.",
                    product.id, file_path, exc)
        return None
    mime = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
    return data, mime


def _collect_item_photos(items: list[RecommendedLine], limit: int) -> list[_ItemPhoto]:
    """Load product photos for the first ``limit`` items that have one on disk.

    ``items`` is in Stage 1 priority order, so the cap keeps the highest-impact
    pieces. Image numbers start at 2 because the room photo is image 1.
    """
    photos: list[_ItemPhoto] = []
    if limit <= 0:
        return photos
    for product, _qty, _placement, _reason in items:
        loaded = _load_item_photo(product)
        if loaded is None:
            continue
        data, mime = loaded
        photos.append(_ItemPhoto(len(photos) + 2, product, data, mime))
        if len(photos) >= limit:
            break
    return photos


def load_context_document() -> str:
    """The Stage 2 image instruction document (see settings.image_gen_context_path)."""
    return load_prompt(settings.image_gen_context_path)


@dataclass
class ImageGenRequest:
    room_image_path: str
    style: str
    notes: str
    recommended_items: list[RecommendedLine] = field(default_factory=list)
    summary: str = ""       # human-readable recap of the recommendation
    instructions: str = ""  # Stage 2 prompt document


@dataclass
class ImageGenResult:
    generated_image_path: str


class ImageGenerator(ABC):
    @abstractmethod
    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        """Render the recommended room as a single image."""
        raise NotImplementedError


class MockImageGenerator(ImageGenerator):
    """Placeholder: copies the student's photo through as the "generated" image.

    Lets the whole flow (API contract, DB rows, frontend) run end to end with
    no image-gen API key.
    """

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        os.makedirs(settings.upload_dir, exist_ok=True)
        out_name = f"mock_generated_{os.path.basename(request.room_image_path)}"
        out_path = os.path.join(settings.upload_dir, out_name)
        shutil.copy(request.room_image_path, out_path)
        return ImageGenResult(generated_image_path=out_path)


class GeminiImageGenerator(ImageGenerator):
    """Google Gemini "Nano Banana 2 Lite" (``gemini-3.1-flash-lite-image``).

    Redraws the student's room photo with the recommended items in place. Needs
    a ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``) in the environment / ``.env``.
    """

    MODEL = "gemini-3.1-flash-lite-image"

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        from google import genai
        from google.genai import types

        api_key = settings.gemini_api_key or settings.google_api_key
        if not api_key:
            raise RuntimeError(
                "Gemini image generation needs GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "set in backend/.env"
            )

        with open(request.room_image_path, "rb") as f:
            room_bytes = f.read()
        mime = mimetypes.guess_type(request.room_image_path)[0] or "image/jpeg"

        # Attach product photos for the top-N items as labelled references
        # (image 1 is the room; images 2..N+1 are products).
        item_photos = _collect_item_photos(
            request.recommended_items, settings.image_gen_max_item_photos
        )

        contents = [
            _build_prompt(request, item_photos),
            types.Part.from_bytes(data=room_bytes, mime_type=mime),
        ]
        for photo in item_photos:
            contents.append(types.Part.from_bytes(data=photo.data, mime_type=photo.mime))

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            # The context document (settings.image_gen_context_path) steers
            # the whole render; the per-request prompt supplies the items.
            system_instruction=request.instructions or None,
        )
        log_gemini_request(
            label="Gemini image-gen request",
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

        image_bytes, image_mime = _first_image(response)
        if image_bytes is None:
            raise RuntimeError(f"Gemini ({self.MODEL}) returned no image for this request.")

        # Nano Banana sometimes returns the render letterboxed onto a square
        # canvas (solid bars top/bottom or left/right). Trim them so the saved
        # image is just the room.
        image_bytes = _trim_solid_border(image_bytes)

        os.makedirs(settings.upload_dir, exist_ok=True)
        ext = mimetypes.guess_extension(image_mime) or ".png"
        base = os.path.splitext(os.path.basename(request.room_image_path))[0]
        out_path = os.path.join(settings.upload_dir, f"gemini_generated_{base}{ext}")
        with open(out_path, "wb") as f:
            f.write(image_bytes)

        return ImageGenResult(generated_image_path=out_path)


def _build_prompt(
    request: ImageGenRequest, item_photos: list[_ItemPhoto] | None = None
) -> str:
    item_photos = item_photos or []
    photo_no_by_id = {p.product.id: p.image_no for p in item_photos}

    lines = [
        "Restyle this photo of a college dorm room for a student.",
        f"Target aesthetic: {request.style.replace('_', ' ')}.",
    ]
    if request.summary.strip():
        lines.append(f"Intended overall look: {request.summary.strip()}")

    if item_photos:
        lines += [
            "",
            f"Images: image 1 is the CURRENT ROOM — the room to restyle. Images 2"
            f"-{item_photos[-1].image_no} are product reference photos on plain "
            "backgrounds. For any piece marked \"[Image N]\" below, render that "
            "exact product — its real shape, proportions, material and colour "
            "from the photo — not a generic stand-in. Ignore each product "
            "photo's background.",
        ]

    lines += [
        "",
        "Keep the same room and camera angle. Keep existing furniture that is "
        "not replaced below. Add or swap in only these IKEA pieces (a few "
        "houseplants aside), in these quantities and roughly these positions — "
        "put each where it makes functional sense for its type and next to what "
        "it is used with:",
    ]
    for product, qty, placement, reason in request.recommended_items:
        line = f"- {qty}x {product.name} ({product.category}, {product.dominant_color})"
        photo_no = photo_no_by_id.get(product.id)
        if photo_no:
            line += f" [Image {photo_no}]"
        if placement:
            line += f", placed {placement}"
        if reason:
            line += f" — {reason}"
        line += f": {product.description}"
        lines.append(line)
    if request.notes.strip():
        lines += ["", f"Student's notes: {request.notes.strip()}"]
    lines += ["", "Return a single photorealistic image of the redecorated room."]
    return "\n".join(lines)


# 0-255: how far a pixel may differ from the corner colour and still count as
# part of a solid pad bar (slack for JPEG noise on the letterbox edge).
_BORDER_TOLERANCE = 12


def _trim_solid_border(data: bytes) -> bytes:
    """Crop a uniform pad colour off the image edges (e.g. square-canvas letterboxing).

    The pad colour is taken from the top-left pixel. Returns ``data`` unchanged
    if the image can't be read or there's no border to remove.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001 - never fail the render over a cosmetic trim
        logger.warning("Could not open generated image to trim borders; keeping as-is.")
        return data

    rgb = img.convert("RGB")
    pad = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    mask = ImageChops.difference(rgb, pad).convert("L").point(
        lambda p: 255 if p > _BORDER_TOLERANCE else 0
    )
    bbox = mask.getbbox()
    if not bbox or bbox == (0, 0, rgb.width, rgb.height):
        return data

    left, upper, right, lower = bbox
    logger.info(
        "Trimmed solid border from generated image: %s -> %s "
        "(top %d, bottom %d, left %d, right %d).",
        rgb.size, (right - left, lower - upper),
        upper, rgb.height - lower, left, rgb.width - right,
    )

    out = io.BytesIO()
    fmt = img.format or "PNG"
    save_kwargs = {"quality": 95} if fmt == "JPEG" else {}
    img.crop(bbox).save(out, format=fmt, **save_kwargs)
    return out.getvalue()


def _first_image(response) -> tuple[bytes | None, str]:
    """Pull the first inline image out of a google-genai response."""
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data, (inline.mime_type or "image/png")
    return None, "image/png"


class ReplicateImageGenerator(ImageGenerator):
    """Stub for a future Replicate (Stable Diffusion / Flux) implementation."""

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        raise NotImplementedError("Wire up a Replicate model here.")


def get_image_generator() -> ImageGenerator:
    """Factory: picks the generator based on IMAGE_GEN_PROVIDER in settings."""
    provider = settings.image_gen_provider.lower()
    if provider == "gemini":
        return GeminiImageGenerator()
    if provider == "replicate":
        return ReplicateImageGenerator()
    return MockImageGenerator()
