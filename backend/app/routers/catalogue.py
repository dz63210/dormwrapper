"""Read-only product search across the public catalog."""
import sqlite3

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.models import CatalogueItem
from app.schemas import CatalogueItemOut
from app.services.catalogue_repository import search_catalogue

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])


@router.get("", response_model=list[CatalogueItemOut])
def list_catalogue_items(
    style: str | None = None,
    category: str | None = None,
    max_price: float | None = Query(default=None, ge=0),
    retailer: str | None = None,
    q: str | None = Query(default=None, max_length=200),
    currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
) -> list[CatalogueItem]:
    return search_catalogue(db, style=style, category=category, max_price=max_price,
                            retailer=retailer, query=q, currency=currency,
                            limit=limit, offset=offset)
