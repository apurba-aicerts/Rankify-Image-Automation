"""
Per-brand gallery directories under ``<root>/<brand_id>/``.

``GALLERY_STORAGE_DIR`` defaults to ``generated-images``. Each brand has an isolated subdirectory.
Logical keys returned to clients look like ``generated-images/<brand_id>/<filename>``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from brands.schemas import validate_brand_id

load_dotenv()

logger = logging.getLogger(__name__)

_raw_dir = os.getenv("LOCAL_IMAGE_STORAGE_DIR", "").strip()
GALLERY_STORAGE_DIR = Path(_raw_dir if _raw_dir else "generated-images").resolve()
GALLERY_KEY_PREFIX = "generated-images/"

_FILENAME_SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


@dataclass(frozen=True)
class GalleryFileMetadata:
    """One image file on disk for a single brand."""

    brand_id: str
    filename: str
    size_bytes: int
    last_modified_utc: datetime


def logical_gallery_key(brand_id: str, filename: str) -> str:
    """API-facing storage key (no path traversal)."""
    return f"{GALLERY_KEY_PREFIX}{validate_brand_id(brand_id)}/{validate_gallery_filename(filename)}"


def gallery_dir_for_brand(brand_id: str) -> Path:
    """Directory where a brand's raster files are stored."""
    return GALLERY_STORAGE_DIR / validate_brand_id(brand_id)


def ensure_gallery_directory_exists(brand_id: str) -> None:
    gallery_dir_for_brand(brand_id).mkdir(parents=True, exist_ok=True)


def validate_gallery_filename(filename: str) -> str:
    if not filename or not _FILENAME_SAFE.match(filename):
        raise ValueError("Invalid filename.")
    return filename


def resolved_gallery_file_path(brand_id: str, filename: str) -> Path:
    return gallery_dir_for_brand(brand_id) / validate_gallery_filename(filename)


def commit_temp_file_to_gallery(brand_id: str, temp_source_path: str, destination_filename: str) -> Path:
    ensure_gallery_directory_exists(brand_id)
    dest = resolved_gallery_file_path(brand_id, destination_filename)
    os.replace(temp_source_path, dest)
    logger.info(
        "Gallery commit brand_id=%s file=%s bytes=%s",
        brand_id,
        destination_filename,
        dest.stat().st_size if dest.is_file() else 0,
    )
    return dest


def gallery_file_exists(brand_id: str, filename: str) -> bool:
    return resolved_gallery_file_path(brand_id, filename).is_file()


def remove_gallery_file(brand_id: str, filename: str) -> None:
    path = resolved_gallery_file_path(brand_id, filename)
    if path.is_file():
        path.unlink()
        logger.info("Gallery file removed brand_id=%s file=%s", brand_id, filename)


def list_gallery_files_with_metadata(brand_id: str) -> list[GalleryFileMetadata]:
    ensure_gallery_directory_exists(brand_id)
    root = gallery_dir_for_brand(brand_id)
    out: list[GalleryFileMetadata] = []
    if not root.is_dir():
        return out
    for path in root.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        st = path.stat()
        lm = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        out.append(
            GalleryFileMetadata(
                brand_id=validate_brand_id(brand_id),
                filename=path.name,
                size_bytes=st.st_size,
                last_modified_utc=lm,
            )
        )
    return out


def purge_gallery_files_older_than_hours_for_brand(brand_id: str, max_age_hours: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    deleted = 0
    for meta in list_gallery_files_with_metadata(brand_id):
        if meta.last_modified_utc < cutoff:
            try:
                remove_gallery_file(brand_id, meta.filename)
                deleted += 1
            except OSError as exc:
                logger.warning("Purge unlink failed brand_id=%s file=%s: %s", brand_id, meta.filename, exc)
    return deleted


def purge_all_brand_galleries_older_than_hours(max_age_hours: int) -> int:
    """Walk every brand subdirectory under the gallery root and apply TTL purge."""
    if not GALLERY_STORAGE_DIR.is_dir():
        return 0
    total = 0
    for entry in GALLERY_STORAGE_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            bid = validate_brand_id(entry.name)
        except ValueError:
            continue
        total += purge_gallery_files_older_than_hours_for_brand(bid, max_age_hours)
    if total:
        logger.info("Gallery TTL purge total files removed=%s (max_age_h=%s)", total, max_age_hours)
    return total
