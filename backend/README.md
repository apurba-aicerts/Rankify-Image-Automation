# Rankify — Backend service (API)

This backend is **multi-brand**: each tenant has an isolated configuration (JSON + assets under `data/brands/<brand_id>/`) and its own gallery (`generated-images/<brand_id>/`). Image generation reads prompts from that configuration so the pipeline stays **brand-agnostic**—onboarding a new brand does not require code changes.

**Quick path to first generate**

1. `POST /api/brands/bootstrap-demo` (creates `demo-ai-certs` from the packaged template).
2. Optionally `POST /api/brands/demo-ai-certs/assets/logo` to upload a logo; otherwise the server falls back to `assets/default_logo.jpg`.
3. `POST /api/generate` with JSON body including `"brand_id": "demo-ai-certs"` (see API section below).

Legacy unscoped routes `GET /api/gallery` and `/api/gallery/raw/...` return **410 Gone**; use **`/api/brands/{brand_id}/gallery`** instead.

---

This folder is the **Rankify image backend**: a standalone HTTP API that turns structured marketing copy + a brand logo into slide images using **Gemini**, **OpenAI GPT Image**, or **Google Imagen 4**, stores them on **local disk**, and exposes **gallery** and **signed URL** helpers for a separate frontend.

---

## Why this service exists

- **Speed:** Marketing teams should not depend on manual design tools for every carousel variant.
- **Consistency:** Generation is driven by a fixed **brand governance** prompt plus structured post text so layouts stay on-brand.
- **Separation of concerns:** The **frontend** (demo app in `../frontend/`) only talks HTTP; all provider keys (Gemini / Imagen / OpenAI) and file storage stay on the server.
- **No cloud storage in this phase:** There is **no AWS/S3** dependency—images live under `generated-images/` (or `LOCAL_IMAGE_STORAGE_DIR`) so you can run and demo without cloud credentials.

---

## What this service does

| Capability | Description |
|------------|-------------|
| **Brand onboarding** | `GET/POST /api/brands`, `POST /api/brands/ai-draft` (OpenAI draft; needs `OPENAI_API_KEY`), `PUT /api/brands/{id}`, `POST .../assets/logo`, `POST /api/brands/bootstrap-demo`. |
| **Slide generation** | `POST /api/generate` (JSON + `brand_id`) and `POST /api/generate-with-logo` (multipart + `brand_id`). |
| **Per-brand gallery** | `GET/DELETE /api/brands/{brand_id}/gallery/...`, signed raw `GET /api/brands/{brand_id}/gallery/raw/{filename}`. |
| **Model catalog** | `GET /api/models` and `GET /api/image-sizes` (unchanged). |
| **Social copy (OpenAI)** | `POST /api/brands/{brand_id}/text/social-copy` (caption + hashtags; optional `image_filename` for vision). Same body on `.../text/captions` and `.../text/hashtags` (returns full object). Requires `OPENAI_API_KEY`. |

---

## How requests flow (high level)

1. Client sends `x-api-key` + post **content** (and optional logo) to a generate endpoint.
2. **`main.py`** validates input, loads **``BrandConfiguration``** from ``data/brands/<brand_id>/brand.json``.
3. **`generation/prompt_builder.py`** builds governance + slide prompts from that config.
4. **`generation/slide_pipeline.py`** calls the selected provider and writes into ``generated-images/<brand_id>/``.
5. Responses include signed URLs via **`gallery_url_signing.py`** (tenant-scoped HMAC: ``brand_id:filename:exp``).

---

## Tech stack

- **Python 3.12** (see `Dockerfile`)
- **FastAPI** + **Uvicorn** — HTTP server (`main:app`)
- **Google Gemini** — `generateContent` with image modality (`gemini_slide_client.py`)
- **Google Imagen 4** — batch image generation via `google-genai` SDK (optional; model ids `imagen-4.0-*-generate-001`)
- **OpenAI GPT Image** — image generation + edits via the OpenAI Images API (logo-reference generation supported)
- **Pillow** — logo loading and image handling
- **Optional:** **Streamlit** — local slide lab (`streamlit_slide_lab.py`; install Streamlit separately if you use it)

