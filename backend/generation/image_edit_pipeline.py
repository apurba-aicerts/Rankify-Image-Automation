"""AI refinement of an existing gallery image (instruction + source raster, not full slide regen)."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from PIL import Image

from brands.schemas import BrandConfiguration
from gallery_local_store import logical_gallery_key, validate_gallery_filename
from services.gallery_service import (
    build_gallery_view_url,
    commit_generated_image,
    gallery_image_exists,
    resolve_gallery_local_path,
)
from generation.edit_prompts import (
    EDIT_GOVERNANCE_SYSTEM,
    build_brand_edit_context_snippet,
    build_edit_user_prompt,
)
from generation.image_providers import ImageProviderNoOutput, estimate_price_usd, edit_image_to_file
from generation.image_providers.registry import model_supports_image_size

logger = logging.getLogger(__name__)


def run_gallery_image_edit(
    *,
    brand_id: str,
    config: BrandConfiguration,
    source_filename: str,
    instruction: str,
    model_id: str,
    aspect_ratio: str,
    image_size: str,
    google_api_key: str,
    openai_api_key: str,
    public_origin: str,
    signing_secret: str,
    allowed_models: tuple[str, ...],
    allowed_ratios: tuple[str, ...],
    allowed_sizes: tuple[str, ...],
) -> dict[str, Any]:
    """
    Load a gallery PNG/JPEG, call Gemini image edit, commit a new file, return ``BrandSlideGenerateResponse``-shaped dict.
    """
    if model_id not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model for edit. Choose from {list(allowed_models)}",
        )
    if aspect_ratio not in allowed_ratios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid aspect_ratio. Choose from {list(allowed_ratios)}",
        )
    if model_id == "gemini-3-pro-image-preview" and image_size not in allowed_sizes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image_size. Choose from {list(allowed_sizes)}",
        )
    if model_supports_image_size(model_id) and model_id != "gemini-3-pro-image-preview":
        if image_size not in allowed_sizes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image_size. Choose from {list(allowed_sizes)}",
            )

    try:
        validate_gallery_filename(source_filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid source_filename.") from exc
    if not gallery_image_exists(brand_id, source_filename):
        raise HTTPException(status_code=404, detail="Source image not found in gallery.")

    src_path = resolve_gallery_local_path(brand_id, source_filename)
    try:
        base = Image.open(src_path)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Could not read source image: {exc}") from exc

    brand_snippet = build_brand_edit_context_snippet(config)
    user_prompt = build_edit_user_prompt(instruction, brand_snippet)
    logger.info(
        "Image edit start brand_id=%s source=%s model=%s aspect=%s instruction_chars=%s",
        brand_id,
        source_filename,
        model_id,
        aspect_ratio,
        len(instruction),
    )
    logger.debug("Image edit user prompt preview:\n%s", user_prompt[:2500])

    out_name = f"rankify_edit_{uuid.uuid4().hex[:10]}.png"
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_png_path = tmp.name
    try:
        edit_image_to_file(
            model_id=model_id,
            edit_system_prompt=EDIT_GOVERNANCE_SYSTEM,
            edit_user_prompt=user_prompt,
            base_image=base,
            output_file_path=temp_png_path,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            google_api_key=google_api_key,
            openai_api_key=openai_api_key,
        )
        edit_batch = uuid.uuid4().hex[:8]
        out_name, file_size, _ = commit_generated_image(
            brand_id=brand_id,
            temp_source_path=temp_png_path,
            filename=out_name,
            batch_id=edit_batch,
            slide_index=None,
            model_id=model_id,
        )
    except ImageProviderNoOutput as exc:
        detail = str(exc).strip()
        if len(detail) > 1800:
            detail = detail[:1797] + "..."
        hint = (
            " The image model sometimes declines a pass (especially on images already edited once). "
            "Try again with a shorter instruction, edit from the original slide file in Versions, "
            "or try another model (e.g. gemini-3-pro-image-preview or openai:gpt-image-2)."
        )
        raise HTTPException(status_code=422, detail=detail + hint) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image edit failed brand_id=%s source=%s", brand_id, source_filename)
        raise HTTPException(status_code=502, detail=f"Image edit failed: {exc}") from exc
    finally:
        if os.path.isfile(temp_png_path):
            try:
                os.unlink(temp_png_path)
            except OSError:
                pass

    now = datetime.now(timezone.utc)
    view_url = build_gallery_view_url(
        brand_id=brand_id,
        filename=out_name,
        public_origin=public_origin,
        signing_secret=signing_secret,
    )
    per_image = estimate_price_usd(
        model_id,
        image_size if model_id == "gemini-3-pro-image-preview" or model_supports_image_size(model_id) else "2K",
    )

    logger.info(
        "Image edit done brand_id=%s new_file=%s bytes=%s",
        brand_id,
        out_name,
        file_size,
    )
    return {
        "images": [
            {
                "filename": out_name,
                "url": view_url,
                "storage_path": logical_gallery_key(brand_id, out_name),
                "size_bytes": file_size,
                "created_at": now.isoformat(),
                "age_hours": 0.0,
            }
        ],
        "model_used": model_id,
        "per_image_price_usd": per_image,
        "total_price_usd": round(per_image, 3),
        "message": f"Edited image saved for brand '{brand_id}' (refined from '{source_filename}').",
        "generation_audit_path": None,
    }
