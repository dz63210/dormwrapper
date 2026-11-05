"""Application configuration, loaded from environment variables / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Path to the SQLite file, relative to the backend/ directory. A legacy
    # "sqlite:///" prefix is tolerated (see app/database.py).
    database_url: str = "./data/app.db"
    upload_dir: str = "./data/uploads"
    frontend_origins: str = "http://localhost:5173"
    session_hours: int = Field(default=24, ge=1, le=168)
    max_upload_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=32 * 1024 * 1024)
    max_image_pixels: int = Field(default=20_000_000, ge=1)
    login_attempts_per_hour: int = Field(default=20, ge=1)
    generations_per_hour: int = Field(default=10, ge=1)
    uploads_per_hour: int = Field(default=30, ge=1)
    debug_ai_logging: bool = False
    development_cors: bool = False
    allow_guest_login: bool = False
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    verified_session_hours: int = Field(default=168, ge=1, le=720)
    email_requests_per_hour: int = Field(default=3, ge=1)
    email_verifications_per_hour: int = Field(default=10, ge=1)

    # The "generate design" flow runs in two AI stages, each with its own
    # provider switch ("mock" | "gemini") and its own instruction document.
    #   Stage 1: text inputs -> structured furniture recommendation (JSON)
    #   Stage 2: recommendation -> generated room image
    recommendation_provider: str = "mock"
    image_gen_provider: str = "mock"

    # The IKEA catalogue that seed_data.py loads into the DB. Generated from the
    # repo-root catalog.json by `python export_catalog.py`.
    catalogue_data_file: str = "./data/catalog.json"
    # Folder of per-item product photos (images/<product_id>.jpg), served at
    # /catalogue-images. Lives at the repo root, one level above backend/.
    catalogue_images_dir: str = "../images"

    # Instruction documents for the two AI stages (paths relative to backend/).
    # Loaded once via app.services.prompts.load_prompt(); a missing file is
    # tolerated (the stage just runs with no extra instructions).
    recommendation_prompt_path: str = "./app/prompts/recommendation.md"
    image_gen_context_path: str = "./app/prompts/image_gen_context.md"

    # Stage 2 attaches the product photo of the top-N recommended items to the
    # image request as labelled references, so the model renders the real
    # product rather than guessing from its text description. Items past the cap
    # (and any whose photo file is missing) are still described in text.
    image_gen_max_item_photos: int = 6

    # Image-gen provider credentials. IMAGE_GEN_PROVIDER=gemini uses the Google
    # Gemini "Nano Banana 2 Lite" model and reads gemini_api_key / google_api_key.
    gemini_api_key: str | None = None
    google_api_key: str | None = None
    replicate_api_token: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


settings = Settings()