---

## Code layout

```
backend/
├── main.py                      # HTTP routes (brands, generate, gallery)
├── brands/
│   ├── schemas.py               # BrandConfiguration + onboarding payloads
│   ├── repository.py            # Filesystem persistence (data/brands/)
│   ├── demo_brand_template.py   # Packaged demo-ai-certs BrandConfiguration
│   └── demo_ai_certs_governance.py  # Long governance text for that seed only
├── generation/
│   ├── prompt_builder.py        # Brand-agnostic prompt assembly
│   ├── slide_pipeline.py        # Provider + gallery orchestration (Gemini / OpenAI / Imagen)
│   ├── openai_social_copy_service.py  # OpenAI caption + hashtags (optional vision on gallery file)
│   └── text_stubs.py            # Legacy stubs / prompt helpers
├── gemini_slide_client.py       # Gemini REST image calls
├── generation/image_providers/  # Provider dispatch + model catalog (Gemini/OpenAI/Imagen)
├── gallery_local_store.py       # Per-brand gallery directories
├── gallery_url_signing.py       # HMAC URLs for .../gallery/raw/...
├── streamlit_slide_lab.py       # Optional local Streamlit UI (same prompts as API)
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── assets/                      # Fallback default_logo.jpg
```

| Module | Responsibility |
|--------|----------------|
| `main.py` | HTTP surface: brands CRUD, bootstrap, generate, brand gallery, CORS, TTL task. |
| `brands/*` | Pydantic config model, JSON repository, demo seed content. |
| `generation/prompt_builder.py` | Builds system + user prompts from `BrandConfiguration` (governance body, optional layout/CTA/visual/avoid modules, structured JSON summary). |
| `generation/slide_pipeline.py` | Validates model params, runs selected provider, saves under `generated-images/<brand_id>/`. |
| `generation/openai_social_copy_service.py` | OpenAI structured caption + hashtags from brand config + studio brief; optional gallery image (vision). |
| `generation/text_stubs.py` | Legacy helpers / doc hooks for text pipelines. |
| `gemini_slide_client.py` | Low-level `generateContent` (IMAGE modality). |
| `gallery_local_store.py` | Per-brand paths, list/delete, recursive TTL purge. |
| `gallery_url_signing.py` | Tenant-aware signed URLs for raw image bytes. |

---

## Configuration (`.env`)

Create a file named **`.env` in this `backend/` directory** (same folder as `main.py`) so `load_dotenv()` and relative paths (`assets/`, `generated-images/`) resolve correctly.

```bash
cd backend
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes (for Google models) | Used for Gemini and Imagen 4 models. |
| `API_KEY` | Yes (for protected routes) | Shared secret; clients send `x-api-key: <value>`. Also used to sign gallery image URLs. |
| `OPENAI_API_KEY` | No | OpenAI: image models (`openai:gpt-image-*` on `POST /api/generate`), brand AI draft, and social copy. If empty, OpenAI-backed routes return 503. |
| `IMAGE_TTL_HOURS` | No | Gallery history retention: delete generated images older than this many hours (default `720` = 30 days). |
| `PUBLIC_BASE_URL` | No | Public origin for signed URLs if the API sits behind a reverse proxy (no trailing slash). |
| `LOCAL_IMAGE_STORAGE_DIR` | No | Root for raster output (default `generated-images/`). Actual files live in `<root>/<brand_id>/`. |
| `BRAND_DATA_DIR` | No | Root for brand JSON + assets (default `data/brands`). |

---

## How to run everything

### A. HTTP API — local (development)

From **repository root**:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9600
```

- API base: `http://localhost:9600`
- Open **Swagger:** `http://localhost:9600/docs`
- If you previously kept `.env` at the **repo root**, copy it here: `backend/.env` (the server is started with cwd `backend/`).

### B. HTTP API — Docker

**Full stack** (API + React UI + Postgres) from **repository root**:

```bash
cp .env.example .env   # if needed
docker compose up --build
```

