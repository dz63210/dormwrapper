import io

from fastapi.testclient import TestClient
from PIL import Image

from app.database import init_db
from app.main import app
from app.seed_data import seed

# TestClient doesn't run the lifespan unless used as a context manager, so make
# sure the tables exist (and the catalogue is populated) before the first request.
init_db()
seed()

client = TestClient(app)


def _session(handle: str) -> dict:
    response = client.post("/api/login", json={"handle": handle})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def _png() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalogue_list() -> None:
    response = client.get("/api/catalogue")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list) and body
    item = body[0]
    assert {"id", "name", "category", "price", "style_tags", "image_url"} <= item.keys()


def test_catalogue_filter_by_style() -> None:
    response = client.get("/api/catalogue", params={"style": "scandinavian"})
    assert response.status_code == 200
    items = response.json()
    assert items and all("scandinavian" in i["style_tags"].split(",") for i in items)


def test_login_creates_guest_and_blocks_handle_impersonation() -> None:
    first = client.post("/api/login", json={"handle": "test_handle"})
    assert first.status_code == 200
    body = first.json()
    assert body["handle"] == "test_handle"
    assert set(body) == {"id", "handle", "created_at", "email", "token", "expires_at"}

    again = client.post("/api/login", json={"handle": "TEST_HANDLE"})  # case-insensitive
    assert again.status_code == 409


def test_login_rejects_bad_handle() -> None:
    assert client.post("/api/login", json={"handle": "no"}).status_code == 422
    assert client.post("/api/login", json={"handle": "has space"}).status_code == 422


def test_save_then_list_then_unsave_design() -> None:
    headers = _session("saver_user")

    def saved_ids(h: dict) -> list[int]:
        return [d["submission_id"] for d in client.get("/api/designs", headers=h).json()]

    sub = client.post(
        "/api/submissions",
        data={"budget": "300", "style": "scandinavian"},
        files={"image": ("room.png", _png(), "image/png")},
        headers=headers,
    ).json()
    client.post(f"/api/generate/{sub['id']}", headers=headers)

    assert sub["id"] not in saved_ids(headers)  # not saved yet

    saved = client.post(f"/api/designs/{sub['id']}/save", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["submission_id"] == sub["id"]
    assert sub["id"] in saved_ids(headers)

    # another user doesn't see this design
    assert sub["id"] not in saved_ids(_session("other_user"))

    assert client.delete(f"/api/designs/{sub['id']}/save", headers=headers).status_code == 200
    assert sub["id"] not in saved_ids(headers)


def test_save_unknown_submission_404() -> None:
    assert client.post("/api/designs/999999/save", headers=_session("unknown_sub")).status_code == 404


def test_generate_returns_recommendation_and_image() -> None:
    headers = _session("gen_user")
    sub = client.post(
        "/api/submissions",
        data={"budget": "400", "style": "modern", "notes": "need storage"},
        files={"image": ("room.png", _png(), "image/png")},
        headers=headers,
    ).json()

    res = client.post(f"/api/generate/{sub['id']}", headers=headers)
    assert res.status_code == 200
    body = res.json()

    # Stage 2: an image was produced (mock copies the photo through).
    assert body["generated_image_path"]

    # Stage 1: a structured recommendation is attached and within budget.
    rec = body["recommendation"]
    assert rec is not None
    assert rec["items"] and all(i["quantity"] >= 1 for i in rec["items"])
    assert rec["total_price"] <= 400
    assert body["total_price"] == rec["total_price"]

    # Re-POST is idempotent (no second pair of AI calls).
    again = client.post(f"/api/generate/{sub['id']}", headers=headers).json()
    assert again["id"] == body["id"]
    assert again["recommendation"]["total_price"] == rec["total_price"]


def test_saved_design_carries_recommendation() -> None:
    headers = _session("rec_saver")
    sub = client.post(
        "/api/submissions",
        data={"budget": "250", "style": "boho"},
        files={"image": ("room.png", _png(), "image/png")},
        headers=headers,
    ).json()
    client.post(f"/api/generate/{sub['id']}", headers=headers)
    client.post(f"/api/designs/{sub['id']}/save", headers=headers)

    design = client.get("/api/designs", headers=headers).json()[0]
    assert design["recommendation"] is not None
    assert "items" in design["recommendation"]
