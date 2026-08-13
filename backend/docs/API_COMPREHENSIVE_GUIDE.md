# Rankify Image Automation — Comprehensive API Guide

**Version:** 3.0.0  
**Base URL:** `http://localhost:8750` (no `/api/v1` prefix)  
**Interactive docs:** `/docs` (Swagger), `/redoc`, `/openapi.json`

This guide consolidates practical integration knowledge for every Rankify HTTP endpoint: request shapes, responses, Postman setup, frontend patterns, and end-to-end flows. For field-level schema details and TypeScript types, see [API_REFERENCE.md](./API_REFERENCE.md).

---

## Table of contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Common conventions](#3-common-conventions)
4. [Shared data models](#4-shared-data-models)
5. [Health](#5-health)
6. [Brands](#6-brands)
7. [Brand logo assets](#7-brand-logo-assets)
8. [Social copy (captions & hashtags)](#8-social-copy-captions--hashtags)
9. [Catalog (models & image sizes)](#9-catalog-models--image-sizes)
10. [Image generation](#10-image-generation)
11. [Gallery](#11-gallery)
12. [Legacy endpoints](#12-legacy-endpoints)
13. [Error handling](#13-error-handling)
14. [End-to-end flows](#14-end-to-end-flows)
15. [Shipped React UI reference](#15-shipped-react-ui-reference)
16. [Endpoint quick index](#16-endpoint-quick-index)

---

## 1. Overview

Rankify is a **multi-brand** creative API:

- **Brands** hold configuration (colors, typography, governance prompts, logo).
- **Generate / edit** endpoints produce images into a **per-brand gallery**.
- **Social copy** generates captions and hashtags via OpenAI.
- Gallery image URLs are either **HMAC-signed** (local storage) or **S3 presigned** (when `STORAGE_BACKEND=s3`).

| Concern | Behavior |
|--------|----------|
| CORS | `Access-Control-Allow-Origin: *`; credentials disabled |
| Auth | Header `x-api-key` on almost all `/api/*` routes |
| WebSockets | None |
| Content types | `application/json` or `multipart/form-data` |

---

## 2. Authentication

### 2.1 API key (primary)

Almost all `/api/*` endpoints require:

| Header | Value |
|--------|--------|
| `x-api-key` | Must match server environment variable `API_KEY` |

| Status | `detail` | When |
|--------|----------|------|
| `401` | `"Invalid API key."` | Missing, empty, or wrong key |
| `500` | `"API_KEY is not configured on the server."` | Server has no `API_KEY` |

There is **no JWT, OAuth, or cookie session**. Possession of `API_KEY` grants full access to all brands on that server.

### 2.2 Signed gallery URLs (no API key)

`GET /api/brands/{brand_id}/gallery/raw/{filename}` uses query parameters instead of `x-api-key`:

| Query param | Description |
|-------------|-------------|
| `exp` | Unix expiry timestamp |
| `sig` | HMAC-SHA256 hex of `brand_id:filename:exp` (secret = `API_KEY`) |

**Do not build signatures in the browser.** Use the `url` field returned by list/generate/edit responses.

### 2.3 Server-side provider keys

These are **not** sent by clients:

| Env var | Used for |
|---------|----------|
| `GOOGLE_API_KEY` | Gemini / Imagen image generation |
| `OPENAI_API_KEY` | OpenAI image models, social copy, brand AI draft |

---

## 3. Common conventions

### 3.1 Headers

| Header | When |
|--------|------|
| `x-api-key` | All authenticated routes |
| `Content-Type: application/json` | JSON body endpoints only |
| `Content-Type: multipart/form-data` | **Do not set manually** — let Postman/browser set boundary |

### 3.2 `brand_id` slug rules

- Length **2–64** characters
- Lowercase letters, digits, hyphens only
- Must not start or end with `-`
- Pattern: `^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`

**Valid:** `acme-corp`, `demo-ai-certs`, UUID slugs  
**Invalid:** `A`, `-acme`, `acme_`, `Acme Corp`

### 3.3 Gallery filenames

- Pattern: `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`
- No path separators, spaces, or empty names

| Pattern | Source |
|---------|--------|
| `rankify_slide_<8hex>_<n>.png` | Generate (`n` = 1..num_images) |
| `rankify_edit_<10hex>.png` | Gallery edit (new file; source not overwritten) |

### 3.4 Error response shape

```json
{
  "detail": "Human-readable message or validation array"
}
```

---

## 4. Shared data models

### 4.1 `StudioCampaignBrief`

Used by generate (optional) and social-copy endpoints.

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `intent` | **Yes** | — | User prompt; **only this drives image generation** |
| `creativity_tone_label` | **Yes** | — | Required key; e.g. `"Balanced — on-brand with light creative stretch"` |
| `platforms` | No | `[]` | Lowercase: `linkedin`, `instagram`, `x`, … |
| `voice_tone_label` | No | `"Professional"` | Tone dropdown |
| `campaign_goal_id` | No | `"brand_awareness"` | Legacy; UI always sends default |

```json
{
  "campaign_goal_id": "brand_awareness",
  "platforms": ["linkedin", "instagram"],
  "voice_tone_label": "Professional",
  "creativity_tone_label": "Balanced — on-brand with light creative stretch",
  "intent": "Announce our new AI certification pathway for mid-career professionals."
}
```

### 4.2 `GalleryImageItem`

Returned by generate, edit, and gallery list.

| Field | Use |
|-------|-----|
| `filename` | Edit, delete, social-copy `image_filename` |
| `url` | `<img src>` / download (signed; ~1 hour TTL) |
| `storage_path` | Informational: `generated-images/<brand_id>/<filename>` |
| `size_bytes` | File size |
| `created_at` | ISO datetime |
| `age_hours` | Age in hours; dashboard uses `≤ 168` for “last 7 days” |

### 4.3 `BrandSlideGenerateResponse`

Returned by all generate endpoints and gallery edit.

| Field | Description |
|-------|-------------|
| `images` | `GalleryImageItem[]` |
| `model_used` | Model id used |
| `per_image_price_usd` | Estimate per image |
| `total_price_usd` | Estimate batch total |
| `message` | Human summary |
| `generation_audit_path` | Server path only — ignore in UI |

### 4.4 `BrandCreatePayload` / `BrandConfiguration`

| Object | Purpose |
|--------|---------|
| `colors` | `primary[]`, `secondary[]`, `usage_rules` |
| `typography` | Font hints for image model |
| `voice` | Tone, writing style, audience |
| `social_defaults` | Platforms, default aspect ratio, default image size |
| `platform_hints` | `{ "linkedin": "...", "instagram": "..." }` |
| `content_themes` | Categories, recurring themes |
| `text_preferences` | Hashtag/caption style, banned phrases |
| `generation` | **Required** — `governance_prompt_template` (≥ 20 chars) + visual rules |

**Create (`BrandCreatePayload`):** `brand_id` optional (server assigns UUID if omitted).  
**Full config (`BrandConfiguration`):** `brand_id` required; includes `updated_at`.

---

## 5. Health

### `GET /health`

| Item | Value |
|------|--------|
| Auth | **None** (public) |
| Purpose | Liveness / readiness probe |
| Shipped UI | Not called |

**Response `200`:**

```json
{
  "status": "ok",
  "storage_backend": "local",
  "database": "disabled",
  "gallery_root": ".../generated-images",
  "brand_config_root": ".../data/brands",
  "timestamp": "2026-08-13T11:32:00+00:00"
}
```

If DB or S3 checks fail, `status` becomes `"degraded"` but HTTP remains **200**.

---

## 6. Brands

All brand endpoints require **`x-api-key`**.

### 6.1 `GET /api/brands` — List brands

**Response `200`:**

```json
{
  "brands": [
    { "brand_id": "acme-corp", "display_name": "Acme Corp", "updated_at": "..." }
  ],
  "total": 1
}
```

### 6.2 `POST /api/brands` — Create brand

**Content-Type:** `multipart/form-data`

| Form field | Type | Required | Description |
|------------|------|----------|-------------|
| `payload` | Text (JSON string) | **Yes** | `BrandCreatePayload` |
| `logo` | File | **Yes** | `.png`, `.jpg`, `.jpeg`, `.webp` |

#### What the frontend typically omits

| Field | Required from client? |
|-------|------------------------|
| `brand_id` | **No** — server assigns UUID slug |
| `logo_asset_filename` | **No** — defaults to `"logo.png"` |
| `display_name` | **Yes** |
| `generation.governance_prompt_template` | **Yes** (≥ 20 chars) |
| `logo` file | **Yes** |

After create, use **`response.brand_id`** for all subsequent calls.

#### Postman setup

1. Method: `POST`
2. URL: `http://localhost:8750/api/brands`
3. Header: `x-api-key` only (**do not** set `Content-Type`)
4. Body → **form-data**:

| Key | Type | Value |
|-----|------|--------|
| `payload` | **Text** | JSON string (see minimal example below) |
| `logo` | **File** | Select image file |

**Minimal `payload`:**

```json
{
  "display_name": "Acme Corp",
  "generation": {
    "governance_prompt_template": "You design on-brand social slides for Acme. Use navy and coral. Keep layouts clean with ample whitespace."
  }
}
```

**Response `200`:** Full `BrandConfiguration` including assigned `brand_id`.

**Errors:** `409` duplicate brand_id, `400` invalid logo, `422` validation, `500` logo upload failed (brand rolled back).

**Transaction note:** If logo storage fails after config save, the brand is deleted — no half-created brand.

### 6.3 `POST /api/brands/ai-draft` — AI auto-fill brand guidelines

**Purpose:** OpenAI drafts a `BrandCreatePayload` from unstructured notes. **Does not persist.**

**Content-Type:** `application/json`  
**Requires:** Server `OPENAI_API_KEY`

| Field | Required | Validation |
|-------|----------|------------|
| `brand_materials` | **Yes** | 30–120,000 chars |
| `brand_id` | No | Valid slug if set; else UUID in draft |
| `model_name` | No | Default `gpt-4o-2024-08-06`; allowed: `gpt-4o-2024-08-06`, `gpt-4o-mini`, `gpt-4o` |

**Postman:**

```json
{
  "brand_materials": "Acme Corp sells developer tools. Voice is crisp. Primary navy #0A2540, accent coral. Never comic fonts. Target mid-level engineers.",
  "model_name": "gpt-4o-2024-08-06"
}
```

**Response `200`:**

```json
{
  "draft": { /* full BrandCreatePayload */ },
  "model_used": "gpt-4o-2024-08-06"
}
```

**Flow:** ai-draft → user reviews form → `POST /api/brands` with logo. AI draft does **not** upload logo.

**Errors:** `503` no OpenAI key, `400` bad model, `422` parse/refusal, `502` OpenAI failure.

### 6.4 `POST /api/brands/bootstrap-demo` — Demo brand

**Purpose:** Create packaged demo brand `demo-ai-certs` if missing. **Idempotent.**

**Request:** No body.

**Response `200`:** `BrandConfiguration` for `demo-ai-certs`.

**Caveat:** Config only — no logo. Until `POST .../assets/logo`, generation uses `assets/default_logo.jpg`.

### 6.5 `GET /api/brands/{brand_id}` — Get full config

**Response `200`:** Full `BrandConfiguration`.  
**Errors:** `404` brand not found.

### 6.6 `PUT /api/brands/{brand_id}` — Replace entire config

**Content-Type:** `application/json`  
**Purpose:** Full document replace (not PATCH).

- `body.brand_id` must equal path `{brand_id}`
- Does **not** upload logo — use logo asset endpoint separately

**Postman:** GET first → edit fields → PUT entire JSON back.

**Errors:** `400` brand_id mismatch, `404`, `422` validation.

### 6.7 `DELETE /api/brands/{brand_id}` — Delete brand

**Purpose:** Destructive — removes config, assets, and gallery.

**Response `200`:**

```json
{
  "message": "Brand acme-corp and its gallery folder removed.",
  "brand_id": "acme-corp"
}
```

**Storage:** Local deletes disk; S3+DB mode may leave S3 blobs until TTL/ops cleanup.

---

## 7. Brand logo assets

Logos are **API-key protected** — fetch as blob for display, not raw `<img src>`.

### 7.1 Create vs replace — different field names

| Action | Endpoint | File field name |
|--------|----------|-----------------|
| Create brand | `POST /api/brands` | `logo` |
| Replace logo later | `POST /api/brands/{id}/assets/logo` | `file` |

User's original upload filename is ignored. Server stores as `logo_asset_filename` (default `logo.png`).

### 7.2 `POST /api/brands/{brand_id}/assets/logo` — Upload / replace

**Content-Type:** `multipart/form-data`

| Form field | Type | Required |
|------------|------|----------|
| `file` | File | **Yes** |

**Postman:** form-data, key `file` type **File**, header `x-api-key` only.

**Response `200`:**

```json
{
  "message": "Logo saved.",
  "path": "<storage path or S3 key>"
}
```

### 7.3 `GET /api/brands/{brand_id}/assets/logo` — Download logo bytes

**Response `200`:** Binary image (`image/png`, `image/jpeg`, or `image/webp`).

**Frontend pattern:**

```javascript
const res = await fetch(`${apiBase}/api/brands/${encodeURIComponent(brandId)}/assets/logo`, {
  headers: { "x-api-key": apiKey },
});
if (res.status === 404) return null;
const blob = await res.blob();
const url = URL.createObjectURL(blob); // revoke on unmount
```

---

## 8. Social copy (captions & hashtags)

### Endpoints (same logic)

| Method | Path | Shipped UI |
|--------|------|------------|
| `POST` | `/api/brands/{brand_id}/text/social-copy` | **Yes** |
| `POST` | `/api/brands/{brand_id}/text/captions` | Alias |
| `POST` | `/api/brands/{brand_id}/text/hashtags` | Alias |

**Requires:** Server `OPENAI_API_KEY`  
**Model:** Fixed **`gpt-4o-mini`** (not client-selectable)

### Request body

```json
{
  "studio_campaign": {
    "platforms": ["linkedin"],
    "voice_tone_label": "Professional",
    "creativity_tone_label": "Balanced — on-brand with light creative stretch",
    "intent": "Launch of our cloud security badge for DevOps teams."
  },
  "image_filename": "rankify_slide_a1b2c3d4_1.png"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `studio_campaign` | **Yes** | Same brief as generate |
| `image_filename` | No | Gallery filename for vision grounding |

**How frontend gets `image_filename`:** From generate/edit response `images[0].filename` — **not** from user upload name or URL.

### Response `200`

```json
{
  "caption": "Introducing our Cloud Security Badge…",
  "hashtags": "#CloudSecurity #DevOps #AcmeCorp",
  "model_used": "gpt-4o-mini"
}
```

`hashtags` is one space-separated string — split on spaces for chips.

### Postman

- `POST http://localhost:8750/api/brands/{brand_id}/text/social-copy`
- Headers: `x-api-key`, `Content-Type: application/json`
- Body: raw JSON (above)

---

## 9. Catalog (models & image sizes)

Load on Creative Studio boot to populate model/ratio/size controls.

### 9.1 `GET /api/models`

**Response `200`:**

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
    }
  ]
}
```

| Field | UI use |
|-------|--------|
| `model_name` | Send as `model_name` on generate/edit |
| `label` | Dropdown label |
| `supports_image_size` | Show 1K/2K/4K control; send `image_size` only if true |
| `supports_generate` | Show in generate UI |
| `supports_edit` | Show in edit UI (Imagen = false) |

**OpenAI ids are namespaced:** `openai:gpt-image-1`, `openai:gpt-image-2`, etc.

**Shipped UI:** Hides Imagen models. Custom clients should honor `supports_edit`.

### 9.2 `GET /api/image-sizes`

**Response `200`:**

```json
{
  "image_sizes": ["1K", "2K", "4K"],
  "aspect_ratios": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
  "note": "Image size applies to gemini-3-pro-image-preview and OpenAI gpt-image-1 / gpt-image-2 models."
}
```

Prefer each model's `supports_image_size` over the static `note`.

---

## 10. Image generation

All generate endpoints require **`x-api-key`**, write to the brand gallery, and return **`BrandSlideGenerateResponse`**.

**Logo resolution order:** multipart logo override → brand logo asset → `assets/default_logo.jpg`.

### Which endpoint to use

| User action | Endpoint | Body type |
|-------------|----------|-----------|
| Text prompt only | `POST /api/generate` | JSON |
| Prompt + reference / moodboard | `POST /api/generate-with-reference` | multipart |
| Legacy structured copy + optional logo | `POST /api/generate-with-logo` | multipart |

**Shipped Creative Studio:** reference file → `generate-with-reference`; else → `/api/generate`. Does **not** use `generate-with-logo`.

### 10.1 `POST /api/generate` — JSON (primary)

**Content-Type:** `application/json`

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `brand_id` | **Yes** | — | Must exist |
| `studio_campaign` | Conditional | — | Studio path (recommended) |
| `content` | Conditional | — | Legacy; required if no `studio_campaign` |
| `model_name` | No | `gemini-3-pro-image-preview` | From catalog |
| `num_images` | No | `1` | 1–10 |
| `aspect_ratio` | No | `1:1` | From image-sizes |
| `image_size` | No | `2K` | Only when model supports size |

If both `studio_campaign` and `content` are sent, **`studio_campaign` wins**. Image generation uses **`intent` only**.

**Postman example:**

```json
{
  "brand_id": "acme-corp",
  "studio_campaign": {
    "platforms": ["instagram"],
    "voice_tone_label": "Confident",
    "creativity_tone_label": "Bold — striking visuals welcome",
    "intent": "Hero slide: Cloud Security Badge now open for enrollment"
  },
  "model_name": "gemini-3-pro-image-preview",
  "num_images": 1,
  "aspect_ratio": "1:1",
  "image_size": "2K"
}
```

### 10.2 `POST /api/generate-with-reference` — Multipart + moodboard

**Content-Type:** `multipart/form-data`

| Form field | Type | Required | Notes |
|------------|------|----------|--------|
| `brand_id` | Text | **Yes** | |
| `studio_campaign` | Text (JSON string) | **Yes** | Not a File |
| `model_name` | Text | No | |
| `num_images` | Text | No | e.g. `"1"` |
| `aspect_ratio` | Text | No | |
| `image_size` | Text | No | If model supports size |
| `reference_image` | **File** | No | Moodboard / layout inspiration |
| `logo` | File | No | One-off override (UI skips) |

**Postman:** form-data; `studio_campaign` = **Text**; `reference_image` = **File**; do not set `Content-Type` header.

**Imagen + reference_image → `400`.** Use Gemini or OpenAI.

### 10.3 `POST /api/generate-with-logo` — Legacy multipart

Not used by shipped UI. Requires `content` (plain text), not `studio_campaign`. Optional `logo` file field.

### 10.4 Generate response

```json
{
  "images": [
    {
      "filename": "rankify_slide_a1b2c3d4_1.png",
      "url": "http://localhost:8750/api/brands/.../gallery/raw/...?exp=&sig=",
      "storage_path": "generated-images/acme-corp/rankify_slide_a1b2c3d4_1.png",
      "size_bytes": 412000,
      "created_at": "...",
      "age_hours": 0.0
    }
  ],
  "model_used": "gemini-3-pro-image-preview",
  "per_image_price_usd": 0.134,
  "total_price_usd": 0.134,
  "message": "Successfully generated 1 slide(s) for brand 'acme-corp'.",
  "generation_audit_path": null
}
```

**After generate:** use `images[0].filename` for social-copy; `images[0].url` for display.

### 10.5 Provider notes

| Provider | Notes |
|----------|-------|
| **Gemini** | Full governance + logo; best error mapping |
| **OpenAI** | Namespaced ids; size tiers matter for `openai:gpt-image-2` |
| **Imagen** | No logo, no governance, no reference, no edit — hidden in shipped UI |

---

## 11. Gallery

Per-brand storage under `/api/brands/{brand_id}/gallery/...`.

### 11.1 `GET /api/brands/{brand_id}/gallery` — List

**Response `200`:**

```json
{
  "total": 2,
  "images": [ { "filename": "...", "url": "...", "size_bytes": 412000, "age_hours": 1.25, ... } ]
}
```

Newest first. Shipped gallery page uses `url` for thumbnails.

### 11.2 `POST /api/brands/{brand_id}/gallery/edit` — AI edit

**Not the same as generate.** Refines an **existing** gallery image.

**Content-Type:** `application/json`

```json
{
  "source_filename": "rankify_slide_a1b2c3d4_1.png",
  "instruction": "Change the CTA button text to Enroll Today and keep everything else identical.",
  "model_name": "gemini-3-pro-image-preview",
  "aspect_ratio": "1:1",
  "image_size": "2K"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `source_filename` | **Yes** | From generate/list response |
| `instruction` | **Yes** | 3–2000 chars |
| `model_name` | No | API default `gemini-2.5-flash-image` |

Creates new `rankify_edit_*.png`; **does not overwrite** source. Returns same shape as generate (usually 1 image).

### 11.3 `GET /api/brands/{brand_id}/gallery/{filename}` — 307 redirect

Requires `x-api-key`. Redirects to signed view URL. Shipped UI prefers `url` from list response.

### 11.4 `GET .../gallery/raw/{filename}` — Stream bytes

Auth via `?exp=&sig=` query — **not** `x-api-key`. Use `url` from API responses.

URLs expire (~1 hour). On **401**, reload gallery for fresh URLs.

### 11.5 `DELETE /api/brands/{brand_id}/gallery/{filename}`

Shipped gallery page does **not** call this. Custom clients may delete individual images.

**Response `200`:**

```json
{
  "message": "Image deleted.",
  "filename": "rankify_slide_a1b2c3d4_1.png"
}
```

---

## 12. Legacy endpoints

Always return **410 Gone**. Do not use.

| Method | Path | Use instead |
|--------|------|-------------|
| `GET` | `/api/gallery` | `GET /api/brands/{brand_id}/gallery` |
| `GET` | `/api/gallery/{filename}` | Brand-scoped gallery URLs |
| `GET` | `/api/gallery/raw/{filename}` | `GET .../gallery/raw/{filename}` |
| `DELETE` | `/api/gallery/{filename}` | `DELETE .../gallery/{filename}` |

---

## 13. Error handling

| HTTP | Common meaning | UI action |
|------|----------------|-----------|
| `200` | Success | Proceed |
| `307` | Gallery redirect | Follow or use list `url` |
| `400` | Bad input (model, ratio, logo type, JSON) | Fix and retry |
| `401` | Bad API key or expired gallery signature | Fix key; reload gallery |
| `404` | Brand, logo, or image missing | Empty state / navigate away |
| `409` | Duplicate `brand_id` on create | Pick different slug |
| `410` | Legacy API | Update client paths |
| `422` | Validation; model refusal; no image output | Show message |
| `500` | Missing `API_KEY` / `GOOGLE_API_KEY`; upload failure | Ops / config |
| `502` | Upstream provider failure | Retry later |
| `503` | Missing `OPENAI_API_KEY` | Configure OpenAI |

---

## 14. End-to-end flows

### 14.1 First run / empty database

1. Optional: `POST /api/brands/bootstrap-demo`
2. `POST /api/brands/{demo-ai-certs}/assets/logo` (if logo needed)
3. `GET /api/brands` → open studio

### 14.2 Onboard a custom brand

1. Optional: `POST /api/brands/ai-draft` with pasted guidelines
2. Review draft in form
3. `POST /api/brands` (multipart: `payload` + `logo`)
4. Save `response.brand_id`

### 14.3 Creative Studio — generate + caption

1. `GET /api/brands/{id}`, `GET /api/models`, `GET /api/image-sizes`
2. Generate:
   - No reference → `POST /api/generate` (JSON)
   - With reference → `POST /api/generate-with-reference` (multipart)
3. `POST .../text/social-copy` with same `studio_campaign` + `images[0].filename`

### 14.4 Edit an existing slide

1. `POST .../gallery/edit` with `source_filename` + `instruction`
2. Optional: social-copy with new `images[0].filename`

### 14.5 Gallery management

1. `GET .../gallery` → display `url` / `filename`
2. Optional: `DELETE .../gallery/{filename}`

### 14.6 Update brand settings

1. `GET /api/brands/{id}`
2. `PUT /api/brands/{id}` (full JSON)
3. If new logo: `POST .../assets/logo` (field `file`)

### 14.7 Delete brand

1. `DELETE /api/brands/{id}` — removes config, assets, local gallery

---

## 15. Shipped React UI reference

| Screen / feature | Endpoints used |
|------------------|----------------|
| App boot / dashboard | `GET /api/brands`, per brand `GET .../gallery` |
| Create brand wizard | `POST /api/brands/ai-draft` → `POST /api/brands` |
| Edit brand | `GET` + `PUT /api/brands/{id}`; logo via `POST .../assets/logo` |
| Creative Studio | Catalog GETs, generate or generate-with-reference, social-copy, gallery edit |
| Gallery page | `GET .../gallery` only (no delete) |
| Caption / hashtags | **`POST .../text/social-copy` only** (not captions/hashtags aliases) |

### Multipart field name cheat sheet

| Endpoint | JSON/config field | Image file field |
|----------|-------------------|------------------|
| `POST /api/brands` | `payload` (Text) | `logo` (File) |
| `POST .../assets/logo` | — | `file` (File) |
| `POST /api/generate-with-reference` | `studio_campaign` (Text) | `reference_image` (File) |
| `POST /api/generate-with-logo` | `content` (Text) | `logo` (File, optional) |

### Display rules

| Asset | Auth | `<img src>` |
|-------|------|-------------|
| Brand logo | `x-api-key` | No — fetch blob first |
| Gallery image | Signed in `url` | Yes — use `url` as returned |

---

## 16. Endpoint quick index

| Method | Path | Auth | Summary |
|--------|------|------|---------|
| `GET` | `/health` | Public | Health / infra status |
| `GET` | `/api/brands` | API key | List brands |
| `POST` | `/api/brands` | API key | Create brand + logo (multipart) |
| `POST` | `/api/brands/ai-draft` | API key | AI draft brand config |
| `POST` | `/api/brands/bootstrap-demo` | API key | Idempotent demo brand |
| `GET` | `/api/brands/{brand_id}` | API key | Get brand |
| `PUT` | `/api/brands/{brand_id}` | API key | Replace brand |
| `DELETE` | `/api/brands/{brand_id}` | API key | Delete brand + gallery |
| `POST` | `/api/brands/{brand_id}/assets/logo` | API key | Upload logo |
| `GET` | `/api/brands/{brand_id}/assets/logo` | API key | Download logo |
| `POST` | `/api/brands/{brand_id}/text/social-copy` | API key | Caption + hashtags |
| `POST` | `/api/brands/{brand_id}/text/captions` | API key | Alias of social-copy |
| `POST` | `/api/brands/{brand_id}/text/hashtags` | API key | Alias of social-copy |
| `GET` | `/api/models` | API key | Image model catalog |
| `GET` | `/api/image-sizes` | API key | Sizes + aspect ratios |
| `POST` | `/api/generate` | API key | Generate (JSON) |
| `POST` | `/api/generate-with-logo` | API key | Generate (multipart + logo) |
| `POST` | `/api/generate-with-reference` | API key | Generate + reference image |
| `GET` | `/api/brands/{brand_id}/gallery` | API key | List gallery |
| `POST` | `/api/brands/{brand_id}/gallery/edit` | API key | Edit gallery image |
| `GET` | `/api/brands/{brand_id}/gallery/{filename}` | API key | 307 → view URL |
| `GET` | `/api/brands/{brand_id}/gallery/raw/{filename}` | Signature | Stream image bytes |
| `DELETE` | `/api/brands/{brand_id}/gallery/{filename}` | API key | Delete image |
| `GET/DELETE` | `/api/gallery*` | — | **410** legacy |

---

## Related documentation

- [API_REFERENCE.md](./API_REFERENCE.md) — Full field reference, TypeScript contracts, scenarios
- [IMAGE_GENERATION_WORKFLOW_AND_COSTS.md](./IMAGE_GENERATION_WORKFLOW_AND_COSTS.md) — Generation pipeline and pricing
- [PRODUCTION_DB_S3.md](./PRODUCTION_DB_S3.md) — Production storage configuration
