"""One-off script to load the IKEA catalogue into the database.

Run with:  python -m app.seed_data

Reads data/catalog.json through the IKEA source adapter. Adds missing products
without overwriting existing records. Use app.catalogue_import for refreshes.
"""
import json
from pathlib import Path

from app.config import settings
from app.database import db_session, init_db
from app.services.catalogue_repository import ingest
from app.services.catalogue_sources import IkeaSnapshotAdapter

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BACKEND_DIR / settings.catalogue_data_file

COLUMNS = (
    "id", "name", "category", "price",
    "dominant_color", "style_tags", "description",
    "image_url", "product_url",
)


def _to_row(item: dict) -> tuple:
    pid = item["product_id"]
    return (
        int(pid),
        item["name"],
        item["type"],
        item["price_usd"],
        item.get("dominant_color", ""),
        ",".join(item.get("styles", [])),
        item.get("description", ""),
        f"/catalogue-images/{pid}.jpg",
        item.get("product_url", ""),
    )


def seed() -> None:
    init_db()
    with db_session() as conn:
        existing = {row[0] for row in conn.execute(
            "SELECT external_product_id FROM catalogue_items WHERE retailer='ikea'")}

        with open(DATA_FILE, encoding="utf-8") as f:
            items = json.load(f)

        records = (item for item in IkeaSnapshotAdapter().records(iter(items))
                   if item.external_product_id not in existing)
        counts = ingest(conn, records)
        print(f"Added {counts['catalogue']} IKEA products; existing records preserved.")


if __name__ == "__main__":
    seed()
