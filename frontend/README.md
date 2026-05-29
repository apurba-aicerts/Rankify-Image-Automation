# Rankify — Frontend (API tester GUI)

Small **Vite + vanilla JS** app to exercise the backend: health check, bootstrap demo brand, list brands, generate slides, and show the per-brand gallery (signed image URLs).

## Why

- Quick manual QA without Swagger or curl.
- Same flows the product demo will use later.

## Run

**1. Backend** (from repo root or `backend/`):

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 9600
```

**2. Frontend** (this folder):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually **http://localhost:5173**).

**3. In the UI**

1. Set **API base URL** (e.g. `http://localhost:9600`) and **x-api-key** (must match `API_KEY` in `backend/.env`).
2. Click **Save to browser** (stores in `localStorage` on this machine only).
3. **POST /api/brands/bootstrap-demo** once to create `demo-ai-certs`.
4. Adjust **Brand ID** if needed (default `demo-ai-certs`).
5. Edit post content, then **POST /api/generate** (calls Gemini; needs `GOOGLE_API_KEY` on the server).
6. **GET gallery** refreshes thumbnails (uses signed `url` from the API).

## Build (static files)

```bash
npm run build
```

Output in `frontend/dist/` — serve with any static host; set API base URL to your deployed API.

## Project layout

```
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js      # fetch helpers + UI wiring
    └── style.css
```

## Notes

- **CORS:** backend allows all origins in dev; tighten for production.
- **Secrets:** the API key in the page is **only for local testing**; do not ship it in a public production SPA without a proper auth layer.
