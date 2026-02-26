# AI CERTs® Image Generator — Backend API

FastAPI backend that generates branded carousel images for AI CERTs® social media posts using Google Gemini models. **Images are stored on AWS S3.**

---

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
GOOGLE_API_KEY="your-google-gemini-api-key"
API_KEY="your-secret-api-key-for-header-auth"
IMAGE_TTL_HOURS=24
AWS_ACCESS_KEY_ID="your-aws-access-key-id"
AWS_SECRET_ACCESS_KEY="your-aws-secret-access-key"
AWS_S3_BUCKET_NAME="aicerts-image-generator"
AWS_REGION="us-east-1"
```

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Google Gemini API key (required for image generation) |
| `API_KEY` | Secret key that frontend must send in the `x-api-key` header |
| `IMAGE_TTL_HOURS` | Auto-delete images older than this (default: `24` hours) |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key ID |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret access key |
| `AWS_S3_BUCKET_NAME` | S3 bucket name for storing generated images |
| `AWS_REGION` | AWS region where the S3 bucket is hosted (default: `us-east-1`) |

---

#### IAM Permissions Required

The IAM user/role whose credentials you use needs the following S3 permissions on the bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::aicerts-image-generator",
        "arn:aws:s3:::aicerts-image-generator/*"
      ]
    }
  ]
}
```

You can attach this as an **inline policy** or create a managed policy and attach it to the IAM user/role.

---

### 3. Run with Docker (Recommended)

```bash
docker build -t aicerts-image-api .
docker run --env-file .env -p 9600:9600 aicerts-image-api
```

The API will be available at **`http://localhost:9600`**

---

### 4. Run Locally (Without Docker)

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 9600
```

---

## Authentication

**Every API request** (except `/health`) must include this header:

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

No authentication required. Returns server status and S3 bucket info.

**Response:**
```json
{
  "status": "ok",
  "storage": "s3",
  "s3_bucket": "aicerts-image-generator",
  "timestamp": "2026-02-20T16:02:17.000000+00:00"
}
```

---

### List Available Models

```
GET /api/models
```

Returns all Gemini models the frontend can use in the generate endpoint, along with pricing info.

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
      "supports_image_size": true,
      "pricing": { "1K": 0.134, "2K": 0.134, "4K": 0.24 }
    },
    {
      "model_name": "gemini-2.5-flash-image",
      "supports_image_size": false,
      "price_per_image_usd": 0.039
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
  "note": "Image size selection applies only to gemini-3-pro-image-preview. For gemini-2.5-flash-image the size is managed automatically.",
  "aspect_ratios": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
}
```

---

### Generate Images (JSON)

```
POST /api/generate
```

Generate carousel images using the default logo. Send a JSON body. Images are uploaded to S3 and presigned URLs are returned.

**Headers:**
```
Content-Type: application/json
x-api-key: <your-api-key>
```

**Request Body:**
```json
{
  "content": "TITLE:\nFuture-Proof Your Career with AI CERTs®\n\nSUBTITLE:\nBecome Certified. Become AI-Ready.\n\nBODY:\nAI is transforming every industry.\nUpskill with globally recognized AI certifications.\n\nCTA BUTTON:\nEnroll Now",
  "model_name": "gemini-3-pro-image-preview",
  "num_images": 2,
  "aspect_ratio": "1:1",
  "image_size": "2K"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | `string` | **required** | Post content in TITLE / SUBTITLE / BODY / CTA format |
| `model_name` | `string` | `gemini-3-pro-image-preview` | Model: `gemini-3-pro-image-preview` or `gemini-2.5-flash-image` |
| `num_images` | `integer` | `1` | Number of images to generate (1–10) |
| `aspect_ratio` | `string` | `1:1` | Options: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9` |
| `image_size` | `string` | `2K` | Resolution (only for `gemini-3-pro-image-preview`): `1K`, `2K`, `4K` |

**Response:**
```json
{
  "images": [
    {
      "filename": "aicerts_a1b2c3d4_1.png",
      "url": "https://aicerts-image-generator.s3.amazonaws.com/generated-images/aicerts_a1b2c3d4_1.png?X-Amz-Algorithm=...",
      "s3_key": "generated-images/aicerts_a1b2c3d4_1.png",
      "size_bytes": 245120,
      "created_at": "2026-02-20T16:05:00+00:00",
      "age_hours": 0.01
    }
  ],
  "model_used": "gemini-3-pro-image-preview",
  "per_image_price_usd": 0.134,
  "total_price_usd": 0.268,
  "message": "Successfully generated 2 image(s) and uploaded to S3."
}
```