API on **http://localhost:9600**; UI on **http://localhost:5173**. Compose sets `DATABASE_URL` to the `postgres` service and mounts volumes for `generated-images/` and `data/`.

**API image only** (build context must be `backend/`):

```bash
docker build -f backend/Dockerfile -t rankify-image-api ./backend
docker run --env-file backend/.env -p 9600:9600 rankify-image-api
```

**Postgres only** (local dev):

```bash
docker compose up -d
```

### C. Streamlit slide lab (optional)

Does **not** start the FastAPI server; it calls Gemini directly for local experiments.

```bash
cd backend
pip install streamlit
streamlit run streamlit_slide_lab.py
```

### D. Smoke test the API

```bash
curl -s http://localhost:9600/health
```

---

## Authentication

**Authenticated API requests** (everything except `GET /health` and **signed** `GET /api/brands/{brand_id}/gallery/raw/...` with valid `exp` + `sig`) must include this header:

```
x-api-key: <your API_KEY from .env>
```

Missing or invalid keys return `401 Unauthorized`.

---

## API Endpoints

### Health Check

```
GET /health
```

No authentication required. Returns server status and storage path.

**Response:**
```json
{
  "status": "ok",
  "storage": "local",
  "storage_dir": "/app/generated-images",
  "timestamp": "2026-02-20T16:02:17.000000+00:00"
}
```

---

### List Available Models

```
GET /api/models
```

Returns all supported image models the frontend can use in the generate endpoint (Gemini / OpenAI / Imagen), along with pricing hints and capability flags.

**Headers:**
```
x-api-key: <your-api-key>
```

**Response:**
```json
{
  "models": [
    {
      "model_name": "gemini-3-pro-image-preview",
      "provider": "gemini",
      "label": "Gemini 3 Pro Image",
      "supports_image_size": true,
      "supports_generate": true,
      "supports_edit": true,
      "pricing": { "1K": 0.134, "2K": 0.134, "4K": 0.24 }
    },
    {
      "model_name": "gemini-2.5-flash-image",
      "provider": "gemini",
      "label": "Gemini 2.5 Flash Image",
      "supports_image_size": false,
      "supports_generate": true,
      "supports_edit": true,
      "price_per_image_usd": 0.039
    },
    {
      "model_name": "openai:gpt-image-1-mini",
      "provider": "openai",
      "label": "OpenAI GPT Image 1 Mini",
      "supports_image_size": false,
      "supports_generate": true,
      "supports_edit": true
    },
    {
      "model_name": "imagen-4.0-fast-generate-001",
      "provider": "imagen",
      "label": "Imagen 4 Fast",
      "supports_image_size": false,
      "supports_generate": true,
      "supports_edit": false
    }
  ]
}
```

---

### List Available Image Sizes

```
GET /api/image-sizes
```

Returns supported image resolutions and aspect ratios.

**Headers:**
```
x-api-key: <your-api-key>
```

**Response:**
```json
{
  "image_sizes": ["1K", "2K", "4K"],
  "note": "Image size is used by some models (Gemini Pro, OpenAI GPT Image). For other models it may be ignored or chosen automatically.",
  "aspect_ratios": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
}
```

---

### Brands — list / create / bootstrap

```
GET /api/brands
POST /api/brands
POST /api/brands/ai-draft
POST /api/brands/bootstrap-demo
GET /api/brands/{brand_id}
PUT /api/brands/{brand_id}
DELETE /api/brands/{brand_id}
POST /api/brands/{brand_id}/assets/logo   (multipart file)
```

`POST /api/brands` accepts a JSON body matching **`BrandCreatePayload`**: required `brand_id` (slug), `display_name`, and nested `generation.governance_prompt_template` (long system prompt). Optional sections cover colors, typography, voice, social defaults, platform hints, content themes, and text preferences (used when caption/hashtag pipelines exist).

`POST /api/brands/ai-draft` accepts **`BrandAiDraftRequest`**: `brand_materials` (long unstructured paste), optional `brand_id` (if omitted the server assigns a UUID slug), and optional `model_name` (default `gpt-4o-2024-08-06`). Requires **`OPENAI_API_KEY`** in the server environment. Returns **`BrandAiDraftResponse`** with a validated `draft` object — same shape as `POST /api/brands` — for human review before create.

