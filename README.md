# DormWrapper

DormWrapper is a full-stack product recommendation app for students furnishing a dorm or first apartment. A user uploads a room photo, chooses a budget and design style, and receives a curated set of IKEA furniture recommendations.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, Pydantic
- **Data:** SQLite and a curated IKEA product catalogue
- **Testing:** pytest and FastAPI test utilities
- **AI integrations:** configurable recommendation and image-generation providers, with deterministic mock providers for local development

## How it works

1. The user chooses a username and starts a local session.
2. The user submits a room photo, budget, style, and optional notes.
3. The API stores the submission and filters catalogue items by style and price.
4. A recommendation service selects a room package within budget.
5. The frontend displays the generated design and recommended products.
6. Users can save designs and return to them later.

## Repository layout

```text
frontend/              React and Vite client
frontend/src/pages/    Sign-in, home, and room design screens
backend/               FastAPI application, catalogue ingestion, and tests
backend/app/services/  Furniture recommendations and room image generation
images/                Catalogue product photos used in the demo
catalog.json           Curated product data used to seed the backend
```

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed_data
uvicorn app.main:app --reload --port 8000
```

For the local demo, set `ALLOW_GUEST_LOGIN=true` in `backend/.env` before starting the API. Use a fresh username for each new session. A username alone cannot recover a previous session.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend runs at `http://localhost:5173`; the API runs at `http://localhost:8000`.

Run backend tests with:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

## Portfolio notes

- Secrets and local runtime files are excluded from version control.
- The default local configuration uses deterministic mock providers, so the app can be explored without paid API keys.
- Production email authentication and AI providers require environment-specific configuration; see [EMAIL_LOGIN_SETUP.md](EMAIL_LOGIN_SETUP.md) and the `.env.example` files.

## Future improvements

- Add room-dimension and per-category constraints to improve room fit.
- Render product photos directly in recommendation cards.
- Add a deployed demo with managed storage for uploaded images.
- Add analytics for saved items and recommendation quality.
