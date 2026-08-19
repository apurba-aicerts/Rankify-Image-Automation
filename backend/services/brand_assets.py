"""Brand logo and asset storage (local filesystem or S3 + DB)."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from db.config import database_enabled
from db.repositories import BrandAssetDbRepository
from gallery_local_store import validate_gallery_filename
from storage.config import s3_enabled
from storage import s3_client

logger = logging.getLogger(__name__)

_asset_repo = BrandAssetDbRepository()
_LOGO_CACHE_ROOT = Path(tempfile.gettempdir()) / "rankify_logo_cache"


def local_logo_cache_path(brand_id: str) -> Path:
    return _LOGO_CACHE_ROOT / brand_id / "logo.png"


def save_logo_upload(*, brand_id: str, temp_path: str, filename: str, content_type: str) -> str:
    """Persist uploaded logo; return a display path or object key."""
    safe_name = validate_gallery_filename(Path(filename).name if "." in filename else f"{filename}.png")

    if s3_enabled():
        object_key = s3_client.brand_asset_object_key(brand_id, safe_name)
        size = s3_client.upload_file(local_path=temp_path, object_key=object_key, content_type=content_type)
        if database_enabled():
            _asset_repo.upsert_logo(
                brand_id=brand_id,
                filename=safe_name,
                object_key=object_key,
                content_type=content_type,
                size_bytes=size,
            )
        _refresh_logo_cache(brand_id, temp_path)
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return object_key

    from brands.repository import BrandRepository

    repo = BrandRepository()
    repo.ensure_layout(brand_id)
    dest = repo.logo_path(brand_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(temp_path, dest)
    logger.info("Logo saved locally brand_id=%s path=%s", brand_id, dest)
    return str(dest)


def _refresh_logo_cache(brand_id: str, source_path: str) -> None:
    dest = local_logo_cache_path(brand_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest)


def brand_has_logo(brand_id: str, configured_filename: str) -> bool:
    """True when the brand has a persisted logo asset (local disk or S3 + DB)."""
    return resolve_logo_local_path(brand_id, configured_filename) is not None


def build_logo_view_url(
    *,
    brand_id: str,
    configured_filename: str,
    public_origin: str,
    signing_secret: str,
) -> str | None:
    """
    Temporary URL to view the brand logo, or None if no file exists.

    S3: presigned GET. Local: HMAC URL to /api/brands/{id}/assets/logo/raw.
    """
    from brands.repository import BRAND_DATA_DIR
    from gallery_url_signing import GALLERY_IMAGE_URL_TTL_SECONDS, build_brand_logo_view_url

    if s3_enabled():
        if database_enabled():
            row = _asset_repo.get_primary_logo(brand_id)
            if row is None:
                return None
            object_key = row.object_key
        else:
            object_key = s3_client.brand_asset_object_key(brand_id, configured_filename)
            if not s3_client.object_exists(object_key):
                return None
        return s3_client.presigned_get_url(object_key)

    safe_name = Path(configured_filename or "logo.png").name
    path = BRAND_DATA_DIR / brand_id / "assets" / safe_name
    if not path.is_file():
        return None
    if not signing_secret:
        return None
    return build_brand_logo_view_url(
        public_api_origin=public_origin,
        signing_secret=signing_secret,
        brand_id=brand_id,
        ttl_seconds=GALLERY_IMAGE_URL_TTL_SECONDS,
    )


def resolve_logo_local_path(brand_id: str, configured_filename: str) -> Path | None:
    """Local path for PIL/open; None if no logo configured."""
    from brands.repository import BrandRepository

    if s3_enabled():
        if database_enabled():
            row = _asset_repo.get_primary_logo(brand_id)
            if row is None:
                return None
            object_key = row.object_key
        else:
            object_key = s3_client.brand_asset_object_key(brand_id, configured_filename)
            if not s3_client.object_exists(object_key):
                return None
        cache = local_logo_cache_path(brand_id)
        if not cache.is_file():
            s3_client.download_to_path(object_key, str(cache))
        return cache

    repo = BrandRepository()
    path = repo.logo_path(brand_id)
    return path if path.is_file() else None
