# Rankify Image Automation — Deployment & Company Onboarding Guide

This document explains what this repository does, whether it can run for any organization, what each company must supply, and the minimum infrastructure needed to host it.

---

## What this repository is

**Rankify Image Automation** is a multi-brand marketing image platform. It turns structured social-post copy and a brand logo into on-brand slide images using external AI image APIs (Google Gemini, Google Imagen 4, and OpenAI GPT Image). A React frontend provides a Creative Studio UI; a Python FastAPI backend handles brand configuration, generation, gallery storage, and optional social-copy generation.

| Component | Role |
|-----------|------|
| **Frontend** (`frontend/`) | Vite + React demo studio — brand workspaces, image generation, gallery, settings |
| **Backend** (`backend/`) | FastAPI HTTP API — brands, generate/edit pipelines, signed gallery URLs |
| **PostgreSQL** (optional) | Persists brand configs, gallery metadata, social-copy history |
| **Object storage** (optional) | Local disk (default) or AWS S3 / S3-compatible (e.g. Cloudflare R2) for images and logos |

**Typical workflow**

1. Onboard a **brand** (colors, typography, voice, governance prompts, logo).
2. User writes structured post content (title, subtitle, body, CTA) in the studio.
3. Backend builds prompts from the brand config and calls the selected AI provider.
4. Generated images are stored per brand and exposed via time-limited signed URLs.
5. Optional: OpenAI generates captions and hashtags from the same brand context.

Image inference runs on **third-party cloud APIs**, not on your servers. Your infrastructure mainly orchestrates HTTP, stores files/metadata, and serves the UI.

---

## Is it compatible with any company?

**Partially.** The application is **brand-agnostic at the code level** — you do not need code changes to add a new tenant. Each company (or brand workspace) is isolated by `brand_id` with its own configuration, logo, and gallery.

It is **not** plug-and-play for an arbitrary company without onboarding. The system needs:

1. **Per-brand configuration** (governance prompts, visual rules, colors, fonts, voice).
2. **Infrastructure credentials** (API keys, database, storage, networking).
3. **Outbound access** to Google and/or OpenAI APIs (depending on which models you enable).

The bundled `demo-ai-certs` brand is an example for AI CERTs only. Other organizations must create their own brand(s) via the API or UI.

---

## What a company must provide

### 1. Brand / marketing inputs (required per brand)

These map to the `BrandConfiguration` schema (`backend/brands/schemas.py`). Minimum to generate images:

| Input | Required | Description |
|-------|----------|-------------|
| **Brand ID** | Yes | Lowercase slug, 2–64 chars (e.g. `acme-corp`). Auto-generated UUID if omitted on create. |
| **Display name** | Yes | Human-readable brand name. |
| **Governance prompt** | Yes | Full “brand bible” system prompt (`generation.governance_prompt_template`, min 20 chars). Defines layout law, logo placement, colors, tone, and restrictions. |
| **Logo** | Strongly recommended | PNG/JPG/WebP uploaded via `POST /api/brands/{brand_id}/assets/logo`. Falls back to a server default if missing. |
| **Colors** | Recommended | Primary/secondary hex palette and usage rules. |
| **Typography** | Recommended | Font names and hierarchy notes (model uses these descriptively). |
| **Voice & audience** | Recommended | Tone keywords, writing style, target audience (used for social copy). |
| **Layout / visual rules** | Recommended | Design guidelines, spacing, CTA button rules, visual style, explicit “avoid” list. |
| **Social defaults** | Optional | Preferred platforms, default aspect ratio, default image size. |
| **Platform hints** | Optional | Per-platform copy/layout notes (LinkedIn, Instagram, X, etc.). |
| **Text preferences** | Optional | Hashtag style, caption style, banned phrases. |

**Ways to onboard a brand**

- **Manual:** `POST /api/brands` with multipart JSON payload + logo file.
- **AI-assisted draft:** `POST /api/brands/ai-draft` — paste unstructured brand materials; OpenAI returns a structured draft for review (requires `OPENAI_API_KEY`).
- **Demo seed:** `POST /api/brands/bootstrap-demo` — creates the packaged AI CERTs example only.

