# Rankify Image Automation — API Reference

**Version:** 3.0.0  
**Framework:** FastAPI  
**Default base URL:** `http://localhost:8750`  
**Interactive docs:** `/docs` (Swagger UI), `/redoc`, `/openapi.json`

This document describes every HTTP endpoint exposed by the Rankify backend so frontend developers and integrators can consume the API without reading the server source.

**Practical integration guide:** [API_COMPREHENSIVE_GUIDE.md](./API_COMPREHENSIVE_GUIDE.md) — consolidated flows, Postman setup, multipart field names, and shipped UI behavior from integrator discussions.

**Frontend engineers:** start with [§2 Frontend integration guide](#2-frontend-integration-guide), then use [§15 scenarios](#15-end-to-end-frontend-scenarios) and [§18 TypeScript contracts](#18-typescript-style-contracts). Field-level details for every endpoint follow in §§6–12.

---

## Table of contents

1. [Overview](#1-overview)
2. [Frontend integration guide](#2-frontend-integration-guide) — start here (includes [shipped UI behavior](#210-shipped-frontend-behavior-rankify-react-ui))
3. [Authentication](#3-authentication)
4. [Common conventions](#4-common-conventions)
5. [Shared data models](#5-shared-data-models)
6. [Health](#6-health)
7. [Brands](#7-brands)
8. [Brand assets](#8-brand-assets)
9. [Brand text (social copy)](#9-brand-text-social-copy)
10. [Models and image sizes](#10-models-and-image-sizes)
11. [Image generation](#11-image-generation)
12. [Gallery](#12-gallery)
13. [Legacy endpoints](#13-legacy-endpoints)
14. [Error handling](#14-error-handling)
15. [End-to-end frontend scenarios](#15-end-to-end-frontend-scenarios)
16. [Business rules and operational notes](#16-business-rules-and-operational-notes)
17. [Endpoint quick index](#17-endpoint-quick-index)
18. [TypeScript-style contracts](#18-typescript-style-contracts)

---

## 1. Overview

Rankify is a **multi-brand** creative API:

- Brands hold configuration (colors, typography, governance prompts, logo).
- Generation / edit endpoints produce images into a **per-brand gallery**.
- Gallery image URLs are either **HMAC-signed** (local storage) or **S3 presigned** (when `STORAGE_BACKEND=s3`).

There is **no URL versioning** (`/api/v1/...`). Paths are rooted at `/` and `/api/...`.

| Concern | Behavior |
|--------|----------|
| CORS | `Access-Control-Allow-Origin: *`; credentials disabled; all methods/headers allowed |
| Auth | Header `x-api-key` (almost all `/api/*` routes) |
| WebSockets | None |
| Content types | `application/json` or `multipart/form-data` |

---

## 2. Frontend integration guide

This section is the practical contract for UI work. Sections 6–12 document every field; use this for **how** to call the API correctly in a browser.

### 2.1 Base URL and settings

| Setting | Typical value | Notes |
|---------|---------------|-------|
| API base URL | `http://localhost:8750` or empty string in Vite/dev behind a proxy | No trailing slash |
| API key | Same as server `API_KEY` | Store in app settings / env (`VITE_API_KEY`); never ship in public repos |

Resolve request URLs as `` `${apiBase}${path}` `` where `path` starts with `/api/...` or `/health`.

### 2.2 Which endpoints need which headers

| Call type | `x-api-key` | `Content-Type` | Body |
|-----------|-------------|----------------|------|
| JSON APIs (`/api/brands`, `/api/generate`, social-copy, edit, …) | **Required** | `application/json` | `JSON.stringify(body)` |
| Multipart (`POST /api/brands`, generate-with-logo/reference, logo upload) | **Required** | **Do not set manually** — browser sets multipart boundary via `FormData` | `FormData` |
| `GET /health` | Not required | — | — |
| Gallery image `url` from responses (signed raw or S3) | **Not required** — do **not** attach `x-api-key` | — | Use as `<img src={url}>` or `fetch(url)` for download (auth is already in the query string / S3 signature) |
| `GET .../assets/logo` | **Required** | — | Binary response — cannot put in `<img src>` without fetching as blob |

**Logo exception:** Brand logos are **API-key protected**. Frontend must `fetch` with `x-api-key`, then `URL.createObjectURL(blob)` for display. Revoke the object URL on unmount.

### 2.3 Minimal authenticated JSON client

```javascript
async function apiJson(apiBase, apiKey, path, { method = "GET", body } = {}) {
  const res = await fetch(`${apiBase.replace(/\/+$/, "")}${path}`, {
    method,
    headers: {
      "x-api-key": apiKey,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? data.detail
        : text || res.statusText;
    const err = new Error(formatApiDetail(res.status, detail));
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

/** detail may be a string or a Pydantic error array */
function formatApiDetail(status, detail) {
  if (typeof detail === "string") return `${status}: ${detail}`;
  if (Array.isArray(detail)) {
    return `${status}: ${detail.map((e) => e.msg || JSON.stringify(e)).join("; ")}`;
  }
  return `${status}: ${JSON.stringify(detail)}`;
}
```

### 2.4 Path encoding

Always encode path segments that come from user/data:

```javascript
`/api/brands/${encodeURIComponent(brandId)}/gallery/${encodeURIComponent(filename)}`
```

Do **not** encode the whole path. Query params on signed URLs are already correct — use the `url` field as returned.

### 2.5 Which generate endpoint to call

| User action | Endpoint | Body type |
|-------------|----------|-----------|
| Text prompt only (Creative Studio / simple generate) | `POST /api/generate` | JSON with `studio_campaign` **or** legacy `content` |
| Text prompt + **reference / moodboard image** | `POST /api/generate-with-reference` | `FormData` (`studio_campaign` as JSON **string**) |
| Structured copy + optional one-off logo file | `POST /api/generate-with-logo` | `FormData` with `content` string |
| Refine an existing gallery PNG | `POST /api/brands/{id}/gallery/edit` | JSON |

Recommended studio flow (matches the shipped frontend):

1. Build `studio_campaign` with `intent`, `platforms`, `voice_tone_label`, `creativity_tone_label`.
2. If user attached a reference image → multipart `generate-with-reference`.
3. Else → JSON `/api/generate` with `studio_campaign`.
4. After success, take `images[0].filename` and call social-copy with optional `image_filename`.

### 2.6 Model selector rules (from `GET /api/models`)

For each catalog row:

| Field | UI behavior |
|-------|-------------|
| `model_name` | Value sent as `model_name` |
| `label` | Dropdown label |
| `supports_generate` | Recommended: show in generate UIs if `true` |
| `supports_edit` | Recommended: show in edit UI if `true` (Imagen is `false`) |
| `supports_image_size` | If `true`, show `1K`/`2K`/`4K` control and send `image_size`; if `false`, omit or ignore size |
| `provider` | Optional grouping (`gemini` / `openai` / `imagen`) |

Always load aspect ratios from `GET /api/image-sizes` (`aspect_ratios` array). Only send values from that list (or a documented UI subset).

**Shipped Rankify UI:** always hides Imagen (`provider === "imagen"` or `model_name` starts with `imagen-`). It does **not** consult `supports_generate` / `supports_edit` (edit reuses the same filtered generate list). Custom clients should still honor `supports_edit` and avoid Imagen for reference images and edits.

### 2.7 Displaying and downloading gallery images

1. Prefer `image.url` from list/generate/edit responses for `<img src={url}>`.
2. Signed / presigned URLs expire (~1 hour — see `GALLERY_IMAGE_URL_TTL_SECONDS` / `S3_PRESIGN_TTL_SECONDS`). On **401** when fetching/downloading, reload gallery (`GET .../gallery`) to get fresh URLs — do not keep stale URLs in long-lived state without refresh.
3. For download: `fetch(url)` → blob → temporary object URL → `<a download>`. If a local signed URL points at another origin, rewrite to same-origin `/api/brands/.../gallery/raw/...?exp=&sig=` when a Vite/nginx proxy is available.
4. **S3 URLs:** also download via `fetch(url)` → blob when possible (CORS allows `*`). Do not assume `<a href download>` always forces a filename across origins.
5. Do **not** call `GET .../gallery/{filename}` from `<img>` expecting JSON; that endpoint **307-redirects**. Following redirects in `fetch` works; for `<img>` prefer the final `url` already in the list response.

### 2.8 Latency and UX expectations

| Operation | Typical UX |
|-----------|------------|
| Generate / edit | Seconds to tens of seconds — show busy state; allow cancel only client-side (server does not support cancel) |
| Social copy / AI draft | Usually a few seconds |
| List brands / gallery / models | Fast |
| Multi-image generate (`num_images` > 1) | Cost and time scale roughly linearly (provider-dependent) |

### 2.9 Recommended screen → API map

| Screen / feature | Endpoints |
|------------------|-----------|
| App boot | `GET /api/brands` (shipped UI does **not** call `/health`; that endpoint is for ops/probes) |
| Brand list / dashboard | `GET /api/brands`, per brand optional `GET /api/brands/{id}` + `GET .../gallery` |
| Create brand wizard | `POST /api/brands/ai-draft` → review → `POST /api/brands` (multipart); wizard does not collect `brand_id` |
| Edit brand | `GET /api/brands/{id}` → `PUT /api/brands/{id}`; logo via `POST .../assets/logo` |
| Creative studio | `GET /api/models`, `GET /api/image-sizes`, `GET /api/brands/{id}`, generate or generate-with-reference, social-copy, optional gallery edit |
| Gallery page | `GET .../gallery`, open `url` (shipped UI has **no** per-image delete) |
| Delete brand | `DELETE /api/brands/{id}` |
| Settings | optional `POST /api/brands/bootstrap-demo` |

### 2.10 Shipped frontend behavior (Rankify React UI)

Verified against `frontend/src` (Creative Studio, brand wizard, dashboard, gallery). Custom integrators may differ.

| Behavior | What the shipped UI does |
|----------|--------------------------|
| Auth client | Sends `x-api-key` on all `/api/*` except paths containing `/health` or `/gallery/raw` |
| Create brand | Multipart `payload` + required `logo`; **no `brand_id` field** → server assigns UUID |
| Studio brief | `studio_campaign.intent` is the visual prompt; `campaign_goal_id` is **always** `"brand_awareness"` (no picker) |
| Generate routing | Reference file present → `POST /api/generate-with-reference`; else `POST /api/generate`. **Never** calls `generate-with-logo` |
| After generate / regenerate / edit | Calls `POST .../text/social-copy` with `image_filename`; on failure, falls back to a **client-side** caption/hashtag draft and still toasts the API error |
| Models | **Always** hides Imagen; omits `image_size` unless `supports_image_size` |
| Default size control | UI state / empty brand form default **`1K`** (API request default when omitted remains **`2K`**) |
| Aspect ratio chips | Only **`1:1`**, **`4:5`**, **`9:16`**, **`16:9`** even if `/api/image-sizes` returns more |
| Platform toggles | LinkedIn, Instagram, X, Facebook, Threads (default chip: LinkedIn) |
| Edit model | Sends the **currently selected studio generate model**, not the API edit default `gemini-2.5-flash-image` |
| Logo display | Authenticated `GET .../assets/logo` → blob object URL; revoke on unmount |
| Downloads | `fetch(url)` → blob; rewrite local `/gallery/raw/...` to same-origin path+query when proxied |
| Pricing fields | Studio ignores `per_image_price_usd` / `total_price_usd` / `message` / `generation_audit_path` |
| Unused by shipped UI | `/health`, `POST /api/generate-with-logo`, `.../text/captions`, `.../text/hashtags`, `DELETE .../gallery/{filename}`, `GET .../gallery/{filename}` (307 redirect) |

There is also an unmounted `GenerateImageModal.jsx` that posts **legacy `content`** to `/api/generate` (no `studio_campaign`); it is **not** in the routed app.

---

## 3. Authentication

### 3.1 API key (primary)

Almost all `/api/*` endpoints require:

| Header | Required | Description |
|--------|----------|-------------|
| `x-api-key` | Yes | Must exactly match the server env var `API_KEY` |

**Failure responses:**

| Status | `detail` | When |
|--------|----------|------|
| `401` | `"Invalid API key."` | Header missing, empty, or wrong |
| `500` | `"API_KEY is not configured on the server."` | Server has no `API_KEY` |

Example:

```http
GET /api/brands HTTP/1.1
Host: localhost:8750
x-api-key: YOUR_API_KEY
```

There is **no JWT, OAuth, cookie session, or per-user RBAC**. Possession of `API_KEY` grants full access to all brands on that server.

### 3.2 Signed gallery raw URLs

`GET /api/brands/{brand_id}/gallery/raw/{filename}` does **not** use `x-api-key`. Instead it requires query parameters produced by the server:

| Query param | Type | Description |
|-------------|------|-------------|
| `exp` | integer (Unix seconds) | Expiration timestamp |
| `sig` | string (hex) | HMAC-SHA256 of `brand_id:filename:exp` using `API_KEY` as secret |

Default TTL: **3600 seconds** (1 hour) via `GALLERY_IMAGE_URL_TTL_SECONDS`.

When `STORAGE_BACKEND=s3`, gallery list/generate responses typically return **S3 presigned GET URLs** instead of Rankify signed raw URLs (TTL from `S3_PRESIGN_TTL_SECONDS`, default **3600**). Clients should treat the `url` field as opaque and fetch it directly (no API key).

Raw endpoint auth error when `API_KEY` missing: `"API_KEY is not configured."` (slightly shorter than the authenticated-route message).

### 3.3 Provider API keys (server-side)

Clients never send Google/OpenAI keys. The server uses:

| Env var | Needed for | Client-visible failure |
|---------|------------|------------------------|
| `GOOGLE_API_KEY` | Gemini and Imagen generation / Gemini edit | `500` with message about `GOOGLE_API_KEY` |
| `OPENAI_API_KEY` | Brand AI draft, social copy, OpenAI image models | `503` with message about `OPENAI_API_KEY` |

---

## 4. Common conventions

### 4.1 Request headers

| Header | When |
|--------|------|
| `x-api-key` | Required on authenticated routes |
| `Content-Type: application/json` | JSON body endpoints only |
| `Content-Type: multipart/form-data` | **Omit** — let the browser set it when using `FormData` |
| `Accept: application/json` | Optional for JSON routes |

### 4.2 `brand_id` path / field rules

Slug validated as:

- Length **2–64** characters
- Lowercase letters, digits, hyphens only
- Must not start or end with a hyphen
- Pattern: `^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`

**Valid examples:** `acme`, `acme-corp`, `demo-ai-certs`, UUID slugs like `a1b2c3d4-e5f6-...`  
**Invalid examples:** `A`, `-acme`, `acme_`, `Acme Corp`, empty string

Invalid values typically yield **422** (request body validation) or **400** (path/filename validation).

### 4.3 Gallery filenames

Must match: `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`  
No path separators (`/`, `\`), no spaces, no empty names.

Server-generated names:

| Pattern | Source |
|---------|--------|
| `rankify_slide_<8hex>_<n>.png` | Generate endpoints (`n` = 1..num_images) |
| `rankify_edit_<10hex>.png` | Gallery edit |

Frontend may pass these filenames into edit, delete, social-copy `image_filename`, and gallery paths.

### 4.4 Error response shape

FastAPI `HTTPException` responses:

```json
{
  "detail": "Human-readable message or structured validation errors"
}
```

Pydantic validation failures (**422**) often return `detail` as an **array** of error objects:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "display_name"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

**Missing header behavior:** If `x-api-key` is entirely omitted on a route that declares it required, FastAPI may return **422** (header validation) rather than **401**. If the header is present but wrong → **401**. Frontend should treat both as “auth/config problem”.

### 4.5 Datetimes

ISO 8601 strings, typically UTC (e.g. `2026-07-15T15:30:00+00:00`). Safe to display with `new Date(iso)`.

### 4.6 Public origin for image URLs

Signed URLs use `PUBLIC_BASE_URL` when set; otherwise the request’s `base_url` (scheme + host). Behind a reverse proxy, ops must set `PUBLIC_BASE_URL` so browsers receive reachable links.

### 4.7 Idempotency and concurrency

| Action | Idempotent? | Notes |
|--------|-------------|-------|
| `POST /api/brands/bootstrap-demo` | Yes | Returns existing brand if present |
| `POST /api/generate*` | No | Each call creates new gallery files |
| `POST .../gallery/edit` | No | Always appends a new `rankify_edit_*.png` |
| `PUT /api/brands/{id}` | Replace | Full document replace; last write wins |
| `DELETE` | Yes if missing → 404 | Treat 404 as already gone in UI if desired |

---

## 5. Shared data models

### 5.1 `StudioCampaignBrief`

Used by social-copy and (optionally) generate endpoints.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `campaign_goal_id` | string | No | `"brand_awareness"` | Legacy field for copy assembly; UI may always send default |
| `platforms` | string[] | No | `[]` | Lowercase platform ids (`linkedin`, `instagram`, `x`, …) |
| `voice_tone_label` | string | No | `"Professional"` | Tone dropdown label |
| `creativity_tone_label` | string | **Yes** | — | Full creativity string (e.g. `"Balanced — on-brand with light creative stretch"`). Required key, but the API accepts `""` (no `min_length`); UI should still require a real value. |
| `intent` | string | **Yes** | — | User content intent / prompt (`min_length=1`). Whitespace-only strings can pass schema; generate then strips — validate non-empty after `.trim()` in the UI. |

**How the server uses this for images vs text:**

| Consumer | Behavior |
|----------|----------|
| Image generate (`studio_campaign` present) | Uses **`intent` primarily** as the visual brief |
| Social-copy | Assembles structured context from platforms/tones/`intent`, then calls OpenAI |

```json
{
  "campaign_goal_id": "brand_awareness",
  "platforms": ["linkedin", "instagram"],
  "voice_tone_label": "Professional",
  "creativity_tone_label": "Balanced — on-brand with light creative stretch",
  "intent": "Announce our new AI certification pathway for mid-career professionals."
}
```

### 5.2 `GalleryImageItem`

Returned inside generate, edit, and gallery list responses.

| Field | Type | Always present? | Description |
|-------|------|-----------------|-------------|
| `filename` | string | Yes | File name in the brand gallery — use for edit/delete/social-copy |
| `url` | string | Yes | Ready-to-use view URL (signed Rankify raw **or** S3 presigned). Prefer this for `<img>` / download. |
| `storage_path` | string | Yes | Logical key: `generated-images/<brand_id>/<filename>` (informational). S3 object keys may use prefix `gallery/`, but this response field always uses the logical `generated-images/...` form. |
| `size_bytes` | integer | Yes | File size in bytes |
| `created_at` | string | Yes | ISO datetime |
| `age_hours` | number | Yes | Age in hours (2 decimal places); `0.0` immediately after generation. Shipped dashboard treats `age_hours ≤ 168` as activity in the last 7 days. |

### 5.3 `BrandSlideGenerateResponse`

Returned by **all** generate endpoints and **gallery edit**.

| Field | Type | Always present? | Description |
|-------|------|-----------------|-------------|
| `images` | `GalleryImageItem[]` | Yes | One or more images (edit usually returns length 1) |
| `model_used` | string | Yes | Echo of the model id used |
| `per_image_price_usd` | number | Yes | Estimated USD per image (hint only) |
| `total_price_usd` | number | Yes | Estimated batch total USD (hint only) |
| `message` | string | Yes | Human summary for toasts |
| `generation_audit_path` | string \| null | Yes | Server filesystem path if audit enabled; **not** a public URL — ignore in UI |

### 5.4 Brand nested objects

#### `BrandColors`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `primary` | string[] | No | `[]` | Hex strings recommended (`#0A2540`) |
| `secondary` | string[] | No | `[]` | |
| `usage_rules` | string | No | `""` | Free text for the model |

#### `BrandTypography`

| Field | Type | Default |
|-------|------|---------|
| `primary_font` | string | `""` |
| `headline_font` | string | `""` |
| `body_font` | string | `""` |
| `notes` | string | `""` |

Fonts are **descriptive hints** for the image model, not web-font loading instructions.

#### `BrandVoice`

| Field | Type | Default |
|-------|------|---------|
| `tone_keywords` | string[] | `[]` |
| `writing_style` | string | `""` |
| `target_audience` | string | `""` |

#### `BrandSocialDefaults`

| Field | Type | Default |
|-------|------|---------|
| `preferred_platforms` | string[] | `[]` |
| `default_aspect_ratio` | string | `"1:1"` |
| `default_image_size` | string | `"2K"` (API schema default). **Shipped brand wizard** often persists **`"1K"`** from its empty-form default. |

UI may prefill studio controls from these after `GET /api/brands/{id}`. Studio falls back to **`1K`** if brand size is missing/invalid.

#### `PlatformSpecificHints`

| Field | Type | Default | Example |
|-------|------|---------|---------|
| `hints` | `{ [platformId: string]: string }` | `{}` | `{ "linkedin": "Prefer professional headroom", "instagram": "Shorter headlines" }` |

#### `BrandContentThemes`

| Field | Type | Default |
|-------|------|---------|
| `categories` | string[] | `[]` |
| `recurring_themes` | string[] | `[]` |

#### `BrandTextPreferences`

| Field | Type | Default |
|-------|------|---------|
| `hashtag_style` | string | `""` |
| `caption_style` | string | `""` |
| `banned_phrases` | string[] | `[]` |

#### `BrandGenerationRules` (required on create/update)

| Field | Type | Required | Validation | Notes |
|-------|------|----------|------------|-------|
| `governance_prompt_template` | string | **Yes** | `min_length=20` | Main brand “bible” / system prompt for images |
| `design_guidelines` | string | No | — | Extra visual rules |
| `layout_spacing_rules` | string | No | — | Margins, safe zones, logo placement |
| `cta_button_rules` | string | No | — | CTA patterns |
| `visual_style_rules` | string | No | — | Imagery / mood |
| `avoid_rules` | string | No | — | Explicit do-not list |
| `slide_intro_template` | string | No | — | Intro before post copy |
| `slide_user_prompt_suffix` | string | No | — | Appended after post copy |

### 5.5 `BrandConfiguration`

Full brand document — response of create/get/put/bootstrap; body of PUT.

| Field | Type | Required | Validation | Notes |
|-------|------|----------|------------|-------|
| `brand_id` | string | Yes | slug rules | Must match path on PUT |
| `display_name` | string | Yes | 1–200 chars | |
| `tagline` | string | No | | |
| `legal_suffix` | string | No | | Trademark line |
| `colors` | `BrandColors` | No | | Defaults to empty object fields |
| `typography` | `BrandTypography` | No | | |
| `voice` | `BrandVoice` | No | | |
| `social_defaults` | `BrandSocialDefaults` | No | | |
| `platform_hints` | `PlatformSpecificHints` | No | | |
| `content_themes` | `BrandContentThemes` | No | | |
| `text_preferences` | `BrandTextPreferences` | No | | |
| `generation` | `BrandGenerationRules` | **Yes** | governance ≥ 20 chars | |
| `logo_asset_filename` | string | No | | Default `"logo.png"` — filename under brand assets |
| `updated_at` | string \| null | No | ISO | Server may set on create; send on PUT if known |

### 5.6 Complete `BrandConfiguration` example

```json
{
  "brand_id": "acme-corp",
  "display_name": "Acme Corp",
  "tagline": "Build with confidence",
  "legal_suffix": "®",
  "colors": {
    "primary": ["#0A2540", "#FF6B4A"],
    "secondary": ["#F5F7FA"],
    "usage_rules": "Navy for backgrounds; coral for CTAs only."
  },
  "typography": {
    "primary_font": "Inter",
    "headline_font": "Montserrat",
    "body_font": "Open Sans",
    "notes": "Avoid script fonts."
  },
  "voice": {
    "tone_keywords": ["Professional", "Clear", "Confident"],
    "writing_style": "Short sentences. Benefit-led.",
    "target_audience": "Mid-level engineers and team leads"
  },
  "social_defaults": {
    "preferred_platforms": ["linkedin", "instagram"],
    "default_aspect_ratio": "1:1",
    "default_image_size": "2K"
  },
  "platform_hints": {
    "hints": {
      "linkedin": "Prefer professional photography metaphors",
      "instagram": "Allow bolder color blocking"
    }
  },
  "content_themes": {
    "categories": ["Product", "Education"],
    "recurring_themes": ["Cloud security", "Certifications"]
  },
  "text_preferences": {
    "hashtag_style": "3–6 mixed brand + topic tags",
    "caption_style": "2–4 sentences, one CTA, minimal emoji",
    "banned_phrases": ["synergy", "disrupt"]
  },
  "generation": {
    "governance_prompt_template": "You design on-brand social slides for Acme Corp. Use navy and coral. Keep layouts clean with ample whitespace and clear hierarchy.",
    "design_guidelines": "One focal headline max; logo top-right safe zone.",
    "layout_spacing_rules": "16px minimum margin from edges.",
    "cta_button_rules": "Pill CTA in coral; white label text.",
    "visual_style_rules": "Modern flat illustration or soft gradients; no clutter.",
    "avoid_rules": "No comic fonts, no neon glow, no stock watermarks.",
    "slide_intro_template": "",
    "slide_user_prompt_suffix": "Respect brand colors and keep CTA readable."
  },
  "logo_asset_filename": "logo.png",
  "updated_at": "2026-07-15T12:00:00+00:00"
}
```

### 5.7 `BrandCreatePayload`

Same shape as configuration except:

| Field | Difference |
|-------|------------|
| `brand_id` | **Optional** — omit or `""` → server assigns a UUID slug |
| `updated_at` | Do not send on create; server sets it |

For `POST /api/brands`, this object is **stringified into the multipart `payload` field**, not sent as raw JSON body.

**Client-side validation recommended before submit:**

| Field | Enforce in UI |
|-------|----------------|
| `display_name` | Non-empty, ≤ 200 chars (Configuration enforces 1–200 on convert; bare create payload may not return a tidy `422` for empty/`>200`) |
| `generation.governance_prompt_template` | ≥ 20 characters |
| `brand_id` (if set) | Valid slug rules from §4.2 |

### 5.8 `BrandSummary`

| Field | Type | Description |
|-------|------|-------------|
| `brand_id` | string | Slug |
| `display_name` | string | Display name |
| `updated_at` | string \| null | Last update |

### 5.9 `BrandStudioSocialCopyRequest` / `Response`

**Request**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `studio_campaign` | `StudioCampaignBrief` | Yes | Studio brief |
| `image_filename` | string \| null | No | Existing gallery filename for vision grounding |

**Response**

| Field | Type | Description |
|-------|------|-------------|
| `caption` | string | Caption text (no guaranteed markdown) |
| `hashtags` | string | Space-separated tags, each starting with `#` — split on spaces for chips. Server normalizes plain words and pads to at least 3 tags. |
| `model_used` | string | OpenAI model used. Internal model is fixed to **`gpt-4o-mini`** (not client-selectable). |

### 5.10 `GalleryImageEditRequest`

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `source_filename` | string | Yes | — | Must exist in brand gallery |
| `instruction` | string | Yes | — | length 3–2000 |
| `model_name` | string | No | `gemini-2.5-flash-image` | Allowed + `supports_edit` |
| `aspect_ratio` | string | No | `1:1` | From `/api/image-sizes` |
| `image_size` | string \| null | No | `2K` | Applied when the selected model has `supports_image_size: true` (Gemini 3 Pro and OpenAI size-aware models), not only Gemini 3 Pro. **Shipped studio edit** sends the current generate model + optional size, not the API Flash default. |

### 5.11 `GalleryListResponse` / `GalleryDeleteResponse`

**List:** `{ "total": number, "images": GalleryImageItem[] }`  
**Delete:** `{ "message": string, "filename": string }`

---

## 6. Health

### `GET /health`

**Auth:** None (public)  
**Purpose:** Liveness / readiness probe and infrastructure status.  
**Shipped UI:** Not called (ops / load balancers only).

#### Response `200`

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` or `"degraded"` |
| `storage_backend` | string | e.g. `"local"` or `"s3"` |
| `database` | string | `"enabled"` or `"disabled"` |
| `gallery_root` | string | Local gallery root path |
| `brand_config_root` | string | Brand config root path |
| `timestamp` | string | UTC ISO datetime |
| `database_status` | string | Present if DB enabled: `"ok"` or `"error: …"` |
| `s3_status` | string | Present if S3 enabled: `"ok"` or `"error: …"` |

If DB or S3 checks fail, `status` becomes `"degraded"` but the HTTP status remains **200**.

#### Example

```bash
curl -s http://localhost:8750/health
```

```json
{
  "status": "ok",
  "storage_backend": "local",
  "database": "disabled",
  "gallery_root": ".../generated-images",
  "brand_config_root": ".../data/brands",
  "timestamp": "2026-07-15T15:30:00+00:00"
}
```

---

## 7. Brands

All brand endpoints require **`x-api-key`**.

---

### 7.1 `GET /api/brands`

**Purpose:** List onboarded brands (lightweight summaries).

#### Response `200`

```json
{
  "brands": [
    {
      "brand_id": "acme-corp",
      "display_name": "Acme Corp",
      "updated_at": "2026-07-15T12:00:00+00:00"
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `brands` | `BrandSummary[]` | Summaries |
| `total` | integer | Count |

#### Errors

| Status | Meaning |
|--------|---------|
| `401` | Invalid API key |
| `500` | `API_KEY` not configured |

---

### 7.2 `POST /api/brands`

**Purpose:** Onboard a new brand with configuration JSON + **required** logo file.  
**Content-Type:** `multipart/form-data`

#### Form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payload` | string (JSON) | **Yes** | Serialized `BrandCreatePayload` |
| `logo` | file | **Yes** | Logo image: `.png`, `.jpg`, `.jpeg`, or `.webp` |

#### Sample request

```bash
curl -X POST "http://localhost:8750/api/brands" \
  -H "x-api-key: YOUR_API_KEY" \
  -F 'payload={
    "brand_id": "acme-corp",
    "display_name": "Acme Corp",
    "tagline": "Build with confidence",
    "generation": {
      "governance_prompt_template": "You are designing on-brand social slides for Acme. Use navy and coral. Keep layouts clean and professional with ample whitespace."
    },
    "colors": {
      "primary": ["#0A2540", "#FF6B4A"],
      "usage_rules": "Navy for backgrounds; coral for CTAs."
    }
  }' \
  -F "logo=@./logo.png;type=image/png"
```

Minimal `payload` (server-assigned `brand_id`):

```json
{
  "display_name": "Acme Corp",
  "generation": {
    "governance_prompt_template": "At least twenty characters of brand governance rules go here."
  }
}
```

#### Response `200`

Full `BrandConfiguration` (JSON), including assigned `brand_id` and `updated_at`.

#### Errors

| Status | `detail` / meaning |
|--------|-------------------|
| `409` | `"brand_id already exists."` |
| `400` | `"Logo must be png, jpg, or webp."` |
| `422` | Invalid `BrandCreatePayload` JSON / field validation |
| `500` | Logo upload failed (brand create is rolled back) |
| `401` | Invalid API key |

**Transaction note:** If logo storage fails after config save, the brand is deleted so the API does not leave a half-created brand.

**Shipped UI:** Create wizard requires a logo and does **not** collect `brand_id` (omitted → server UUID). Edit flow uses `PUT` for config and a separate `POST .../assets/logo` when the user picks a new file.

#### Frontend: `FormData` example

```javascript
async function createBrand(apiBase, apiKey, createPayloadObject, logoFile) {
  const fd = new FormData();
  // IMPORTANT: payload must be a JSON string field, not a Blob of application/json
  fd.append("payload", JSON.stringify(createPayloadObject));
  fd.append("logo", logoFile, logoFile.name || "logo.png");

  const res = await fetch(`${apiBase}/api/brands`, {
    method: "POST",
    headers: { "x-api-key": apiKey }, // do NOT set Content-Type
    body: fd,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(String(data?.detail ?? res.status)), { status: res.status, detail: data?.detail });
  return data; // BrandConfiguration — read data.brand_id for routing
}
```

#### Scenarios

| Scenario | Result |
|----------|--------|
| Valid payload + PNG logo, new `brand_id` | `200` + full config |
| Omit `brand_id` | `200`; server UUID slug in response |
| Duplicate `brand_id` | `409` |
| Governance text &lt; 20 chars | `422` |
| Logo `.gif` / missing logo field | `400` or `422` |
| Invalid JSON in `payload` | `422` with Pydantic errors array |

---

### 7.3 `POST /api/brands/ai-draft`

**Purpose:** Use OpenAI to draft a `BrandCreatePayload` from unstructured materials. **Does not persist** — review then `POST /api/brands`.  
**Requires:** Server `OPENAI_API_KEY`

#### Request body (`BrandAiDraftRequest`)

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `brand_materials` | string | **Yes** | — | `min_length=30`, `max_length=120000` |
| `brand_id` | string \| null | No | `null` | If set, must be valid slug; baked into draft |
| `model_name` | string | No | `"gpt-4o-2024-08-06"` | Must be one of allowed draft models |

**Allowed draft models:**

- `gpt-4o-2024-08-06`
- `gpt-4o-mini`
- `gpt-4o`

#### Sample request

```bash
curl -X POST "http://localhost:8750/api/brands/ai-draft" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_materials": "Acme Corp sells developer tools. Voice is crisp and helpful. Primary color navy #0A2540, accent coral. Never use comic fonts. Target mid-level engineers.",
    "brand_id": "acme-corp",
    "model_name": "gpt-4o-2024-08-06"
  }'
```

#### Response `200` (`BrandAiDraftResponse`)

```json
{
  "draft": {
    "brand_id": "acme-corp",
    "display_name": "Acme Corp",
    "tagline": "Build with confidence",
    "generation": {
      "governance_prompt_template": "You design on-brand social slides for Acme Corp with navy and coral…"
    },
    "colors": { "primary": ["#0A2540", "#FF6B4A"], "secondary": [], "usage_rules": "" },
    "logo_asset_filename": "logo.png"
  },
  "model_used": "gpt-4o-2024-08-06"
}
```

The `draft` object is a full `BrandCreatePayload` (all nested sections may be populated). Map it into your form, let the user edit, then submit via `POST /api/brands` with a logo file. **AI draft does not save the brand.**

| Field | Type | Description |
|-------|------|-------------|
| `draft` | `BrandCreatePayload` | Validated create payload |
| `model_used` | string | Echo of requested model |

#### Errors

| Status | Meaning |
|--------|---------|
| `503` | `"OPENAI_API_KEY is not configured on the server."` |
| `400` | Invalid `model_name` |
| `422` | Model refusal, empty parse, or schema mismatch |
| `502` | OpenAI empty message / draft call failed |
| `401` | Invalid API key |

---

### 7.4 `POST /api/brands/bootstrap-demo`

**Purpose:** Create the packaged demo brand `demo-ai-certs` if missing. **Idempotent** — if it exists, returns the existing config.

#### Request body

None.

#### Response `200`

`BrandConfiguration` for `demo-ai-certs`.

**Logo caveat:** Bootstrap saves configuration only — it does **not** upload a logo file. Until `POST /api/brands/demo-ai-certs/assets/logo`, generation uses `assets/default_logo.jpg`.

#### Errors

| Status | Meaning |
|--------|---------|
| `401` / `500` | Auth / server key issues |

---

### 7.5 `GET /api/brands/{brand_id}`

**Purpose:** Fetch full brand configuration.

#### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `brand_id` | string | Brand slug (must already be a valid slug from the API) |

#### Response `200`

`BrandConfiguration`

#### Errors

| Status | `detail` |
|--------|----------|
| `404` | `"Brand not found: {brand_id}"` |
| `401` | Invalid API key |

**Slug note:** Always use `brand_id` values returned by the API. Malformed path slugs can raise an unhandled server error (**500**) rather than a tidy `400`/`404`.

---

### 7.6 `PUT /api/brands/{brand_id}`

**Purpose:** Replace entire brand configuration (full document replace).

#### Path parameters

| Name | Type |
|------|------|
| `brand_id` | string |

#### Request body

Full `BrandConfiguration`. **`body.brand_id` must equal path `brand_id`.**

#### Sample request

```bash
curl -X PUT "http://localhost:8750/api/brands/acme-corp" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": "acme-corp",
    "display_name": "Acme Corp",
    "tagline": "Updated tagline",
    "generation": {
      "governance_prompt_template": "Updated governance text that is long enough for validation."
    },
    "logo_asset_filename": "logo.png"
  }'
```

#### Response `200`

The saved `BrandConfiguration` (request body as stored).

#### Errors

| Status | `detail` |
|--------|----------|
| `400` | `"brand_id in path and body must match."` |
| `404` | `"Brand not found."` |
| `422` | Body validation failure |
| `401` | Invalid API key |

**Note:** This does not upload a new logo; use the logo asset endpoints for that. Changing `logo_asset_filename` only changes the expected filename under brand assets.

---

### 7.7 `DELETE /api/brands/{brand_id}`

**Purpose:** Delete brand configuration, assets, and the brand’s gallery. Destructive.

- **Local storage:** Removes brand config and the on-disk gallery folder under `generated-images/{brand_id}/`.
- **S3 + DB mode:** Removes DB brand/metadata rows; the local gallery tree is cleared if present. **S3 objects for that brand may remain** until TTL purge or separate ops cleanup — do not assume immediate blob deletion.

#### Response `200`

```json
{
  "message": "Brand acme-corp and its gallery folder removed.",
  "brand_id": "acme-corp"
}
```

#### Errors

| Status | `detail` |
|--------|----------|
| `404` | `"Brand not found."` |
| `401` | Invalid API key |

---

## 8. Brand assets

### 8.1 `POST /api/brands/{brand_id}/assets/logo`

**Purpose:** Upload or replace the brand logo file (stored under the brand’s configured `logo_asset_filename`).  
**Content-Type:** `multipart/form-data`

#### Form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | **Yes** | `.png` / `.jpg` / `.jpeg` / `.webp` |

#### Response `200`

```json
{
  "message": "Logo saved.",
  "path": "<storage path or key>"
}
```

#### Errors

| Status | Meaning |
|--------|---------|
| `404` | Brand not found |
| `400` | Invalid logo type |
| `500` | Storage / OS error |
| `401` | Invalid API key |

---

### 8.2 `GET /api/brands/{brand_id}/assets/logo`

**Purpose:** Download the configured logo file.

#### Response `200`

Binary image (`FileResponse`) with appropriate `Content-Type` (`image/png`, `image/jpeg`, `image/webp`).

#### Errors

| Status | `detail` |
|--------|----------|
| `404` | Brand not found, or `"No logo file for this brand yet."` |
| `401` | Invalid API key |

#### Frontend: load logo into `<img>`

```javascript
async function fetchBrandLogoObjectUrl(apiBase, apiKey, brandId) {
  const res = await fetch(
    `${apiBase}/api/brands/${encodeURIComponent(brandId)}/assets/logo`,
    { headers: { "x-api-key": apiKey } },
  );
  if (res.status === 404) return null; // no logo yet — show placeholder
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob); // revoke on unmount
}
```

---

## 9. Brand text (social copy)

All three routes share the same request/response and business logic. Captions/hashtags endpoints exist for older clients.

**Requires:** Server `OPENAI_API_KEY`  
**Internal model:** Always **`gpt-4o-mini`** (not selectable).

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/brands/{brand_id}/text/social-copy` | Canonical — **used by shipped UI** |
| `POST` | `/api/brands/{brand_id}/text/captions` | Alias — same body/response (**not used by shipped UI**) |
| `POST` | `/api/brands/{brand_id}/text/hashtags` | Alias — same body/response (**not used by shipped UI**) |

### 9.1 Request body (`BrandStudioSocialCopyRequest`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `studio_campaign` | `StudioCampaignBrief` | **Yes** | Studio brief |
| `image_filename` | string \| null | No | Gallery filename; if set and present, used as vision input |

### 9.2 Response `200` (`BrandStudioSocialCopyResponse`)

| Field | Type | Description |
|-------|------|-------------|
| `caption` | string | Social caption |
| `hashtags` | string | Space-separated tags, each starting with `#` |
| `model_used` | string | Typically `gpt-4o-mini` |

### 9.3 Sample request

```bash
curl -X POST "http://localhost:8750/api/brands/acme-corp/text/social-copy" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "studio_campaign": {
      "platforms": ["linkedin"],
      "voice_tone_label": "Professional",
      "creativity_tone_label": "Balanced — on-brand with light creative stretch",
      "intent": "Launch of our cloud security badge for DevOps teams."
    },
    "image_filename": "rankify_slide_a1b2c3d4_1.png"
  }'
```

### 9.4 Sample success response

```json
{
  "caption": "Introducing our Cloud Security Badge for DevOps teams…",
  "hashtags": "#CloudSecurity #DevOps #AcmeCorp",
  "model_used": "gpt-4o-mini"
}
```

### 9.5 Errors

| Status | Meaning |
|--------|---------|
| `503` | `OPENAI_API_KEY` missing |
| `404` | Brand not found |
| `400` | `"Gallery image not found: …"` or unsupported image type for vision |
| `422` | Model refusal / empty caption / no structured output |
| `502` | `"OpenAI social copy failed: …"` (upstream OpenAI failure) |
| `401` | Invalid API key |

**Side effect:** When database mode is enabled, a social-copy history row may be stored (optionally linked to the gallery image).

---

## 10. Models and image sizes

### 10.1 `GET /api/models`

**Purpose:** List supported image models with capability flags and pricing hints.

#### Response `200`

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
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `model_name` | string | Pass as `model_name` / `model_id` to generate/edit |
| `provider` | string | `gemini` \| `openai` \| `imagen` |
| `label` | string | Human label |
| `supports_image_size` | boolean | Whether size tiers apply |
| `supports_generate` | boolean | Usable on generate endpoints |
| `supports_edit` | boolean | Usable on gallery edit |
| `pricing` | object | Optional size → USD map |
| `price_per_image_usd` | number | Optional flat USD hint |

**Known `model_name` values (at time of writing):**

| model_name | Provider | Generate | Edit | Image size |
|------------|----------|----------|------|------------|
| `gemini-3-pro-image-preview` | gemini | Yes | Yes | Yes |
| `gemini-2.5-flash-image` | gemini | Yes | Yes | No |
| `openai:gpt-image-2` | openai | Yes | Yes | Yes |
| `openai:gpt-image-1` | openai | Yes | Yes | Yes |
| `openai:gpt-image-1-mini` | openai | Yes | Yes | No |
| `openai:gpt-image-1.5` | openai | Yes | Yes | Yes |
| `imagen-4.0-fast-generate-001` | imagen | Yes | **No** | No\* |
| `imagen-4.0-generate-001` | imagen | Yes | **No** | No\* |
| `imagen-4.0-ultra-generate-001` | imagen | Yes | **No** | No\* |

\*Imagen catalog entries set `supports_image_size: false`; pricing tables may still show size tiers as hints.

OpenAI model ids are **namespaced** with the `openai:` prefix.

**Pricing gaps:** `openai:gpt-image-2` may appear **without** a `pricing` / `price_per_image_usd` field in the catalog; generate still returns a numeric `per_image_price_usd` (typically defaulting near **0.1**). Treat all prices as estimates.

---

### 10.2 `GET /api/image-sizes`

**Purpose:** List allowed aspect ratios and image size tokens.

#### Response `200`

```json
{
  "image_sizes": ["1K", "2K", "4K"],
  "note": "Image size applies to gemini-3-pro-image-preview and OpenAI gpt-image-1 / gpt-image-2 models.",
  "aspect_ratios": [
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
  ]
}
```

**Frontend rule:** Prefer each model’s `supports_image_size` flag from `GET /api/models` over the static `note` string. Size-aware models today include:

- `gemini-3-pro-image-preview`
- `openai:gpt-image-1`
- `openai:gpt-image-1.5`
- `openai:gpt-image-2`

For OpenAI, `1K`/`2K`/`4K` strongly affect high-res behavior on **`openai:gpt-image-2`**; other OpenAI image models mainly map aspect ratio to fixed pixel sizes (size token may have little visual effect).

---

## 11. Image generation

All generate endpoints require **`x-api-key`** and write results into the brand gallery.

**Logo resolution order (all generate endpoints):** multipart logo override (if any) → brand logo asset → `assets/default_logo.jpg` fallback.

**Send only `model_name` values returned by `GET /api/models`.** Do not invent prefixes (`gemini:`, bare OpenAI ids without `openai:`).

---

### 11.1 `POST /api/generate`

**Purpose:** Generate brand slides from JSON. Uses brand logo (or default).  
**Content-Type:** `application/json`

#### Request body (`BrandSlideGenerateRequest`)

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `brand_id` | string | **Yes** | — | Must exist |
| `studio_campaign` | `StudioCampaignBrief` \| null | Conditional | `null` | If set, used for prompt intent |
| `content` | string \| null | Conditional | `null` | Legacy structured copy; required if no `studio_campaign` |
| `model_name` | string | No | `"gemini-3-pro-image-preview"` | Must be allowed model |
| `num_images` | integer | No | `1` | `1`–`10` |
| `aspect_ratio` | string | No | `"1:1"` | Must be allowed ratio |
| `image_size` | string \| null | No | `"2K"` | Required valid when model supports size |

**Validator:** Provide **at least one** of `studio_campaign` or a non-empty `content` string. If **both** are present, **`studio_campaign` wins** (`content` is ignored).

When `studio_campaign` is set, the server uses the brief’s `intent` (verbatim after strip for generation) as the image user brief.

#### Sample — studio campaign

```bash
curl -X POST "http://localhost:8750/api/generate" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": "acme-corp",
    "studio_campaign": {
      "platforms": ["instagram"],
      "voice_tone_label": "Confident",
      "creativity_tone_label": "Bold — striking visuals welcome",
      "intent": "Hero slide: Cloud Security Badge now open for enrollment"
    },
    "model_name": "gemini-3-pro-image-preview",
    "num_images": 2,
    "aspect_ratio": "1:1",
    "image_size": "2K"
  }'
```

#### Sample — legacy content

```json
{
  "brand_id": "acme-corp",
  "content": "TITLE: Cloud Security Badge\nSUBTITLE: For DevOps teams\nBODY: Enroll now\nCTA: Learn more",
  "model_name": "openai:gpt-image-2",
  "num_images": 1,
  "aspect_ratio": "16:9",
  "image_size": "2K"
}
```

#### Response `200`

`BrandSlideGenerateResponse` — see [§5.3](#53-brandslidegenerateresponse).

```json
{
  "images": [
    {
      "filename": "rankify_slide_a1b2c3d4_1.png",
      "url": "http://localhost:8750/api/brands/acme-corp/gallery/raw/rankify_slide_a1b2c3d4_1.png?exp=...&sig=...",
      "storage_path": "generated-images/acme-corp/rankify_slide_a1b2c3d4_1.png",
      "size_bytes": 412000,
      "created_at": "2026-07-15T15:40:00+00:00",
      "age_hours": 0.0
    }
  ],
  "model_used": "gemini-3-pro-image-preview",
  "per_image_price_usd": 0.134,
  "total_price_usd": 0.268,
  "message": "Successfully generated 2 slide(s) for brand 'acme-corp'.",
  "generation_audit_path": null
}
```

Pricing fields are **estimates**. Note: **`openai:gpt-image-2`** has no catalog pricing entry; `per_image_price_usd` falls back to about **`0.1`**.

#### Errors

| Status | Typical cause |
|--------|----------------|
| `404` | Brand not found |
| `400` | Invalid model / aspect_ratio / image_size; Imagen + reference (other endpoints); provider validation |
| `422` | Request validator (`content`/`studio_campaign`); Gemini (and similar) provider returned no image |
| `500` | Missing `GOOGLE_API_KEY` for Gemini/Imagen; some Imagen / OpenAI multi-image batch failures may also surface as unhandled `500` |
| `503` | Missing `OPENAI_API_KEY` for OpenAI models |
| `502` | Upstream generation failure (mapped primarily on the Gemini single-slide path) |
| `401` | Invalid API key |

**Provider notes:**

- **Gemini:** Logo + full governance system prompt applied; per-slide `422`/`502` mapping is the most complete.
- **OpenAI:** Logo applied via edit/generate path; multi-image (`num_images` > 1) may be one provider call with `n`. Size tiers matter most for `openai:gpt-image-2`.
- **Imagen:** Chunks of up to **4** images per provider call (`num_images` 5–10 → multiple calls). Uses the **slide user prompt only** — **brand logo and governance system prompt are not applied**. Prefer Gemini/OpenAI for on-brand logo slides. **No style reference.** **No gallery edit** (`supports_edit: false`).

#### Frontend JSON example

```javascript
const studio_campaign = {
  campaign_goal_id: "brand_awareness",
  platforms: ["linkedin"],
  voice_tone_label: "Professional",
  creativity_tone_label: "Balanced — on-brand with light creative stretch",
  intent: promptText.trim(),
};

const data = await apiJson(apiBase, apiKey, "/api/generate", {
  method: "POST",
  body: {
    brand_id: brandId,
    studio_campaign,
    model_name: modelName,
    num_images: imageCount,
    aspect_ratio: aspectRatio,
    // Only include when catalog.supports_image_size === true
    ...(supportsImageSize ? { image_size: imageSize } : {}),
  },
});
// data.images[i].url → <img>, data.images[i].filename → edit / social-copy
```

#### Scenarios

| Scenario | Result |
|----------|--------|
| Valid `studio_campaign` + existing brand | `200` with `images.length === num_images` |
| Both `content` and `studio_campaign` | `200`; studio path used |
| Only whitespace `content`, no studio | `422` validation |
| Unknown `model_name` | `400` listing allowed models |
| Bad `aspect_ratio` | `400` |
| Size model with invalid `image_size` | `400` |
| Missing Google key + Gemini/Imagen model | `500` |
| Missing OpenAI key + `openai:*` model | `503` |
| Gemini provider returns no image | `422` |
| Upstream crash (mapped paths) | `502` |
| Unknown brand | `404` |

---

### 11.2 `POST /api/generate-with-logo`

**Purpose:** Generate slides via multipart form, with optional one-off logo override.  
**Content-Type:** `multipart/form-data`  
**Shipped UI:** Not used (Creative Studio uses `/api/generate` or `/api/generate-with-reference`). Still supported for API clients.

#### Form fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `brand_id` | string | **Yes** | — | Brand slug |
| `content` | string | **Yes** | — | Structured/post copy text (not studio JSON) |
| `model_name` | string | No | `gemini-3-pro-image-preview` | |
| `num_images` | integer | No | `1` | `1`–`10` |
| `aspect_ratio` | string | No | `1:1` | |
| `image_size` | string | No | `2K` | |
| `logo` | file | No | — | Optional override for this batch only |

#### Sample

```bash
curl -X POST "http://localhost:8750/api/generate-with-logo" \
  -H "x-api-key: YOUR_API_KEY" \
  -F "brand_id=acme-corp" \
  -F "content=TITLE: Launch Day\nCTA: Register" \
  -F "model_name=gemini-2.5-flash-image" \
  -F "num_images=1" \
  -F "aspect_ratio=1:1" \
  -F "image_size=2K" \
  -F "logo=@./alt-logo.png"
```

#### Response / errors

Same shape and error classes as `POST /api/generate`.

#### Frontend `FormData` example

```javascript
const fd = new FormData();
fd.append("brand_id", brandId);
fd.append("content", structuredCopyText);
fd.append("model_name", modelName);
fd.append("num_images", String(numImages));
fd.append("aspect_ratio", aspectRatio);
fd.append("image_size", imageSize); // send only if model supports size
if (logoFile) fd.append("logo", logoFile);

const res = await fetch(`${apiBase}/api/generate-with-logo`, {
  method: "POST",
  headers: { "x-api-key": apiKey },
  body: fd,
});
```

---

### 11.3 `POST /api/generate-with-reference`

**Purpose:** Generate from a studio campaign JSON string, optionally with a **style/layout reference image** and/or logo override.  
**Content-Type:** `multipart/form-data`

#### Form fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `brand_id` | string | **Yes** | — | |
| `studio_campaign` | string (JSON) | **Yes** | — | Must match `StudioCampaignBrief` |
| `model_name` | string | No | `gemini-3-pro-image-preview` | |
| `num_images` | integer | No | `1` | `1`–`10` |
| `aspect_ratio` | string | No | `1:1` | |
| `image_size` | string | No | `2K` | |
| `reference_image` | file | No | — | Optional style/layout inspiration (omit to send studio JSON only) |
| `logo` | file | No | — | Optional logo override |

#### Sample

```bash
curl -X POST "http://localhost:8750/api/generate-with-reference" \
  -H "x-api-key: YOUR_API_KEY" \
  -F "brand_id=acme-corp" \
  -F 'studio_campaign={"platforms":["instagram"],"voice_tone_label":"Bold","creativity_tone_label":"Bold — striking visuals welcome","intent":"Summer campaign hero"}' \
  -F "model_name=gemini-3-pro-image-preview" \
  -F "num_images=1" \
  -F "aspect_ratio=4:5" \
  -F "image_size=2K" \
  -F "reference_image=@./moodboard.png" \
  -F "logo=@./logo.png"
```

#### Extra errors / notes

| Status | `detail` |
|--------|----------|
| `400` | `"Invalid studio_campaign JSON: …"` |
| `400` | Style reference not supported with **Imagen** models |

`reference_image` is optional — the endpoint is still valid without a file (studio brief as multipart + model/size fields). When a reference **is** attached, use Gemini or OpenAI, not Imagen.

#### Frontend `FormData` example

```javascript
async function generateWithReference(apiBase, apiKey, {
  brandId, studioCampaign, modelName, numImages, aspectRatio, imageSize, supportsImageSize, referenceFile, logoFile,
}) {
  const fd = new FormData();
  fd.append("brand_id", brandId);
  fd.append("studio_campaign", JSON.stringify(studioCampaign)); // must be a string
  fd.append("model_name", modelName);
  fd.append("num_images", String(numImages));
  fd.append("aspect_ratio", aspectRatio);
  if (supportsImageSize) fd.append("image_size", imageSize);
  if (referenceFile) fd.append("reference_image", referenceFile);
  if (logoFile) fd.append("logo", logoFile);

  const res = await fetch(`${apiBase}/api/generate-with-reference`, {
    method: "POST",
    headers: { "x-api-key": apiKey },
    body: fd,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail));
    err.status = res.status;
    throw err;
  }
  return data; // BrandSlideGenerateResponse
}
```

---

## 12. Gallery

Brand must exist for list/edit/delete/view (API key routes). Raw streaming uses signatures instead.

---

### 12.1 `GET /api/brands/{brand_id}/gallery`

**Purpose:** List gallery images for a brand (newest first).

#### Response `200` (`GalleryListResponse`)

```json
{
  "total": 1,
  "images": [
    {
      "filename": "rankify_slide_a1b2c3d4_1.png",
      "url": "https://…",
      "storage_path": "generated-images/acme-corp/rankify_slide_a1b2c3d4_1.png",
      "size_bytes": 412000,
      "created_at": "2026-07-15T15:40:00+00:00",
      "age_hours": 1.25
    }
  ]
}
```

#### Errors

| Status | Meaning |
|--------|---------|
| `404` | Brand not found |
| `502` | Storage listing failure |
| `401` | Invalid API key |

---

### 12.2 `POST /api/brands/{brand_id}/gallery/edit`

**Purpose:** AI-edit an existing gallery image with a text instruction; writes a new `rankify_edit_*.png` and returns a generate-shaped response.  
**Does not overwrite** the source file.

#### Request body (`GalleryImageEditRequest`)

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `source_filename` | string | **Yes** | — | Valid gallery filename that exists |
| `instruction` | string | **Yes** | — | `min_length=3`, `max_length=2000` |
| `model_name` | string | No | `"gemini-2.5-flash-image"` | Allowed model that supports edit |
| `aspect_ratio` | string | No | `"1:1"` | Allowed ratio |
| `image_size` | string \| null | No | `"2K"` | Used when model supports size (e.g. Gemini 3 Pro / OpenAI size models) |

#### Sample

```bash
curl -X POST "http://localhost:8750/api/brands/acme-corp/gallery/edit" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "source_filename": "rankify_slide_a1b2c3d4_1.png",
    "instruction": "Change the CTA button text to Enroll Today and keep everything else identical.",
    "model_name": "gemini-2.5-flash-image",
    "aspect_ratio": "1:1",
    "image_size": "2K"
  }'
```

#### Response `200`

`BrandSlideGenerateResponse` with **exactly one** image in `images[]`. Success message shape:

`Edited image saved for brand '<brand_id>' (refined from '<source_filename>').`

#### Errors

| Status | Meaning |
|--------|---------|
| `404` | Brand not found; `"Source image not found in gallery."` |
| `400` | Invalid model/ratio/size/filename; unreadable source; **or** Imagen model id accepted by allow-list then rejected at dispatch: `"Model provider not supported for edit: imagen"` |
| `422` | Model declined / no image output (with retry hint) |
| `502` | Edit pipeline failure |
| `500` / `503` | Missing Google / OpenAI keys as applicable |
| `401` | Invalid API key |

**Constraint:** Filter edit UI to models with `supports_edit: true` (Gemini + OpenAI). The server allows any id in `ALLOWED_IMAGE_MODEL_IDS`, so sending Imagen fails later with **400**.

---

### 12.3 `GET /api/brands/{brand_id}/gallery/{filename}`

**Auth:** `x-api-key`  
**Purpose:** Redirect (**307**) to a time-limited view URL (signed raw or S3 presigned).  
**Shipped UI:** Not used — prefers `url` from list/generate responses.

#### Path parameters

| Name | Description |
|------|-------------|
| `brand_id` | Brand slug |
| `filename` | Gallery filename |

#### Response `307`

`Location` header set to the view URL.

#### Errors

| Status | `detail` |
|--------|----------|
| `400` | `"Invalid filename."` |
| `404` | Brand or `"Image not found."` |
| `401` | Invalid API key |

---

### 12.4 `GET /api/brands/{brand_id}/gallery/raw/{filename}`

**Auth:** Query signature (`exp`, `sig`) — **not** `x-api-key`  
**Purpose:** Stream the image file bytes (local storage path).

#### Path parameters

| Name | Description |
|------|-------------|
| `brand_id` | Brand slug (URL-encoded ok) |
| `filename` | Gallery filename (URL-encoded ok) |

#### Query parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `exp` | integer | **Yes** | Unix expiry |
| `sig` | string | **Yes** | HMAC-SHA256 hex of `brand_id:filename:exp` with secret=`API_KEY` |

#### Response `200`

Binary image (`FileResponse`) with `Content-Type` derived from extension; `Content-Disposition` filename set.

#### Errors

| Status | `detail` |
|--------|----------|
| `400` | `"Invalid brand_id or filename."` |
| `401` | `"Invalid or expired signature."` |
| `404` | `"Image not found."` |
| `500` | `"API_KEY is not configured."` |

**Integrator tip:** Prefer using the `url` returned by list/generate endpoints. Do not invent signatures client-side unless you also hold `API_KEY` (not recommended for browser apps).

**S3 note:** With S3 storage, list/generate URLs usually point at S3; this raw endpoint remains for local/signed serving.

---

### 12.5 `DELETE /api/brands/{brand_id}/gallery/{filename}`

**Purpose:** Delete one gallery image.  
**Shipped UI:** Gallery page does **not** call this (custom clients may).

#### Response `200` (`GalleryDeleteResponse`)

```json
{
  "message": "Image deleted.",
  "filename": "rankify_slide_a1b2c3d4_1.png"
}
```

#### Errors

| Status | `detail` |
|--------|----------|
| `400` | `"Invalid filename."` |
| `404` | Brand or image not found |
| `502` | Storage delete failure |
| `401` | Invalid API key |

---

## 13. Legacy endpoints

These routes always return **410 Gone** and are hidden from OpenAPI schema. Use brand-scoped gallery URLs instead.

| Method | Path | `detail` guidance |
|--------|------|-------------------|
| `GET` | `/api/gallery` | Use `GET /api/brands/{brand_id}/gallery` |
| `GET` | `/api/gallery/{filename}` | Use brand-scoped gallery URLs |
| `GET` | `/api/gallery/raw/{filename}` | Use `GET /api/brands/{brand_id}/gallery/raw/{filename}` |
| `DELETE` | `/api/gallery/{filename}` | Use `DELETE /api/brands/{brand_id}/gallery/{filename}` |

Example:

```json
{
  "detail": "Use GET /api/brands/{brand_id}/gallery. Onboard brands via POST /api/brands or POST /api/brands/bootstrap-demo."
}
```

---

## 14. Error handling

There are **no custom application error codes** beyond HTTP status + `detail` (string or array). Frontend should branch primarily on **`res.status`**, and show **`detail`** to the user (stringified safely).

### 14.1 Status code reference

| HTTP status | Common meaning in Rankify | Suggested UI treatment |
|-------------|---------------------------|------------------------|
| `200` | Success (including degraded health payload) | Proceed; for health, check `status === "ok"` |
| `307` | Temporary redirect to gallery view URL | Follow automatically (`fetch` default); prefer using list `url` instead |
| `400` | Client validation (model, ratio, size, logo type, JSON, filename, brand_id mismatch) | Fix inputs; show `detail` |
| `401` | Bad API key **or** expired gallery signature | Settings: re-enter API key; gallery: refresh list for new URLs |
| `404` | Brand, logo, or gallery image missing | Navigate away / empty state |
| `409` | Brand id already exists | Ask user for a different slug |
| `410` | Legacy gallery API removed | Update client to brand-scoped paths |
| `422` | Schema validation; model refusal; provider no-image | Show message; for edit, suggest shorter instruction / other model |
| `500` | Misconfigured `API_KEY` / `GOOGLE_API_KEY`, or upload failure | Ops / server config issue |
| `502` | Upstream provider or storage failure | Retry later |
| `503` | Missing `OPENAI_API_KEY` for OpenAI features | Ops: configure OpenAI key; hide AI-draft/social-copy if appropriate |

### 14.2 Parsing `detail` in the browser

```javascript
function userMessageFromErrorBody(status, body) {
  const detail = body && typeof body === "object" ? body.detail : body;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Pydantic v2 style
    return detail
      .map((e) => {
        const loc = Array.isArray(e.loc) ? e.loc.filter((x) => x !== "body").join(".") : "";
        return loc ? `${loc}: ${e.msg}` : e.msg || JSON.stringify(e);
      })
      .join("; ");
  }
  if (detail != null) return JSON.stringify(detail);
  return `Request failed (${status})`;
}
```

### 14.3 Distinguishing auth failures

| Symptom | Likely cause |
|---------|--------------|
| `422` mentioning `x-api-key` / header | Header omitted |
| `401` `"Invalid API key."` | Wrong key |
| `401` `"Invalid or expired signature."` | Stale gallery `url` — call `GET .../gallery` again |
| `500` `"API_KEY is not configured..."` | Server misconfiguration |

### 14.4 Network vs HTTP errors

`fetch` network failures (`TypeError`) mean the browser never reached a valid HTTP response (server down, CORS blocked rarely with `*`, wrong base URL). Show a distinct “cannot reach API” message — do not parse as `detail`.

---

## 15. End-to-end frontend scenarios

Scenarios below describe both a **recommended integrator flow** and notes where the **shipped Rankify React UI** differs (see also [§2.10](#210-shipped-frontend-behavior-rankify-react-ui)).

### 15.1 First-run / empty database

1. (Optional ops) `GET /health` → expect `200`, prefer `status: "ok"`. **Shipped UI skips this.**
2. Prompt for API key; store locally.
3. Optional: `POST /api/brands/bootstrap-demo` (empty body) from Settings → use brand `demo-ai-certs`.
4. `GET /api/brands` → render dashboard cards from `brands[]`.

### 15.2 Onboard a custom brand

1. User pastes brand notes (≥ 30 chars) → `POST /api/brands/ai-draft` (shipped UI hardcodes `model_name: "gpt-4o-2024-08-06"`).
2. Map `response.draft` into a form (nested objects as in §5.5).
3. User edits + selects logo file → `POST /api/brands` multipart (`payload` JSON string + `logo`).
4. **Shipped create wizard does not collect `brand_id`** — server assigns a UUID. `409` conflicts are rare unless an AI draft injected a slug that already exists.
5. Route to studio/gallery using `response.brand_id`.
6. Prefill logo preview later via authenticated `GET .../assets/logo` → blob URL.

**Failure path:** `422` on governance length → show field error; `503` on ai-draft → allow manual form without AI.

### 15.3 Creative studio generate + caption

1. Parallel load: `GET /api/brands/{id}`, `GET /api/models`, `GET /api/image-sizes`.
2. Prefill aspect/size from `brand.social_defaults` when valid; shipped UI size fallback is **`1K`**.
3. **Always hide Imagen** models. Filter aspect chips to `1:1`, `4:5`, `9:16`, `16:9` if matching shipped UI.
4. Build `studio_campaign` with `campaign_goal_id: "brand_awareness"`, platforms, tones, and non-empty trimmed `intent`.
5. If reference file present → `POST /api/generate-with-reference` (no logo field in shipped UI); else `POST /api/generate`.
6. Show `images[].url`; keep `images[].filename` in state.
7. `POST /api/brands/{id}/text/social-copy` with same studio brief + `image_filename: images[0].filename`.
8. Split `hashtags` on spaces for chips; show `caption`. **On social-copy failure**, shipped UI uses a local caption/hashtag draft and still toasts the API error.

### 15.4 Edit an existing slide

1. User selects a gallery item (`filename` from list or prior generate).
2. Prefer models with `supports_edit: true` (shipped UI reuses the Imagen-filtered generate list).
3. `POST /api/brands/{id}/gallery/edit` with `source_filename`, `instruction` (3–2000 chars), and the **current studio model** (not necessarily the API default Flash edit model).
4. Append returned image to version history; **do not** delete the source unless user asks.
5. Re-run social-copy against the new filename (shipped UI does this).
6. On `422`, show server hint (often: shorten instruction / try another model / edit from original).

### 15.5 Gallery management

1. `GET /api/brands/{id}/gallery` → already newest-first.
2. Render grid with `url`; on image load error / download `401`, refresh gallery.
3. Per-image delete via `DELETE /api/brands/{id}/gallery/{filename}` is available to API clients but **not implemented in the shipped gallery page**.
4. Do not use legacy `/api/gallery` paths (`410`).

### 15.6 Update brand settings

1. `GET /api/brands/{id}` → form.
2. Save: `PUT /api/brands/{id}` with full `BrandConfiguration` where `body.brand_id === path id` (shipped UI also sets `updated_at` to now).
3. Logo change: `POST /api/brands/{id}/assets/logo` with `file` field (does not require PUT).
4. `400` if path/body id mismatch.

### 15.7 Delete brand

1. Confirm destructive action (config + gallery).
2. `DELETE /api/brands/{id}` → remove from client brand list (`loadBrands` refresh).
3. `404` if already deleted — treat as success in UI if desired.

---

## 16. Business rules and operational notes

### 16.1 Typical client flow

1. (Optional) `GET /health` — ops only; shipped UI skips.
2. `POST /api/brands/bootstrap-demo` (Settings) or `POST /api/brands` (optionally after AI draft).
3. `GET /api/models` + `GET /api/image-sizes` — populate UI selectors.
4. `POST /api/generate` or `POST /api/generate-with-reference` — create slides.
5. `GET /api/brands/{brand_id}/gallery` — show history; use returned `url`s to display images.
6. `POST .../text/social-copy` and optionally `POST .../gallery/edit`.
7. `DELETE /api/brands/{brand_id}` as needed (shipped UI does not delete individual gallery files).

### 16.2 Gallery retention

Background job purges gallery images older than `IMAGE_TTL_HOURS` (default **720** = 30 days) about every **900 seconds**.

### 16.3 Pricing fields

`per_image_price_usd` / `total_price_usd` and model `pricing` fields are **estimates/hints**, not live billing from Google/OpenAI invoices. Models without a catalog price entry (notably **`openai:gpt-image-2`**) still return a numeric estimate via `estimate_price_usd` fallback (~`0.1`).

### 16.4 Audit files

When `RANKIFY_GENERATION_AUDIT=1`, generate may return `generation_audit_path` pointing at a server-side UTF-8 prompt audit file. Not intended for end-user download via API.

### 16.5 Storage modes

| Mode | Env | Gallery `url` behavior |
|------|-----|------------------------|
| Local | `STORAGE_BACKEND=local` (default) | HMAC-signed Rankify raw URLs (`GALLERY_IMAGE_URL_TTL_SECONDS`, default 3600) |
| S3 | `STORAGE_BACKEND=s3` (+ `DATABASE_URL` required) | S3/R2 presigned GET URLs (`S3_PRESIGN_TTL_SECONDS`, default 3600) |

Response `storage_path` is always the logical key `generated-images/<brand_id>/<filename>`, even when the S3 object key uses `S3_GALLERY_PREFIX` (default `gallery/`).

### 16.6 Environment variables (ops / frontend awareness)

| Variable | Required for | Frontend impact |
|----------|--------------|-----------------|
| `API_KEY` | Auth + URL signing | Clients must send matching `x-api-key` |
| `GOOGLE_API_KEY` | Gemini / Imagen | Missing → `500` on those models |
| `OPENAI_API_KEY` | AI draft, social-copy, OpenAI images | Missing → `503` on those features |
| `PUBLIC_BASE_URL` | Correct signed links behind proxies | Broken image URLs if unset behind reverse proxy |
| `IMAGE_TTL_HOURS` | Gallery purge (default 720) | Old images disappear from gallery |
| `STORAGE_BACKEND` | `local` \| `s3` | Changes shape of `url` (Rankify vs S3) |
| `DATABASE_URL` | DB mode; required if S3 | Enables history / S3 metadata |
| `S3_PRESIGN_TTL_SECONDS` | S3 URL lifetime | Image link expiry |
| `LOCAL_IMAGE_STORAGE_DIR` | Local gallery root | Ops only |
| `BRAND_DATA_DIR` | Brand JSON root | Ops only |
| `RANKIFY_GENERATION_AUDIT` | Audit text files | May populate `generation_audit_path` |
| `LOG_LEVEL` | Logging | Ops only |
| `AWS_*` / `S3_*` | S3 credentials & prefixes | Ops only |

See `backend/.env.example` for the full template.

### 16.7 Running the server

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8750
```

Ensure `.env` (or environment) sets at least `API_KEY`, plus provider keys for the features you use.

---

## 17. Endpoint quick index

| Method | Path | Auth | Summary |
|--------|------|------|---------|
| `GET` | `/health` | Public | Health / infra status *(ops; not used by shipped UI)* |
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
| `POST` | `/api/brands/{brand_id}/text/captions` | API key | Alias of social-copy *(not used by shipped UI)* |
| `POST` | `/api/brands/{brand_id}/text/hashtags` | API key | Alias of social-copy *(not used by shipped UI)* |
| `GET` | `/api/models` | API key | Image model catalog |
| `GET` | `/api/image-sizes` | API key | Sizes + aspect ratios |
| `POST` | `/api/generate` | API key | Generate (JSON) |
| `POST` | `/api/generate-with-logo` | API key | Generate (multipart + logo) *(not used by shipped UI)* |
| `POST` | `/api/generate-with-reference` | API key | Generate + reference image |
| `GET` | `/api/brands/{brand_id}/gallery` | API key | List gallery |
| `POST` | `/api/brands/{brand_id}/gallery/edit` | API key | Edit gallery image |
| `GET` | `/api/brands/{brand_id}/gallery/{filename}` | API key | 307 → view URL *(not used by shipped UI)* |
| `GET` | `/api/brands/{brand_id}/gallery/raw/{filename}` | Signature | Stream image bytes |
| `DELETE` | `/api/brands/{brand_id}/gallery/{filename}` | API key | Delete image *(not used by shipped UI)* |
| `GET` | `/api/gallery` | — | **410** legacy |
| `GET` | `/api/gallery/{filename}` | — | **410** legacy |
| `GET` | `/api/gallery/raw/{filename}` | — | **410** legacy |
| `DELETE` | `/api/gallery/{filename}` | — | **410** legacy |

---

## 18. TypeScript-style contracts

Copy-paste types for a frontend TypeScript client (structural; not generated from OpenAPI):

```typescript
export type AspectRatio =
  | "1:1" | "2:3" | "3:2" | "3:4" | "4:3" | "4:5" | "5:4" | "9:16" | "16:9" | "21:9";

export type ImageSizeToken = "1K" | "2K" | "4K";

export interface StudioCampaignBrief {
  campaign_goal_id?: string;
  platforms?: string[];
  voice_tone_label?: string;
  creativity_tone_label: string;
  intent: string;
}

export interface GalleryImageItem {
  filename: string;
  url: string;
  storage_path: string;
  size_bytes: number;
  created_at: string;
  age_hours: number;
}

export interface BrandSlideGenerateResponse {
  images: GalleryImageItem[];
  model_used: string;
  per_image_price_usd: number;
  total_price_usd: number;
  message: string;
  generation_audit_path: string | null;
}

export interface BrandSlideGenerateRequest {
  brand_id: string;
  content?: string | null;
  studio_campaign?: StudioCampaignBrief | null;
  model_name?: string;
  num_images?: number; // 1..10
  aspect_ratio?: AspectRatio | string;
  image_size?: ImageSizeToken | string | null;
}

export interface GalleryImageEditRequest {
  source_filename: string;
  instruction: string; // 3..2000
  model_name?: string;
  aspect_ratio?: string;
  image_size?: string | null;
}

export interface BrandStudioSocialCopyRequest {
  studio_campaign: StudioCampaignBrief;
  image_filename?: string | null;
}

export interface BrandStudioSocialCopyResponse {
  caption: string;
  hashtags: string;
  model_used: string;
}

export interface BrandColors {
  primary?: string[];
  secondary?: string[];
  usage_rules?: string;
}

export interface BrandTypography {
  primary_font?: string;
  headline_font?: string;
  body_font?: string;
  notes?: string;
}

export interface BrandVoice {
  tone_keywords?: string[];
  writing_style?: string;
  target_audience?: string;
}

export interface BrandSocialDefaults {
  preferred_platforms?: string[];
  default_aspect_ratio?: string;
  default_image_size?: string;
}

export interface PlatformSpecificHints {
  hints?: Record<string, string>;
}

export interface BrandContentThemes {
  categories?: string[];
  recurring_themes?: string[];
}

export interface BrandTextPreferences {
  hashtag_style?: string;
  caption_style?: string;
  banned_phrases?: string[];
}

export interface BrandGenerationRules {
  governance_prompt_template: string; // min 20 chars
  design_guidelines?: string;
  layout_spacing_rules?: string;
  cta_button_rules?: string;
  visual_style_rules?: string;
  avoid_rules?: string;
  slide_intro_template?: string;
  slide_user_prompt_suffix?: string;
}

export interface BrandCreatePayload {
  brand_id?: string | null;
  display_name: string;
  tagline?: string;
  legal_suffix?: string;
  colors?: BrandColors;
  typography?: BrandTypography;
  voice?: BrandVoice;
  social_defaults?: BrandSocialDefaults;
  platform_hints?: PlatformSpecificHints;
  content_themes?: BrandContentThemes;
  text_preferences?: BrandTextPreferences;
  generation: BrandGenerationRules;
  logo_asset_filename?: string;
}

export interface BrandConfiguration extends Omit<BrandCreatePayload, "brand_id"> {
  brand_id: string;
  updated_at?: string | null;
}

export interface BrandSummary {
  brand_id: string;
  display_name: string;
  updated_at?: string | null;
}

export interface BrandListResponse {
  brands: BrandSummary[];
  total: number;
}

export interface GalleryListResponse {
  total: number;
  images: GalleryImageItem[];
}

export interface GalleryDeleteResponse {
  message: string;
  filename: string;
}

export interface ImageModelCatalogEntry {
  model_name: string;
  provider: "gemini" | "openai" | "imagen" | string;
  label: string;
  supports_image_size: boolean;
  supports_generate: boolean;
  supports_edit: boolean;
  pricing?: Record<string, number>;
  price_per_image_usd?: number;
}

export interface ModelsResponse {
  models: ImageModelCatalogEntry[];
}

export interface ImageSizesResponse {
  image_sizes: ImageSizeToken[];
  note: string;
  aspect_ratios: AspectRatio[];
}

export interface BrandAiDraftRequest {
  brand_materials: string; // 30..120000
  brand_id?: string | null;
  model_name?: string;
}

export interface BrandAiDraftResponse {
  draft: BrandCreatePayload;
  model_used: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | string;
  storage_backend: string;
  database: "enabled" | "disabled" | string;
  gallery_root: string;
  brand_config_root: string;
  timestamp: string;
  database_status?: string;
  s3_status?: string;
}

/** FastAPI error body */
export type ApiErrorBody = { detail: string | unknown[] | unknown };
```

---

*Generated from the FastAPI application in `backend/main.py` and related schema/pipeline modules. For live schema details, also open `/docs` on a running server.*
