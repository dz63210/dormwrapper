"""Pydantic request/response schemas."""
import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator

from app.models import DecorStyle

# 3-20 chars, letters/digits/underscore. Keep in sync with the frontend check
# in frontend/src/pages/LoginPage.tsx.
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class LoginRequest(BaseModel):
    handle: str

    @field_validator("handle")
    @classmethod
    def _valid_handle(cls, value: str) -> str:
        value = value.strip()
        if not HANDLE_RE.fullmatch(value):
            raise ValueError(
                "Handle must be 3-20 characters: letters, numbers, or underscore."
            )
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    handle: str
    created_at: str
    email: str | None = None


class EmailLoginRequest(BaseModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class EmailVerifyRequest(EmailLoginRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


class SessionOut(UserOut):
    token: str
    expires_at: str


class CatalogueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    price: float
    dominant_color: str = ""
    style_tags: str
    description: str
    image_url: str
    product_url: str
    retailer: str = "ikea"
    external_product_id: str = ""
    currency: str = "USD"
    availability: str = "unknown"
    room_type: str = ""
    dimensions: dict = Field(default_factory=dict)
    materials: list[str] = Field(default_factory=list)
    affiliate_url: str = ""
    source_type: str = "ikea_snapshot"
    license_status: str = "unreviewed"
    fetched_at: str = ""
    last_verified_at: str = ""


class SubmissionCreate(BaseModel):
    budget: float
    style: DecorStyle
    notes: str = ""
    room_width_ft: float | None = None
    room_length_ft: float | None = None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    room_image_path: str
    budget: float
    style: DecorStyle
    notes: str = ""
    room_width_ft: float | None = None
    room_length_ft: float | None = None
    user_id: int | None = None


class RecommendedItemOut(BaseModel):
    """One line of the Stage 1 furniture recommendation."""

    item_id: int
    quantity: int
    placement: str = ""
    reason: str = ""


class RecommendationOut(BaseModel):
    """Stage 1 output. App-facing (drives image gen + persistence); not shown raw."""

    items: list[RecommendedItemOut] = []
    total_price: float = 0.0
    summary: str = ""


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    generated_image_path: str
    total_price: float
    item_ids: str
    created_at: datetime.datetime
    items: list[CatalogueItemOut] = []
    recommendation: RecommendationOut | None = None


class DesignOut(BaseModel):
    """A saved design: a submission joined to its generated suggestion."""

    model_config = ConfigDict(from_attributes=True)

    submission_id: int
    created_at: datetime.datetime
    style: DecorStyle
    budget: float
    room_image_path: str
    generated_image_path: str
    total_price: float
    items: list[CatalogueItemOut] = []
    recommendation: RecommendationOut | None = None