### 2. Server / platform configuration (required)

| Item | Required | Notes |
|------|----------|-------|
| **`API_KEY`** | Yes | Shared secret; clients send `x-api-key`. Also signs gallery image URLs. |
| **`GOOGLE_API_KEY`** | Yes* | *Required if using Gemini or Imagen models. |
| **`OPENAI_API_KEY`** | Conditional | Required for OpenAI image models, brand AI draft, social copy, and image edit on OpenAI models. |
| **`PUBLIC_BASE_URL`** | Recommended in production | Public API origin for signed image links behind a reverse proxy (no trailing slash). |
| **`IMAGE_TTL_HOURS`** | Optional | Gallery retention (default `720` = 30 days). |

See `backend/.env.example` for the full list.

### 3. Persistence mode (choose one)

| Mode | `DATABASE_URL` | `STORAGE_BACKEND` | Best for |
|------|----------------|-------------------|----------|
| **Filesystem only** | unset | `local` (default) | Local dev, single-node demos |
| **DB + local disk** | set | `local` | Production on one VM with persistent volumes |
| **DB + S3** | set | `s3` | Production, multi-instance, durable object storage |

**PostgreSQL** (when `DATABASE_URL` is set)

- Connection string, e.g. `postgresql+psycopg://user:pass@host:5432/rankify`
- Run migrations: `alembic upgrade head` (see `backend/docs/PRODUCTION_DB_S3.md`)

**S3-compatible storage** (when `STORAGE_BACKEND=s3`)

| Variable | Purpose |
|----------|---------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM credentials with read/write on the bucket |
| `AWS_S3_BUCKET_NAME` | Private bucket for gallery and brand assets |
| `AWS_REGION` | Bucket region (default `us-east-1`) |
| `S3_GALLERY_PREFIX` | Default `gallery/` |
| `S3_BRAND_ASSETS_PREFIX` | Default `brands/` |
| `S3_PRESIGN_TTL_SECONDS` | Presigned URL lifetime (default 3600 s) |

### 4. Network and security

- **Inbound:** TCP `8750` (API), `8760` (frontend UI) — or your reverse proxy ports (443 recommended in production).
- **Outbound HTTPS** to:
  - `generativelanguage.googleapis.com` / Google GenAI (Gemini, Imagen)
  - `api.openai.com` (OpenAI image + text)
- **TLS termination** at load balancer or reverse proxy (nginx, ALB, etc.) is expected in production.
- **Secrets** must not be committed; use `.env`, a secrets manager, or platform env injection.

### 5. Operational expectations

- **AI cost and quotas** are billed to the company’s Google Cloud / OpenAI accounts, not to this repo.
- **Disk or S3 capacity** grows with generated images until TTL purge (~every 15 minutes) removes expired items.
- **No built-in SSO, RBAC, or multi-tenant billing** — add these at the gateway or identity layer if needed.

---

## Architecture (reference)

```mermaid
flowchart LR
  User[Browser / Client]
  FE[Frontend nginx :8760]
  API[FastAPI Backend :8750]
  PG[(PostgreSQL)]
  Store[(Local disk or S3)]
  Google[Google Gemini / Imagen APIs]
  OpenAI[OpenAI APIs]

  User --> FE
  FE -->|/api proxy| API
  User -->|API + x-api-key| API
  API --> PG
  API --> Store
  API --> Google
  API --> OpenAI
```

---

## Minimum hardware requirements

The repo does not ship fixed sizing. Requirements below are **practical minimums** for self-hosted Docker Compose (`docker-compose.yml`: Postgres + backend + frontend). Image generation CPU/GPU load is on external APIs; your hosts mainly run API, static UI, DB, and file I/O.

### Minimum (pilot / low traffic)

Suitable for demos, internal QA, or a small team (&lt; ~10 concurrent users, occasional generation).

| Service | vCPU | RAM | Disk |
|---------|------|-----|------|
| **Backend** (FastAPI + Pillow) | 1 | 1 GB | 10 GB+ for gallery (local mode) |
| **Frontend** (nginx static) | 0.25 | 256 MB | negligible |
| **PostgreSQL 16** | 0.5 | 512 MB | 5 GB+ |
| **Total host (all-in-one)** | **2 vCPU** | **4 GB RAM** | **20 GB** SSD |

