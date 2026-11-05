"""Shared data types (no ORM).

The database is raw sqlite3 (see ``app/database.py``); query results come back
as ``sqlite3.Row``. ``CatalogueItem`` is a lightweight dataclass the services
layer and the Pydantic response models read by attribute.
"""
from __future__ import annotations

import enum
import json
import sqlite3
from dataclasses import dataclass, field, fields


class DecorStyle(str, enum.Enum):
    """The style tags carried by catalogue items (see catalog.json `styles`)."""

    SCANDINAVIAN = "scandinavian"
    MINIMALIST = "minimalist"
    MODERN = "modern"
    INDUSTRIAL = "industrial"
    MID_CENTURY = "mid-century"
    BOHO = "boho"
    TRADITIONAL = "traditional"


@dataclass
class CatalogueItem:
    """A retailer-neutral product; the integer ID remains stable for saved designs."""

    id: int
    name: str
    category: str
    price: float
    dominant_color: str = ""
    style_tags: str = ""  # comma-separated DecorStyle values
    description: str = ""
    image_url: str = ""  # served path, e.g. /catalogue-images/60214159.jpg
    product_url: str = ""
    retailer: str = "ikea"
    external_product_id: str = ""
    currency: str = "USD"
    availability: str = "unknown"
    room_type: str = ""
    dimensions: dict = field(default_factory=dict)
    materials: list[str] = field(default_factory=list)
    affiliate_url: str = ""
    source_type: str = "ikea_snapshot"
    license_status: str = "unreviewed"
    fetched_at: str = ""
    last_verified_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CatalogueItem":
        values = dict(row)
        values["dimensions"] = json.loads(values.pop("dimensions_json", "{}"))
        values["materials"] = json.loads(values.pop("materials_json", "[]"))
        names = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in values.items() if key in names})
