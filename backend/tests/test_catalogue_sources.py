"""Protect existing designs, source identity, and the research/public boundary."""
import gzip
import io
import json
import sqlite3
import tarfile

import pytest
from fastapi.testclient import TestClient

from app import database
from app.catalogue_import import read_records
from app.database import db_session, init_db
from app.main import app
from app.services.catalogue_repository import ingest, search_catalogue
from app.services.catalogue_sources import AboAdapter, IkeaSnapshotAdapter, ProductRecord


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "catalogue.db")
    init_db()
    with db_session() as conn:
        yield conn


def product(**changes):
    return ProductRecord.model_validate({
        "retailer": "test_store", "external_product_id": "00042", "name": "Study desk",
        "category": "Desks", "price": 49, "styles": ["modern"],
        "source_type": "approved_feed", "license_status": "approved", **changes})


def test_legacy_migration_preserves_ids_and_records(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(database.SCHEMA)
        conn.execute("INSERT INTO catalogue_items (id,name,category,price) VALUES (42,'Old desk','Desks',39)")
        conn.execute("INSERT INTO submissions (id,created_at,room_image_path,budget,style) VALUES (1,'2026-01-01','room.jpg',100,'modern')")
        conn.execute("INSERT INTO suggestions (submission_id,generated_image_path,item_ids,created_at) VALUES (1,'result.jpg','42','2026-01-01')")
    monkeypatch.setattr(database, "DB_PATH", path)
    init_db()
    init_db()
    with db_session() as conn:
        item = search_catalogue(conn)[0]
        assert (item.id, item.external_product_id, item.retailer) == (42, "00000042", "ikea")
        assert conn.execute("SELECT item_ids FROM suggestions").fetchone()[0] == "42"
        assert item.availability == "unknown"
        assert item.fetched_at == ""  # Migration does not invent a verification date.


def test_source_identity_upsert_and_metadata(isolated_db):
    db = isolated_db
    ingest(db, [product(), product(retailer="other_store", price=30)])
    initial = search_catalogue(db)
    assert len(initial) == 2 and initial[0].id != initial[1].id
    original_id = next(p.id for p in initial if p.retailer == "test_store")
    ingest(db, [product(price=59, dimensions={"width": {"value": 90, "unit": "cm"}}, materials=["wood"])])
    updated = search_catalogue(db, retailer="test_store")[0]
    assert updated.id == original_id and updated.price == 59
    assert updated.dimensions["width"]["unit"] == "cm" and updated.materials == ["wood"]
    assert updated.fetched_at


def test_ikea_adapter_preserves_zero_padded_images(isolated_db):
    item = IkeaSnapshotAdapter().normalize({"product_id": "00000042", "name": "Desk", "type": "Desks", "price_usd": 40})
    ingest(isolated_db, [item])
    row = search_catalogue(isolated_db)[0]
    assert row.id == 42 and row.image_url == "/catalogue-images/00000042.jpg"


def test_public_retrieval_filters_price_stock_currency_and_exact_style(isolated_db):
    ingest(isolated_db, [product(), product(external_product_id="2", styles=["postmodern"]),
                        product(external_product_id="3", availability="out_of_stock"),
                        product(external_product_id="4", currency="EUR")])
    matches = search_catalogue(isolated_db, style="modern", currency="USD", max_price=50)
    assert [p.external_product_id for p in matches] == ["00042"]
    assert search_catalogue(isolated_db, max_price=20) == []
    assert search_catalogue(isolated_db, query="%") == []


def test_abo_is_internal_and_has_no_fake_price(isolated_db):
    record = AboAdapter().normalize({
        "item_id": "B_TEST", "item_name": [{"language_tag": "de_DE", "value": "Stuhl"},
        {"language_tag": "en_US", "value": "Research chair"}],
        "node": [{"node_name": "/Categories/Furniture/Chairs"}],
        "main_image_id": "image123", "material": [{"language_tag": "en_US", "value": "wood"}]})
    assert record.research_only and record.price is None
    assert record.image_url == "" and record.product_url == ""
    assert record.metadata["main_image_id"] == "image123"
    assert ingest(isolated_db, [record]) == {"catalogue": 0, "research": 1}
    ingest(isolated_db, [record])
    assert isolated_db.execute("SELECT COUNT(*) FROM research_products").fetchone()[0] == 1
    assert search_catalogue(isolated_db) == []
    assert AboAdapter().normalize({"item_id": "shoe", "item_name": "Shoe", "product_type": "SHOE"}) is None


@pytest.mark.parametrize("changes", [{"price": None}, {"license_status": "unreviewed"}])
def test_incomplete_public_records_rejected(isolated_db, changes):
    with pytest.raises(ValueError):
        ingest(isolated_db, [product(**changes)])


def test_failed_import_rolls_back_every_product(isolated_db):
    with pytest.raises(ValueError):
        with db_session() as db:
            ingest(db, [product(), product(external_product_id="2", price=None)])
    assert search_catalogue(isolated_db) == []


def test_abo_cannot_be_published_by_changing_research_flag(isolated_db):
    record = product(source_type="amazon_abo", research_only=False)
    assert ingest(isolated_db, [record]) == {"catalogue": 0, "research": 1}
    assert search_catalogue(isolated_db) == []


def test_official_tar_gzip_shards_are_read_without_extraction(tmp_path):
    archive_path = tmp_path / "listings.tar"
    data = gzip.compress((json.dumps({"item_id": "test"}) + "\n").encode())
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("../../listings/listings_0.json.gz")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    assert list(read_records(archive_path)) == [{"item_id": "test"}]
    assert list(tmp_path.iterdir()) == [archive_path]


def test_api_search_metadata_pagination_and_research_exclusion(isolated_db):
    ingest(isolated_db, [product(), product(external_product_id="2", name="Other desk"),
                        product(retailer="amazon", external_product_id="B_TEST", research_only=True)])
    isolated_db.commit()
    with TestClient(app) as client:
        response = client.get("/api/catalogue", params={"retailer": "test_store", "q": "desk", "limit": 1})
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["retailer"] == "test_store"
        assert client.get("/api/catalogue", params={"retailer": "amazon"}).json() == []
        assert client.get("/api/catalogue", params={"limit": 0}).status_code == 422
