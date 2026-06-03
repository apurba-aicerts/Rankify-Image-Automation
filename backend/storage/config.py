"""Object storage configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

STORAGE_BACKEND = (os.getenv("STORAGE_BACKEND") or "local").strip().lower()
AWS_REGION = (os.getenv("AWS_REGION") or "us-east-1").strip()
AWS_S3_BUCKET_NAME = (os.getenv("AWS_S3_BUCKET_NAME") or "").strip()
S3_GALLERY_PREFIX = (os.getenv("S3_GALLERY_PREFIX") or "gallery/").strip()
S3_BRAND_ASSETS_PREFIX = (os.getenv("S3_BRAND_ASSETS_PREFIX") or "brands/").strip()
S3_PRESIGN_TTL_SECONDS = int(os.getenv("S3_PRESIGN_TTL_SECONDS", "3600"))


def s3_enabled() -> bool:
    return STORAGE_BACKEND == "s3"


def require_s3_config() -> None:
    if not AWS_S3_BUCKET_NAME:
        raise RuntimeError("AWS_S3_BUCKET_NAME is required when STORAGE_BACKEND=s3")
