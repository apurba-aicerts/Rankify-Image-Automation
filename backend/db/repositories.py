"""Data access for brands, assets, gallery images, and social copy."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from brands.schemas import BrandConfiguration, BrandSummary, validate_brand_id
from db.models import BrandAssetRow, BrandRow, GeneratedImageRow, SocialCopyRow
from db.session import session_scope
from gallery_local_store import GalleryFileMetadata


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BrandDbRepository:
    """Postgres-backed brand configuration (same surface as filesystem BrandRepository)."""

    def exists(self, brand_id: str) -> bool:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            return session.get(BrandRow, bid) is not None

    def load(self, brand_id: str) -> BrandConfiguration:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            row = session.get(BrandRow, bid)
            if row is None:
                raise FileNotFoundError(f"Unknown brand_id: {bid}")
            return BrandConfiguration.model_validate(row.config)

    def save(self, config: BrandConfiguration) -> None:
        bid = validate_brand_id(config.brand_id)
        now = _utc_now()
        payload = json.loads(config.model_copy(update={"updated_at": now}).model_dump_json())
        with session_scope() as session:
            row = session.get(BrandRow, bid)
            if row is None:
                session.add(BrandRow(brand_id=bid, config=payload, created_at=now, updated_at=now))
            else:
                row.config = payload
                row.updated_at = now

    def delete(self, brand_id: str) -> None:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            row = session.get(BrandRow, bid)
            if row is not None:
                session.delete(row)

    def list_summaries(self) -> list[BrandSummary]:
        with session_scope() as session:
            rows = session.scalars(select(BrandRow).order_by(BrandRow.brand_id)).all()
            out: list[BrandSummary] = []
            for row in rows:
                cfg = BrandConfiguration.model_validate(row.config)
                out.append(
                    BrandSummary(
                        brand_id=cfg.brand_id,
                        display_name=cfg.display_name,
                        updated_at=cfg.updated_at or row.updated_at,
                    )
                )
            return out

    def list_brand_ids(self) -> list[str]:
        return [s.brand_id for s in self.list_summaries()]

    def ensure_layout(self, brand_id: str) -> None:
        bid = validate_brand_id(brand_id)
        if not self.exists(bid):
            raise FileNotFoundError(f"Unknown brand_id: {bid}")

    def logo_path(self, brand_id: str):
        """Filesystem path for logo — only valid when a local asset cache exists."""
        from pathlib import Path

        from services.brand_assets import local_logo_cache_path

        return local_logo_cache_path(brand_id)


class GeneratedImageDbRepository:
    def insert(
        self,
        session: Session,
        *,
        brand_id: str,
        batch_id: str,
        slide_index: Optional[int],
        filename: str,
        object_key: str,
        model_id: Optional[str],
        content_type: str,
        size_bytes: int,
        expires_at: Optional[datetime],
    ) -> GeneratedImageRow:
        row = GeneratedImageRow(
            id=uuid.uuid4(),
            brand_id=validate_brand_id(brand_id),
            batch_id=batch_id,
            slide_index=slide_index,
            filename=filename,
            object_key=object_key,
            model_id=model_id,
            content_type=content_type,
            size_bytes=size_bytes,
            created_at=_utc_now(),
            expires_at=expires_at,
        )
        session.add(row)
        session.flush()
        return row

    def get_by_filename(self, brand_id: str, filename: str) -> Optional[GeneratedImageRow]:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            return session.scalar(
                select(GeneratedImageRow).where(
                    GeneratedImageRow.brand_id == bid,
                    GeneratedImageRow.filename == filename,
                )
            )

    def list_for_brand(self, brand_id: str) -> list[GalleryFileMetadata]:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            rows = session.scalars(
                select(GeneratedImageRow)
                .where(GeneratedImageRow.brand_id == bid)
                .order_by(GeneratedImageRow.created_at.desc())
            ).all()
            return [
                GalleryFileMetadata(
                    brand_id=bid,
                    filename=r.filename,
                    size_bytes=r.size_bytes,
                    last_modified_utc=r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc),
                )
                for r in rows
            ]

    def delete_by_filename(self, brand_id: str, filename: str) -> Optional[str]:
        """Delete row; return object_key for blob cleanup."""
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            row = session.scalar(
                select(GeneratedImageRow).where(
                    GeneratedImageRow.brand_id == bid,
                    GeneratedImageRow.filename == filename,
                )
            )
            if row is None:
                return None
            key = row.object_key
            session.delete(row)
            return key

    def purge_expired(self, max_age_hours: int) -> list[str]:
        cutoff = _utc_now() - timedelta(hours=max_age_hours)
        keys: list[str] = []
        with session_scope() as session:
            rows = session.scalars(
                select(GeneratedImageRow).where(
                    (GeneratedImageRow.expires_at.is_not(None) & (GeneratedImageRow.expires_at < _utc_now()))
                    | (GeneratedImageRow.created_at < cutoff)
                )
            ).all()
            for row in rows:
                keys.append(row.object_key)
                session.delete(row)
        return keys

    def all_brand_ids_with_images(self) -> list[str]:
        with session_scope() as session:
            rows = session.scalars(select(GeneratedImageRow.brand_id).distinct()).all()
            return list(rows)


class BrandAssetDbRepository:
    def upsert_logo(
        self,
        *,
        brand_id: str,
        filename: str,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> None:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            session.execute(
                delete(BrandAssetRow).where(
                    BrandAssetRow.brand_id == bid,
                    BrandAssetRow.asset_type == "logo",
                )
            )
            session.add(
                BrandAssetRow(
                    id=uuid.uuid4(),
                    brand_id=bid,
                    asset_type="logo",
                    filename=filename,
                    object_key=object_key,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    is_primary=True,
                    created_at=_utc_now(),
                )
            )

    def get_primary_logo(self, brand_id: str) -> Optional[BrandAssetRow]:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            return session.scalar(
                select(BrandAssetRow).where(
                    BrandAssetRow.brand_id == bid,
                    BrandAssetRow.asset_type == "logo",
                    BrandAssetRow.is_primary.is_(True),
                )
            )


class SocialCopyDbRepository:
    def insert(
        self,
        *,
        brand_id: str,
        caption: str,
        hashtags: str,
        model_used: str,
        generated_image_id: Optional[uuid.UUID] = None,
    ) -> None:
        bid = validate_brand_id(brand_id)
        with session_scope() as session:
            session.add(
                SocialCopyRow(
                    id=uuid.uuid4(),
                    brand_id=bid,
                    generated_image_id=generated_image_id,
                    caption=caption,
                    hashtags=hashtags,
                    model_used=model_used,
                    created_at=_utc_now(),
                )
            )
