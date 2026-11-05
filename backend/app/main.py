"""FastAPI application entrypoint."""
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

# Surface app.* logs (e.g. the exact prompts sent to Gemini) on the console
# even when uvicorn owns the logging config.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, catalogue, designs, generate, submissions, media
from app.services.prompts import load_prompt
from app.request_limits import RequestBodyLimit


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    os.makedirs(settings.upload_dir, exist_ok=True)
    init_db()
    # Read both AI-stage instruction documents once so the first "generate
    # design" click doesn't pay for the file read (and any problem surfaces
    # at boot).
    load_prompt(settings.recommendation_prompt_path)
    load_prompt(settings.image_gen_context_path)
    yield


app = FastAPI(title="Dorm Decor Suggestion API", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestBodyLimit)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Accept any localhost / 127.0.0.1 port for local dev, so a Vite port
    # fallback (5174, 5175, ...) or a 127.0.0.1 vs localhost mismatch doesn't
    # break the frontend with a CORS preflight 400. Set FRONTEND_ORIGINS for
    # deployed environments.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if settings.development_cors else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalogue.router)
app.include_router(submissions.router)
app.include_router(generate.router)
app.include_router(designs.router)

# Uploaded and generated photos require the same session as their submission.
app.include_router(media.router)


@app.middleware("http")
async def private_response_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/") and request.url.path not in {"/api/catalogue", "/api/health"}:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# Serve the catalogue product photos (images/<product_id>.jpg at the repo root).
_catalogue_images = Path(settings.catalogue_images_dir)
if not _catalogue_images.is_absolute():
    _catalogue_images = (Path(__file__).resolve().parent.parent / _catalogue_images).resolve()
app.mount(
    "/catalogue-images",
    StaticFiles(directory=str(_catalogue_images), check_dir=False),
    name="catalogue-images",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
