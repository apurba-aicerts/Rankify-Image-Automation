# Rankify — Frontend (demo studio UI)

Vite + React app to exercise the backend: connect to an API, bootstrap a demo brand, manage workspaces, generate image variants, edit images, and browse brand-scoped galleries (signed image URLs).

## Why

- Quick manual QA without Swagger or curl.
- Same flows the product demo will use later.

## Run

**1. Backend** (from repo root or `backend/`):

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8750
```

**2. Frontend** (this folder):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually **http://localhost:8760**).

**3. In the UI**

1. Set **API base URL** (e.g. `http://localhost:8750`) and **x-api-key** (must match `API_KEY` in `backend/.env`).
2. Click **Save to browser** (stores in `localStorage` on this machine only).
3. **POST /api/brands/bootstrap-demo** once to create `demo-ai-certs`.
4. Adjust **Brand ID** if needed (default `demo-ai-certs`).
5. Open a workspace **Studio**, choose a model (Gemini / OpenAI / Imagen 4), select **Variants**, and click **Generate**.
6. **GET gallery** refreshes thumbnails (uses signed `url` from the API).

## Models

- **Gemini**: requires `GOOGLE_API_KEY`
- **Imagen 4**: requires `GOOGLE_API_KEY` (batch generation uses `number_of_images`)
- **OpenAI GPT Image**: requires `OPENAI_API_KEY` (logo-reference generation supported; multi-variant generation uses `n`)

The model list in the dropdown is loaded from `GET /api/models`.

## Docker (with backend)

From the **repository root** (see root `README.md`):

```bash
docker compose up --build
```

Open **http://localhost:8760**. The container nginx proxies `/api` and `/health` to the `backend` service. Set **x-api-key** in Settings to match `backend/.env` `API_KEY`; leave API base URL empty.

Build the image alone:

```bash
docker build -t rankify-frontend ./frontend
```

The nginx config expects a Docker network peer named `backend` (as in root `docker-compose.yml`).

## Build (static files)

```bash
npm run build
```

Output in `frontend/dist/` — serve with any static host; set API base URL to your deployed API (or build with `VITE_USE_PROXY=true` behind a reverse proxy that forwards `/api`).

## Project layout

```
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── pages/
    ├── components/
    ├── lib/
    └── styles/
```

## Notes

- **CORS:** backend allows all origins in dev; tighten for production.
- **Secrets:** the API key in the page is **only for local testing**; do not ship it in a public production SPA without a proper auth layer.
