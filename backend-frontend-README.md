# DormWrapper — App

A student submits a photo of their dorm room plus a budget and style preference,
and gets back a suggestion of IKEA furniture for the space (with a generated
image, stubbed for now).

## Stack

- **Frontend:** React + Vite + TypeScript, styled with Tailwind CSS
- **Backend:** Python 3.10+ + FastAPI
- **Database:** SQLite, raw `sqlite3` (no ORM) — schema in `backend/app/database.py`
- **Image generation:** stubbed behind a provider-agnostic interface
  (`backend/app/services/image_generation.py`) with a mock implementation, so the
  rest of the app can be built and tested before an AI image provider is chosen

## Data

The catalogue is a 300-item slice (15 per furniture type) of the 2025 IKEA US
dataset (`jeffreyszhou/ikea-us-products-2025`, Hugging Face). `catalog.json` at
the repo root is the source of truth; `backend/data/catalog.json` is the copy the
backend seeds from. `build_catalog.py` writes both; after hand-editing the root
copy, run:

```bash
python export_catalog.py     # catalog.json -> backend/data/catalog.json
```

Per-item product photos live at the repo root in `images/<product_id>.jpg` (one
real IKEA photo per item) and are served at `/catalogue-images/<product_id>.jpg`.

## Project layout

```
Dorm-Wrapper-/
├── catalog.json                   # the IKEA catalogue (source of truth, 300 items)
├── products-us.jsonl              # raw dataset (gitignored) — see build_catalog.py
├── build_catalog.py               # products-us.jsonl -> catalog.json (+ backend copy)
├── fetch_images.py                # downloads images/<product_id>.jpg from ikea.com
├── export_catalog.py              # catalog.json -> backend/data/catalog.json
├── images/                        # <product_id>.jpg per catalogue item
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, CORS, private media + /catalogue-images
│   │   ├── config.py              # env-based settings
│   │   ├── database.py            # raw sqlite3 connection + schema
│   │   ├── models.py              # CatalogueItem dataclass + DecorStyle enum
│   │   ├── schemas.py             # Pydantic request/response models
│   │   ├── seed_data.py           # loads data/catalog.json into SQLite
│   │   ├── routers/
│   │   │   ├── auth.py            # guest creation, bearer sessions, /me and /logout
│   │   │   ├── catalogue.py       # GET  /api/catalogue  (?style= &category= &max_price=)
│   │   │   ├── submissions.py     # POST /api/submissions, GET /api/submissions/{id}
│   │   │   ├── generate.py        # POST /api/generate/{submission_id}
│   │   │   └── designs.py         # GET /api/designs, POST/DELETE /api/designs/{id}/save
│   │   └── services/
│   │       └── image_generation.py  # ImageGenerator interface + Mock/Gemini/Replicate impls
│   ├── data/
│   │   └── catalog.json           # IKEA catalogue (300 items), from export_catalog.py
│   ├── tests/
│   │   └── test_health.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── api/client.ts          # fetch wrapper for the backend API
    │   ├── context/UserContext.tsx
    │   ├── pages/                 # HomePage, LoginPage, DesignPage
    │   ├── components/
    │   │   ├── UploadForm.tsx     # photo + budget slider + style picker + notes
    │   │   └── ResultView.tsx     # generated image + suggested item list
    │   └── types.ts
    ├── tailwind.config.js
    └── .env.example
```

## How it fits together

1. User enters an email → `POST /api/auth/request-code`, then verifies the delivered code → `POST /api/auth/verify-code`. A private token authenticates subsequent requests. Returning users recover saved designs. Follow [EMAIL_LOGIN_SETUP.md](EMAIL_LOGIN_SETUP.md) for Supabase and SMTP setup; guest creation is disabled by default.
2. `UploadForm` (photo, budget, style, notes) → `POST /api/submissions` stores the
   photo on disk and a row in SQLite.
3. `POST /api/generate/{submission_id}` → backend filters catalogue items by the
   submission's style, the mock generator greedily fills the budget, and copies
   the original photo as a placeholder "generated" image.
4. `ResultView` fetches the private generated image with the session token and renders it alongside the suggested IKEA items.
5. `POST /api/designs/{submission_id}/save` marks a design saved; `HomePage`
   lists the current user's saved designs.

## Running locally

### Backend  (needs Python 3.10+)

```bash
cd backend
python3 -m venv .venv           # or: uv venv --python 3.12 .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed_data         # loads backend/data/catalog.json into SQLite
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs. Delete `data/app.db` to reseed.

Tests: `pip install -r requirements-dev.txt && python -m pytest`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

App at http://localhost:5173

## Next steps (not built yet)

- **Real image generation:** `IMAGE_GEN_PROVIDER=gemini` wires up Google's
  `gemini-3.1-flash-lite-image` (needs `GEMINI_API_KEY`); `mock` just copies the
  photo. The Replicate stub in `image_generation.py` is left for another provider.
- **Better matching:** matching is still a style filter + greedy budget fill (no
  per-category "room package"). The dataset has no dimensions, so there is no
  room-fit check.
- **Show product photos:** items carry an `image_url` (`/catalogue-images/<product_id>.jpg`)
  that no component renders yet.
- **Persistent storage:** move uploaded/generated images off local disk before
  deploying anywhere non-local.
