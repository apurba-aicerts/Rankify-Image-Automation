"""Initial brands, assets, generated_images, social_copy tables.

Revision ID: 001
Revises:
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("brand_id", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("brand_id"),
    )
    op.create_table(
        "brand_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.brand_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("brand_id", "asset_type", "filename", name="uq_brand_asset_file"),
    )
    op.create_index("ix_brand_assets_brand_id", "brand_assets", ["brand_id"])

    op.create_table(
        "generated_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", sa.String(length=64), nullable=False),
        sa.Column("batch_id", sa.String(length=16), nullable=False),
        sa.Column("slide_index", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.brand_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("brand_id", "filename", name="uq_brand_gallery_filename"),
    )
    op.create_index("ix_generated_images_brand_id", "generated_images", ["brand_id"])
    op.create_index("ix_generated_images_batch_id", "generated_images", ["batch_id"])
    op.create_index("ix_generated_images_created_at", "generated_images", ["created_at"])
    op.create_index("ix_generated_images_expires_at", "generated_images", ["expires_at"])

    op.create_table(
        "social_copy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", sa.String(length=64), nullable=False),
        sa.Column("generated_image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.brand_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_image_id"], ["generated_images.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_copy_brand_id", "social_copy", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_social_copy_brand_id", table_name="social_copy")
    op.drop_table("social_copy")
    op.drop_index("ix_generated_images_expires_at", table_name="generated_images")
    op.drop_index("ix_generated_images_created_at", table_name="generated_images")
    op.drop_index("ix_generated_images_batch_id", table_name="generated_images")
    op.drop_index("ix_generated_images_brand_id", table_name="generated_images")
    op.drop_table("generated_images")
    op.drop_index("ix_brand_assets_brand_id", table_name="brand_assets")
    op.drop_table("brand_assets")
    op.drop_table("brands")