> **Note:** The `url` field is a **presigned S3 URL** that expires after 1 hour. Use it directly to display or download the image.

---

### Generate Images with Custom Logo (Multipart Form)

```
POST /api/generate-with-logo
```

Same as above but accepts a **custom logo file** via multipart form upload.

**Headers:**
```
Content-Type: multipart/form-data
x-api-key: <your-api-key>
```

**Form Fields:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | `string` | **required** | Post content |
| `model_name` | `string` | `gemini-3-pro-image-preview` | Gemini model |
| `num_images` | `integer` | `1` | Number of images (1–10) |
| `aspect_ratio` | `string` | `1:1` | Aspect ratio |
| `image_size` | `string` | `2K` | Resolution |
| `logo` | `file` | default logo | Custom logo image (png/jpg) |

**cURL Example:**
```bash
curl -X POST http://localhost:9600/api/generate-with-logo \
  -H "x-api-key: your-api-key" \
  -F "content=TITLE:\nMy Post\n\nSUBTITLE:\nSubtitle\n\nBODY:\nBody text\n\nCTA BUTTON:\nLearn More" \
  -F "num_images=1" \
  -F "logo=@/path/to/logo.png"
```

**Response:** Same format as `/api/generate`.

---

### Gallery — List All Images

```
GET /api/gallery
```

Returns metadata for every image currently stored in S3 (sorted newest first).

**Headers:**
```
x-api-key: <your-api-key>
```

**Response:**
```json
{
  "total": 3,
  "images": [
    {
      "filename": "aicerts_a1b2c3d4_1.png",
      "url": "https://aicerts-image-generator.s3.amazonaws.com/generated-images/aicerts_a1b2c3d4_1.png?X-Amz-Algorithm=...",
      "s3_key": "generated-images/aicerts_a1b2c3d4_1.png",
      "size_bytes": 245120,
      "created_at": "2026-02-20T16:05:00+00:00",
      "age_hours": 2.5
    }
  ]
}
```

---

### Gallery — Download / View Single Image

```
GET /api/gallery/{filename}
```

Redirects (HTTP 307) to a **presigned S3 URL** for the image. The presigned URL expires after 1 hour.

**Headers:**
```
x-api-key: <your-api-key>
```

**Example:**
```
GET /api/gallery/aicerts_a1b2c3d4_1.png
```

Returns: `307 Temporary Redirect` → presigned S3 URL.

---

### Gallery — Delete an Image

```
DELETE /api/gallery/{filename}
```

Deletes the image from S3.

**Headers:**
```
x-api-key: <your-api-key>
```

**Response:**
```json
{
  "message": "Image deleted successfully from S3.",
  "filename": "aicerts_a1b2c3d4_1.png"
}
```

---

## Image Lifecycle

- Images are **generated locally** in a temp directory, **uploaded to S3**, and the local copy is **immediately deleted**.
- All images are stored in S3 under the `generated-images/` prefix.
- A **background job runs every hour** and automatically deletes S3 objects older than `IMAGE_TTL_HOURS` (default: 24 hours).
- Images can also be manually deleted via the `DELETE /api/gallery/{filename}` endpoint.
- Image URLs returned by the API are **presigned S3 URLs** valid for 1 hour.

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
| `404` | Image not found in S3 |
| `422` | Missing required fields |
| `500` | Server misconfiguration (missing env vars) |
| `502` | Upstream Gemini API failure or S3 error |

---

## Project Structure

```
├── api.py              # FastAPI backend (main entry point)
├── generator.py        # AICertsImageGenerator — calls Gemini API
├── prompts.py          # Brand prompt & content prompt builder
├── helpers/
│   ├── __init__.py
│   └── s3_helper.py    # AWS S3 helper functions (upload, download, delete, list, cleanup)
├── Dockerfile          # Docker config — runs FastAPI on port 9600
├── requirements.txt    # Python dependencies (includes boto3)
├── .env.example        # Environment variable template
├── assets/
│   └── default_logo.jpg
└── app.py              # Streamlit UI (legacy, not used in Docker)
```
