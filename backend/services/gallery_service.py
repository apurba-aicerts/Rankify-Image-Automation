"""Gallery persistence: local disk or S3 + optional Postgres metadata."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from db.config import database_enabled
from db.repositories import GeneratedImageDbRepository
from gallery_local_store import (
    GalleryFileMetadata,
    commit_temp_file_to_gallery,
    gallery_file_exists,
    list_gallery_files_with_metadata,
    logical_gallery_key,
    remove_gallery_file,
    resolved_gallery_file_path,
    validate_gallery_filename,
)
from gallery_url_signing import GALLERY_IMAGE_URL_TTL_SECONDS, build_brand_gallery_image_view_url
from storage.config import S3_PRESIGN_TTL_SECONDS, s3_enabled
from storage import s3_client

logger = logging.getLogger(__name__)

_image_repo = GeneratedImageDbRepository()


def _image_ttl_hours() -> int:
    return int(os.getenv("IMAGE_TTL_HOURS", str(30 * 24)))


def _expires_at() -> Optional[datetime]:
    if not database_enabled():
        return None
    return datetime.now(timezone.utc) + timedelta(hours=_image_ttl_hours())


def _content_type_for_filename(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def commit_generated_image(
    *,
    brand_id: str,
    temp_source_path: str,
    filename: str,
    batch_id: str,
    slide_index: Optional[int],
    model_id: Optional[str],
) -> tuple[str, int, str]:
    """
    Store one generated slide. Returns (filename, size_bytes, object_key_or_logical_path).
    """
    validate_gallery_filename(filename)
    content_type = _content_type_for_filename(filename)

    if s3_enabled():
        object_key = s3_client.gallery_object_key(brand_id, filename)
        size_bytes = s3_client.upload_file(
            local_path=temp_source_path,
            object_key=object_key,
            content_type=content_type,
        )
        try:
            os.unlink(temp_source_path)
        except OSError:
            pass
    else:
        commit_temp_file_to_gallery(brand_id, temp_source_path, filename)
        path = resolved_gallery_file_path(brand_id, filename)
        size_bytes = path.stat().st_size
        object_key = logical_gallery_key(brand_id, filename)

    db_object_key = object_key if s3_enabled() else logical_gallery_key(brand_id, filename)
    if database_enabled():
        from db.session import session_scope

        with session_scope() as session:
            _image_repo.insert(
                session,
                brand_id=brand_id,
                batch_id=batch_id,
                slide_index=slide_index,
                filename=filename,
                object_key=db_object_key,
                model_id=model_id,
                content_type=content_type,
                size_bytes=size_bytes,
                expires_at=_expires_at(),
            )

    return filename, size_bytes, object_key


def gallery_image_exists(brand_id: str, filename: str) -> bool:
    validate_gallery_filename(filename)
    if database_enabled():
        row = _image_repo.get_by_filename(brand_id, filename)
        if row is not None:
            if s3_enabled():
                return s3_client.object_exists(row.object_key)
            return gallery_file_exists(brand_id, filename)
        return False
    return gallery_file_exists(brand_id, filename)


def list_gallery_metadata(brand_id: str) -> list[GalleryFileMetadata]:
    if database_enabled():
        return _image_repo.list_for_brand(brand_id)
    return list_gallery_files_with_metadata(brand_id)


def gallery_stats_for_brand(brand_id: str) -> dict[str, int]:
    """Counts only — does not build image URLs."""
    try:
        rows = list_gallery_metadata(brand_id)
    except OSError:
        logger.warning("Gallery stats failed brand_id=%s", brand_id, exc_info=True)
        return {"total": 0, "last_7_days": 0}
    now = datetime.now(timezone.utc)
    last_7_days = 0
    for meta in rows:
        lm = meta.last_modified_utc
        if lm.tzinfo is None:
            lm = lm.replace(tzinfo=timezone.utc)
        if (now - lm).total_seconds() / 3600 <= 168:
            last_7_days += 1
    return {"total": len(rows), "last_7_days": last_7_days}


def delete_gallery_image(brand_id: str, filename: str) -> None:
    validate_gallery_filename(filename)
    object_key: Optional[str] = None
    if database_enabled():
        object_key = _image_repo.delete_by_filename(brand_id, filename)

    if s3_enabled():
        key = object_key or s3_client.gallery_object_key(brand_id, filename)
        if s3_client.object_exists(key):
            s3_client.delete_object(key)
    else:
        if gallery_file_exists(brand_id, filename):
            remove_gallery_file(brand_id, filename)


def resolve_gallery_local_path(brand_id: str, filename: str) -> Path:
    """Return a local path for reading (downloads from S3 to a temp cache when needed)."""
    validate_gallery_filename(filename)
    if s3_enabled():
        if database_enabled():
            row = _image_repo.get_by_filename(brand_id, filename)
            if row is None:
                raise FileNotFoundError(filename)
            object_key = row.object_key
        else:
            object_key = s3_client.gallery_object_key(brand_id, filename)
        cache_dir = Path(tempfile.gettempdir()) / "rankify_gallery_cache" / brand_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        dest = cache_dir / filename
        if not dest.is_file():
            s3_client.download_to_path(object_key, str(dest))
        return dest
    return resolved_gallery_file_path(brand_id, filename)


def build_gallery_view_url(
    *,
    brand_id: str,
    filename: str,
    public_origin: str,
    signing_secret: str,
) -> str:
    validate_gallery_filename(filename)
    if s3_enabled():
        if database_enabled():
            row = _image_repo.get_by_filename(brand_id, filename)
            if row is None:
                raise FileNotFoundError(filename)
            object_key = row.object_key
        else:
            object_key = s3_client.gallery_object_key(brand_id, filename)
        return s3_client.presigned_get_url(object_key, ttl_seconds=S3_PRESIGN_TTL_SECONDS)

    return build_brand_gallery_image_view_url(
        public_api_origin=public_origin,
        signing_secret=signing_secret,
        brand_id=brand_id,
        filename=filename,
        ttl_seconds=GALLERY_IMAGE_URL_TTL_SECONDS,
    )


def purge_all_galleries_older_than_hours(max_age_hours: int) -> int:
    deleted = 0
    if database_enabled():
        keys = _image_repo.purge_expired(max_age_hours)
        for key in keys:
            try:
                if s3_enabled():
                    s3_client.delete_object(key)
                else:
                    parts = key.split("/")
                    if len(parts) >= 3 and parts[0] == "generated-images":
                        remove_gallery_file(parts[1], "/".join(parts[2:]))
            except Exception as exc:
                logger.warning("Purge blob delete failed key=%s: %s", key, exc)
            deleted += 1
        return deleted

    from gallery_local_store import purge_all_brand_galleries_older_than_hours

    return purge_all_brand_galleries_older_than_hours(max_age_hours)
