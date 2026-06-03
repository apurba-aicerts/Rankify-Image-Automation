# Production: PostgreSQL + S3

## Modes

| `DATABASE_URL` | `STORAGE_BACKEND` | Behavior |
|----------------|-------------------|----------|
| unset | `local` (default) | Original filesystem brands + local gallery |
| set | `local` | Brands + gallery metadata in Postgres; image files on disk |
| set | `s3` | Brands in Postgres; images and logos in S3; presigned `view_url` |

`STORAGE_BACKEND=s3` **requires** `DATABASE_URL`.

## Local Postgres

```bash
cd backend
docker compose up -d
pip install -r requirements.txt
alembic upgrade head
```

## `.env` (production example)

```env
DATABASE_URL=postgresql+psycopg://rankify:rankify@localhost:5432/rankify
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=rankify-image-generator
AWS_REGION=us-east-1
```

## Tables

- `brands` — full `BrandConfiguration` as JSONB
- `brand_assets` — logo (and future assets) S3 keys
- `generated_images` — gallery metadata + S3 object keys
- `social_copy` — caption/hashtag history (saved on social-copy API calls)

## Run API

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 9600
```

`GET /health` reports database and S3 connectivity when configured.

## S3 key layout

```
gallery/{brand_id}/{filename}
brands/{brand_id}/assets/{filename}
```

Bucket must be **private**; clients receive **presigned GET** URLs in `view_url`.

## Gallery history (30 days)

Set `IMAGE_TTL_HOURS=720` (30 × 24). Each generated image gets `expires_at` in Postgres; a background task every ~15 minutes removes expired rows and deletes the S3 object. Older than 30 days is purged automatically.