Run with a single Uvicorn worker (default in `backend/Dockerfile`). Expect 10–60+ second latency per generation while waiting on upstream AI APIs.

### Recommended (small production)

Steady daily use, multiple brands, DB + optional S3.

| Service | vCPU | RAM | Disk |
|---------|------|-----|------|
| **Backend** | 2 | 2 GB | Use S3 or ≥ 50 GB volume for local gallery |
| **Frontend** | 0.5 | 512 MB | — |
| **PostgreSQL** | 1 | 2 GB | 20 GB+ SSD, backups enabled |
| **Total** | **4 vCPU** | **8 GB RAM** | Scale storage with image volume |

### Notes on scaling

- **Backend-only** (no UI, no DB): **1 vCPU, 1–2 GB RAM** is enough for API-only integration tests.
- **RAM spikes** can occur when handling multiple large PNGs concurrently (Pillow decode/encode); size backend RAM up if you run many parallel generates.
- **Horizontal scaling** of the API is possible with shared Postgres + S3; local-disk gallery mode is single-node oriented.
- **GPU is not required** on your infrastructure — models run remotely.
- **Bandwidth:** Each 2K/4K image upload/download adds egress; budget accordingly if serving many variants.

---

## Software prerequisites

| Layer | Version / tool |
|-------|----------------|
| **Python** | 3.12 (see `backend/Dockerfile`) |
| **Node.js** | 22 (frontend build; see `frontend/Dockerfile`) |
| **PostgreSQL** | 16 (Compose image) |
| **Docker & Docker Compose** | Recommended for full-stack deploy |
| **Optional** | Alembic for DB migrations, `curl` for health checks |

---

## Quick deploy paths

| Scenario | Command / doc |
|----------|----------------|
| Full stack (Postgres + API + UI) | `docker compose up --build` — see root `README.md` |
| API only (Docker) | `docker build -f backend/Dockerfile -t rankify-image-api ./backend` |
| Staging script | `./deploy_staging.sh <branch>` |
| Production DB + S3 | `backend/docs/PRODUCTION_DB_S3.md` |
| API reference | `backend/README.md` |
| Frontend setup | `frontend/README.md` |

**Health check:** `GET /health` (no auth). In production with DB/S3 configured, response includes connectivity status.

---

## Company onboarding checklist

Use this before go-live for a new organization:

- [ ] Provision host or Kubernetes/VM with ≥ **2 vCPU / 4 GB RAM** (pilot) or **4 vCPU / 8 GB RAM** (production).
- [ ] Open outbound HTTPS to Google and OpenAI (if those providers are used).
- [ ] Set `API_KEY`, `GOOGLE_API_KEY`, and/or `OPENAI_API_KEY`.
- [ ] Choose persistence: filesystem-only, Postgres + local disk, or Postgres + S3.
- [ ] Run DB migrations if using Postgres.
- [ ] Set `PUBLIC_BASE_URL` when behind a reverse proxy.
- [ ] Create brand: governance prompt, colors, typography, voice, logo.
- [ ] Smoke test: `POST /api/generate` with `brand_id` and structured `content`.
- [ ] Configure frontend `x-api-key` (Settings) to match server `API_KEY`.
- [ ] Define backup policy for Postgres and gallery storage.
- [ ] Confirm AI provider billing and rate limits with the company’s cloud accounts.

---

## Related documentation

| Document | Contents |
|----------|----------|
| [`README.md`](README.md) | Monorepo overview and quick start |
| [`backend/README.md`](backend/README.md) | API endpoints, env vars, troubleshooting |
| [`backend/docs/PRODUCTION_DB_S3.md`](backend/docs/PRODUCTION_DB_S3.md) | Postgres + S3 production mode |
| [`frontend/README.md`](frontend/README.md) | UI setup and Docker proxy behavior |
| [`backend/.env.example`](backend/.env.example) | All environment variables |

---

*Hardware figures are guidance derived from the stack (Python API, nginx frontend, Postgres 16, local image storage). Adjust upward for high concurrency, large galleries, or strict availability SLAs.*
