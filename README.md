# Rankify — Image automation monorepo

This repository is split into a **Python API backend** and a **frontend** folder for the product demo UI. Each service has its own guide:

| Service | Documentation |
|---------|----------------|
| **Backend** | [`backend/README.md`](backend/README.md) — why, what, architecture, env, how to run (local, Docker, Streamlit), full HTTP API reference. |
| **Frontend** | [`frontend/README.md`](frontend/README.md) — purpose, planned UI, scaffold steps, how to run with the API, security notes. |

## Quick commands

**Frontend (API tester GUI)**

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** (set API base + `x-api-key` in the page). See [`frontend/README.md`](frontend/README.md).

**Backend (local)**

```bash
cd backend
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY and API_KEY
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9600
```

**Full stack (Docker Compose — backend + frontend + Postgres)**

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set API_KEY, GOOGLE_API_KEY, and/or OPENAI_API_KEY

docker compose up --build
```

| Service   | URL |
|-----------|-----|
| Frontend  | http://localhost:5173 (nginx proxies `/api` to the API) |
| API       | http://localhost:9600 |
| Swagger   | http://localhost:9600/docs |

In the UI **Settings**, set **x-api-key** to match `API_KEY` in `backend/.env` (leave API base URL empty — same-origin proxy).

**Backend only (Docker)**

```bash
docker build -f backend/Dockerfile -t rankify-image-api ./backend
docker run --env-file backend/.env -p 9600:9600 rankify-image-api
```

**Environment file:** keep `.env` under `backend/` (e.g. `backend/.env`) so `load_dotenv()`, Compose, and `docker run --env-file` all use the same paths for `assets/` and `generated-images/`. If you still have a `.env` in the repository root from an older layout, copy or move it to `backend/.env`.

## Workflow

1. Extend APIs in **`backend/`** — full reference: [`backend/README.md`](backend/README.md).
2. Build the demo in **`frontend/`** — full guide: [`frontend/README.md`](frontend/README.md).

Point the frontend at `http://localhost:9600` (or your deployed API URL) and send `x-api-key` on protected routes as documented in the backend README.
