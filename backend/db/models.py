"""SQLAlchemy models for production persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BrandRow(Base):
    __tablename__ = "brands"

    brand_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assets: Mapped[list["BrandAssetRow"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    images: Mapped[list["GeneratedImageRow"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    social_copies: Mapped[list["SocialCopyRow"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )


class BrandAssetRow(Base):
    __tablename__ = "brand_assets"
    __table_args__ = (UniqueConstraint("brand_id", "asset_type", "filename", name="uq_brand_asset_file"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[str] = mapped_column(String(64), ForeignKey("brands.brand_id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="logo")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="image/png")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped["BrandRow"] = relationship(back_populates="assets")


class GeneratedImageRow(Base):
    __tablename__ = "generated_images"
    __table_args__ = (UniqueConstraint("brand_id", "filename", name="uq_brand_gallery_filename"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[str] = mapped_column(String(64), ForeignKey("brands.brand_id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    slide_index: Mapped[int | None] = mapped_column(nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    brand: Mapped["BrandRow"] = relationship(back_populates="images")
    social_copies: Mapped[list["SocialCopyRow"]] = relationship(back_populates="generated_image")


class SocialCopyRow(Base):
    __tablename__ = "social_copy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[str] = mapped_column(String(64), ForeignKey("brands.brand_id", ondelete="CASCADE"), index=True)
    generated_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_images.id", ondelete="SET NULL"), nullable=True
    )
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped["BrandRow"] = relationship(back_populates="social_copies")
    generated_image: Mapped["GeneratedImageRow | None"] = relationship(back_populates="social_copies")
