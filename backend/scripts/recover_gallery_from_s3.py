"""
Recover Postgres gallery metadata from existing S3 objects.

Use when image files exist in S3 but generated_images / brands rows are missing
or point at the wrong local Postgres instance.

  cd backend
  python scripts/recover_gallery_from_s3.py
  python scripts/recover_gallery_from_s3.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from backend/ without installing as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from brands.schemas import BrandConfiguration, BrandGenerationRules
from db.config import database_enabled, database_url
from db.repositories import BrandAssetDbRepository, BrandDbRepository, GeneratedImageDbRepository
from db.session import session_scope
from gallery_local_store import validate_gallery_filename
from storage.config import AWS_S3_BUCKET_NAME, S3_BRAND_ASSETS_PREFIX, S3_GALLERY_PREFIX, require_s3_config, s3_enabled
from storage import s3_client

logger = logging.getLogger(__name__)

_SLIDE_RE = re.compile(r"^rankify_slide_([a-f0-9]+)_(\d+)\.", re.I)
_EDIT_RE = re.compile(r"^rankify_edit_([a-f0-9]+)\.", re.I)

_LOGO_DISPLAY = {
    "n_plus_logo.png": "N+",
    "ai_certs_logo.png": "AI CERTs",
    "sarder_logo.png": "Sarder",
}


def _parse_batch(filename: str) -> tuple[str, int | None]:
    m = _SLIDE_RE.match(filename)
    if m:
        return m.group(1), int(m.group(2))
    m = _EDIT_RE.match(filename)
    if m:
        return m.group(1), None
    stem = Path(filename).stem
    return stem[:16], None


def _content_type(key: str) -> str:
    lower = key.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def _display_name(brand_id: str, logo_filename: str | None) -> str:
    if logo_filename:
        mapped = _LOGO_DISPLAY.get(logo_filename.lower())
        if mapped:
            return mapped
        stem = Path(logo_filename).stem.replace("_", " ").replace("-", " ")
        return stem.title()
    return f"Recovered {brand_id[:8]}"


def _ttl_hours() -> int:
    return int(os.getenv("IMAGE_TTL_HOURS", str(30 * 24)))


def _list_gallery_objects() -> dict[str, list[dict]]:
    client = s3_client.get_s3_client()
    require_s3_config()
    bucket = AWS_S3_BUCKET_NAME
    prefix = S3_GALLERY_PREFIX.rstrip("/") + "/"
    by_brand: dict[str, list[dict]] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            rel = key[len(prefix) :]
            parts = rel.split("/", 1)
            if len(parts) != 2:
                continue
            brand_id, filename = parts[0], parts[1]
            if not filename or "/" in filename:
                continue
            try:
                validate_gallery_filename(filename)
            except ValueError:
                logger.warning("Skip invalid gallery filename: %s", key)
                continue
            by_brand.setdefault(brand_id, []).append(
                {
                    "key": key,
                    "filename": filename,
                    "size_bytes": int(obj.get("Size") or 0),
                    "last_modified": obj["LastModified"],
                }
            )
    return by_brand


def _find_logo(brand_id: str) -> tuple[str, str, int] | None:
    client = s3_client.get_s3_client()
    require_s3_config()
    bucket = AWS_S3_BUCKET_NAME
    prefix = f"{S3_BRAND_ASSETS_PREFIX.rstrip('/')}/{brand_id}/assets/"
    resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
    for obj in resp.get("Contents") or []:
        filename = obj["Key"].split("/")[-1]
        if filename:
            return filename, obj["Key"], int(obj.get("Size") or 0)
    return None


def recover(*, dry_run: bool) -> None:
    if not database_enabled():
        raise SystemExit("DATABASE_URL is not set.")
    if not s3_enabled():
        raise SystemExit("STORAGE_BACKEND must be s3 for S3 recovery.")

    print(f"Database: {database_url().split('@')[-1]}")
    gallery = _list_gallery_objects()
    total_objects = sum(len(v) for v in gallery.values())
    print(f"S3 gallery objects: {total_objects} across {len(gallery)} brand folder(s)")

    brand_repo = BrandDbRepository()
    asset_repo = BrandAssetDbRepository()
    image_repo = GeneratedImageDbRepository()

    brands_created = 0
    logos_linked = 0
    images_inserted = 0
    images_skipped = 0

    ttl = _ttl_hours()
    for brand_id, objects in sorted(gallery.items()):
        logo = _find_logo(brand_id)
        logo_filename = logo[0] if logo else None
        display_name = _display_name(brand_id, logo_filename)

        if not brand_repo.exists(brand_id):
            cfg = BrandConfiguration(
                brand_id=brand_id,
                display_name=display_name,
                generation=BrandGenerationRules(
                    governance_prompt_template=(
                        "Recovered brand placeholder. Replace with your full brand governance "
                        "prompt in Settings before generating new images."
                    )
                ),
                logo_asset_filename=logo_filename or "logo.png",
            )
            print(f"  + brand {brand_id} ({display_name})")
            if not dry_run:
                brand_repo.save(cfg)
            brands_created += 1
        elif logo_filename:
            try:
                existing = brand_repo.load(brand_id)
                if existing.display_name.startswith("Recovered ") or existing.display_name in {"test", "test 2"}:
                    display_name = _display_name(brand_id, logo_filename)
            except FileNotFoundError:
                pass

        if logo and not dry_run:
            filename, object_key, size_bytes = logo
            asset_repo.upsert_logo(
                brand_id=brand_id,
                filename=filename,
                object_key=object_key,
                content_type=_content_type(filename),
                size_bytes=size_bytes,
            )
            logos_linked += 1

        for obj in objects:
            filename = obj["filename"]
            existing = image_repo.get_by_filename(brand_id, filename)
            if existing is not None:
                images_skipped += 1
                continue
            batch_id, slide_index = _parse_batch(filename)
            created_at: datetime = obj["last_modified"]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            expires_at = created_at + timedelta(hours=ttl)
            print(f"  + image {brand_id}/{filename}")
            if not dry_run:
                with session_scope() as session:
                    row = image_repo.insert(
                        session,
                        brand_id=brand_id,
                        batch_id=batch_id,
                        slide_index=slide_index,
                        filename=filename,
                        object_key=obj["key"],
                        model_id=None,
                        content_type=_content_type(filename),
                        size_bytes=obj["size_bytes"],
                        expires_at=expires_at,
                    )
                    row.created_at = created_at
            images_inserted += 1

    print()
    print(f"Brands created: {brands_created}")
    print(f"Logos linked:   {logos_linked}")
    print(f"Images added:   {images_inserted}")
    print(f"Images skipped: {images_skipped} (already in DB)")
    if dry_run:
        print("Dry run only — no changes written.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Recover gallery DB rows from S3.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing.")
    args = parser.parse_args()
    recover(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
