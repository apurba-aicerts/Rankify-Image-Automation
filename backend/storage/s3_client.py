"""AWS S3 operations for gallery images and brand assets."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import BaseClient

from storage.config import AWS_REGION, AWS_S3_BUCKET_NAME, S3_PRESIGN_TTL_SECONDS, require_s3_config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    require_s3_config()
    return boto3.client("s3", region_name=AWS_REGION)


def gallery_object_key(brand_id: str, filename: str) -> str:
    from storage.config import S3_GALLERY_PREFIX

    prefix = S3_GALLERY_PREFIX.rstrip("/") + "/"
    return f"{prefix}{brand_id}/{filename}"


def brand_asset_object_key(brand_id: str, filename: str) -> str:
    from storage.config import S3_BRAND_ASSETS_PREFIX

    prefix = S3_BRAND_ASSETS_PREFIX.rstrip("/") + "/"
    return f"{prefix}{brand_id}/assets/{filename}"


def upload_file(*, local_path: str, object_key: str, content_type: str) -> int:
    path = Path(local_path)
    size = path.stat().st_size
    get_s3_client().upload_file(
        str(path),
        AWS_S3_BUCKET_NAME,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )
    logger.info("S3 upload bucket=%s key=%s bytes=%s", AWS_S3_BUCKET_NAME, object_key, size)
    return size


def delete_object(object_key: str) -> None:
    get_s3_client().delete_object(Bucket=AWS_S3_BUCKET_NAME, Key=object_key)
    logger.info("S3 delete key=%s", object_key)


def object_exists(object_key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        get_s3_client().head_object(Bucket=AWS_S3_BUCKET_NAME, Key=object_key)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def presigned_get_url(object_key: str, ttl_seconds: Optional[int] = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else S3_PRESIGN_TTL_SECONDS
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": object_key},
        ExpiresIn=ttl,
    )


def download_to_path(object_key: str, dest_path: str) -> None:
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(AWS_S3_BUCKET_NAME, object_key, dest_path)
    logger.debug("S3 download key=%s -> %s", object_key, dest_path)
