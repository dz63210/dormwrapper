"""Source adapters produce one normalized shape for snapshots, feeds, and APIs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ProductRecord(BaseModel):
    retailer: str = Field(min_length=1)
    external_product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    dominant_color: str = ""
    styles: list[str] = Field(default_factory=list)
    description: str = ""
    image_url: str = ""
    product_url: str = ""
    affiliate_url: str = ""
    availability: Literal["unknown", "in_stock", "out_of_stock", "discontinued"] = "unknown"
    room_type: str = ""
    dimensions: dict = Field(default_factory=dict)
    materials: list[str] = Field(default_factory=list)
    source_type: str = Field(min_length=1)
    license_status: str = "unreviewed"
    fetched_at: str = ""
    last_verified_at: str = ""
    research_only: bool = False
    metadata: dict = Field(default_factory=dict)

    @field_validator("retailer", "external_product_id", "name", "category", "source_type")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Required product fields cannot be blank")
        return value


class SourceAdapter(ABC):
    """API adapters can page results and yield the same ProductRecord."""
    @abstractmethod
    def normalize(self, raw: dict) -> ProductRecord | None:
        raise NotImplementedError

    def records(self, rows: Iterator[dict]) -> Iterator[ProductRecord]:
        for raw in rows:
            record = self.normalize(raw)
            if record is not None:
                yield record


class IkeaSnapshotAdapter(SourceAdapter):
    def normalize(self, raw: dict) -> ProductRecord:
        pid = str(raw["product_id"]).zfill(8)
        return ProductRecord(
            retailer="ikea", external_product_id=pid,
            name=raw["name"], category=raw["type"], price=raw["price_usd"],
            dominant_color=raw.get("dominant_color", ""), styles=raw.get("styles", []),
            description=raw.get("description", ""),
            image_url=f"/catalogue-images/{pid}.jpg", product_url=raw.get("product_url", ""),
            source_type="ikea_snapshot", license_status="unreviewed",
            dimensions=raw.get("dimensions", {}), materials=raw.get("materials", []))


class NormalizedFeedAdapter(SourceAdapter):
    """For permitted feeds or API results already mapped to our schema."""
    def normalize(self, raw: dict) -> ProductRecord:
        record = ProductRecord.model_validate(raw)
        if record.source_type == "amazon_abo":
            record.research_only = True
        return record


def _english_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    entries = [entry for entry in value if isinstance(entry, dict) and entry.get("value") is not None
               and (not entry.get("language_tag") or entry["language_tag"].startswith("en"))]
    entries.sort(key=lambda entry: entry.get("language_tag") != "en_US")
    return [str(entry["value"]) for entry in entries]


class AboAdapter(SourceAdapter):
    """Official ABO listings; no live prices, stock, or image URLs are invented."""
    def normalize(self, raw: dict) -> ProductRecord | None:
        names = _english_values(raw.get("item_name"))
        nodes = [n["node_name"] for n in (raw.get("node") or [])
                 if isinstance(n, dict) and isinstance(n.get("node_name"), str)]
        types = _english_values(raw.get("product_type"))
        furniture_types = {"SOFA", "CHAIR", "TABLE", "DESK", "BED", "CABINET",
                           "BOOKCASE", "SHELF", "OTTOMAN", "DRESSER", "NIGHTSTAND",
                           "STOOL", "BENCH", "FURNITURE"}
        if not names or not (any("furniture" in n.lower() for n in nodes)
                             or any(t.upper() in furniture_types for t in types)):
            return None
        return self.make_record(raw, names[0], next(
            (n.rsplit("/", 1)[-1] for n in nodes if "furniture" in n.lower()),
            types[0] if types else "Furniture"))

    @staticmethod
    def make_record(raw: dict, name: str, category: str) -> ProductRecord:
        """Shared mapping for furniture and deliberately selected dorm accessories."""
        return ProductRecord(
            retailer="amazon", external_product_id=raw["item_id"], name=name,
            category=category,
            price=None, source_type="amazon_abo", license_status="review_required",
            research_only=True,
            dominant_color=next(iter(_english_values(raw.get("color"))), ""),
            styles=_english_values(raw.get("style")), materials=_english_values(raw.get("material")),
            dimensions=raw.get("item_dimensions") or {},
            description=" ".join(_english_values(raw.get("bullet_point"))),
            metadata={key: raw[key] for key in
                      ("domain_name", "main_image_id", "other_image_id", "3dmodel_id", "brand")
                      if key in raw})


ADAPTERS = {"ikea": IkeaSnapshotAdapter, "feed": NormalizedFeedAdapter, "abo": AboAdapter}