---

### Generate Images (JSON)

```
POST /api/generate
```

Uses the **saved brand configuration** and logo (`data/brands/<brand_id>/assets/` or fallback `assets/default_logo.jpg`). Each returned `url` is a **tenant-scoped** signed link.

`num_images` returns multiple slide variants. For OpenAI and Imagen 4 models, the server batches multiple images in a single upstream request when possible. For Gemini native models, the server may make multiple upstream calls.

**Request Body (example):**
```json
{
  "brand_id": "demo-ai-certs",
  "content": "TITLE:\\nHello\\n\\nSUBTITLE:\\nWorld\\n\\nBODY:\\nBody.\\n\\nCTA BUTTON:\\nGo",
  "model_name": "gemini-3-pro-image-preview",
  "num_images": 1,
  "aspect_ratio": "1:1",
  "image_size": "2K"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `brand_id` | **yes** | Existing brand slug (see `GET /api/brands`). |
| `content` | **yes** | Structured post copy. |
| `model_name` / `num_images` / `aspect_ratio` / `image_size` | no | Same semantics as before. |

**Response `url` example:**  
`http://localhost:9600/api/brands/demo-ai-certs/gallery/raw/rankify_slide_....png?exp=...&sig=...`

**Signature:** HMAC-SHA256 over `brand_id:filename:exp` with `API_KEY`.

---

### Generate Images with Custom Logo (Multipart)

```
POST /api/generate-with-logo
```

**Required form field:** `brand_id`. Other fields unchanged; optional `logo` file overrides the stored brand logo **for that request only**.

---

### Gallery (per brand)

```
GET    /api/brands/{brand_id}/gallery
GET    /api/brands/{brand_id}/gallery/{filename}   → 307 to signed raw URL
GET    /api/brands/{brand_id}/gallery/raw/{filename}?exp=&sig=
DELETE /api/brands/{brand_id}/gallery/{filename}
```

`storage_path` values look like `generated-images/<brand_id>/<filename>`.

---

## Image Lifecycle

- Renders to a temp file, then moves into **`generated-images/<brand_id>/`**.
- Background TTL purge walks **each brand subdirectory** every **15 minutes**.
- Manual delete via **brand-scoped** `DELETE` route above.
- Legacy **`/api/gallery*`** routes return **410 Gone**.

---

## Interactive API Docs

Once the server is running, visit:

- **Swagger UI:** [http://localhost:9600/docs](http://localhost:9600/docs)
- **ReDoc:** [http://localhost:9600/redoc](http://localhost:9600/redoc)

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

| Status Code | Meaning |
|-------------|---------|
| `401` | Invalid or missing `x-api-key` |
| `400` | Invalid request parameters (bad model, aspect ratio, etc.) |
| `404` | Image not found on disk |
| `422` | Missing required fields |
| `500` | Server misconfiguration (missing env vars) |
| `502` | Upstream Gemini API failure or filesystem error |

---

## Troubleshooting

| Symptom | Likely cause | What to try |
|---------|----------------|-------------|
| `500` "API_KEY is not configured" | Missing `API_KEY` in `backend/.env` | Copy `backend/.env.example` → `backend/.env` and set values. |
| `500` "GOOGLE_API_KEY is not configured" | Missing Gemini key | Set `GOOGLE_API_KEY` in `backend/.env`. |
| `401` on `/api/*` | Wrong or missing `x-api-key` | Header must match `API_KEY` exactly. |
| Error opening logo | Missing `assets/default_logo.jpg` | Add default logo under `backend/assets/`. |
| Empty gallery after generate | Wrong cwd | Start Uvicorn from `backend/` so `generated-images/` is created next to `main.py`. |
| Signed image URL 401 | Expired signature | Regenerate links via `GET /api/brands/{brand_id}/gallery` or generate again (~1 hour TTL). |

---

## See also

- **Code layout** and module responsibilities are documented near the **top** of this file.
- Monorepo overview: `../README.md`
- Frontend (demo UI): `../frontend/README.md`
