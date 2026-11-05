# DormWrapper

DormWrapper is a full-stack product recommendation app for students furnishing a dorm or first apartment. A user uploads a room photo, chooses a budget and design style, and receives a curated set of IKEA furniture recommendations.

This repository is a personal portfolio copy of a collaborative course project. The original team included Lingkai Shen, Khuslen Khosbayar, Palak Katiyar, and Doreen Zheng.

## Why it is interesting

- Turns an open-ended room-design problem into a guided recommendation flow.
- Combines image upload, structured user preferences, catalogue filtering, and AI-ready generation interfaces.
- Stores user sessions and saved designs behind authenticated API routes.
- Uses a provider-agnostic design so recommendation and image-generation backends can be swapped without rewriting the product flow.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, Pydantic
- **Data:** SQLite and a curated IKEA product catalogue
- **Testing:** pytest and FastAPI test utilities
- **AI integrations:** configurable recommendation and image-generation providers, with deterministic mock providers for local development

## How it works

1. The user verifies an email and receives a private session.
2. The user submits a room photo, budget, style, and optional notes.
3. The API stores the submission and filters catalogue items by style and price.
4. A recommendation service selects a room package within budget.
5. The frontend displays the generated design and recommended products.
6. Users can save designs and return to them later.

## My contribution

This portfolio copy is intended to document my work on the project. Before publishing, I will add a concise contribution summary covering the specific frontend, backend, data, testing, or product work I owned.

## Repository layout

```text
backend/    FastAPI application, services, catalogue ingestion, auth, and tests
frontend/   React/Vite client and user-facing design flow
images/     Catalogue product images used by the local demo
catalog.json
            Curated product catalogue used to seed the backend
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
