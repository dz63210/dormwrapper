"""Catalog persistence and retrieval shared by source adapters and routes."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from app.database import utcnow_iso
from app.models import CatalogueItem
from app.services.catalogue_sources import ProductRecord


def validate_destination(record: ProductRecord) -> str:
    if record.research_only or record.source_type == "amazon_abo":
        return "research"
    if record.price is None:
        raise ValueError(f"Public product {record.external_product_id} needs a price")
    legacy_ikea = record.retailer == "ikea" and record.source_type == "ikea_snapshot"
    if not legacy_ikea and record.license_status != "approved":
        raise ValueError("New public sources must have license_status='approved'")
    return "catalogue"


def ingest(db: sqlite3.Connection, records: Iterable[ProductRecord]) -> dict[str, int]:
    counts = {"catalogue": 0, "research": 0}
    for record in records:
        record = record.model_copy(update={"fetched_at": record.fetched_at or utcnow_iso()})
        if validate_destination(record) == "research":
            db.execute("""INSERT INTO research_products VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(retailer, external_product_id) DO UPDATE SET
                name=excluded.name, category=excluded.category,
                source_type=excluded.source_type, normalized_json=excluded.normalized_json""",
                (record.retailer, record.external_product_id, record.name, record.category,
                 record.source_type, record.model_dump_json()))
            counts["research"] += 1
            continue
        values = {
            "name": record.name, "category": record.category, "price": record.price,
            "dominant_color": record.dominant_color, "style_tags": ",".join(record.styles),
            "description": record.description, "image_url": record.image_url,
            "product_url": record.product_url, "retailer": record.retailer,
            "external_product_id": record.external_product_id, "currency": record.currency,
            "availability": record.availability, "room_type": record.room_type,
            "dimensions_json": json.dumps(record.dimensions),
            "materials_json": json.dumps(record.materials), "affiliate_url": record.affiliate_url,
            "source_type": record.source_type, "license_status": record.license_status,
            "fetched_at": record.fetched_at, "last_verified_at": record.last_verified_at}
        existing = db.execute("SELECT id FROM catalogue_items WHERE retailer=? AND external_product_id=?",
                              (record.retailer, record.external_product_id)).fetchone()
        if existing:
            db.execute(f"UPDATE catalogue_items SET {', '.join(k + '=?' for k in values)} WHERE id=?",
                       (*values.values(), existing["id"]))
        else:
            if record.source_type == "ikea_snapshot" and record.external_product_id.isdigit():
                legacy_id = int(record.external_product_id)
                if not db.execute("SELECT 1 FROM catalogue_items WHERE id=?", (legacy_id,)).fetchone():
                    values["id"] = legacy_id
            db.execute(f"INSERT INTO catalogue_items ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
                       tuple(values.values()))
        counts["catalogue"] += 1
    return counts


def search_catalogue(db: sqlite3.Connection, *, style: str | None = None,
                     category: str | None = None, max_price: float | None = None,
                     retailer: str | None = None, query: str | None = None,
                     currency: str | None = None, limit: int | None = None,
                     offset: int = 0) -> list[CatalogueItem]:
    clauses = ["source_type != 'amazon_abo'", "availability NOT IN ('out_of_stock', 'discontinued')"]
    params: list = []
    for column, value in (("category", category), ("retailer", retailer), ("currency", currency)):
        if value:
            clauses.append(f"{column}=?")
            params.append(value)
    if style:
        clauses.append("instr(',' || style_tags || ',', ',' || ? || ',') > 0")
        params.append(style)
    if max_price is not None:
        clauses.append("price <= ?")
        params.append(max_price)
    if query:
        clauses.append("instr(lower(name || ' ' || description || ' ' || category), lower(?)) > 0")
        params.append(query)
    sql = "SELECT * FROM catalogue_items WHERE " + " AND ".join(clauses) + " ORDER BY category, name, id"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend((limit, offset))
    return [CatalogueItem.from_row(row) for row in db.execute(sql, params)]
