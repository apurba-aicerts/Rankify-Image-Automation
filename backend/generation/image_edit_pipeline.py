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
from gallery_local_store import (
    commit_temp_file_to_gallery,
    gallery_file_exists,
    logical_gallery_key,
    resolved_gallery_file_path,
    validate_gallery_filename,
)
from gallery_url_signing import GALLERY_IMAGE_URL_TTL_SECONDS, build_brand_gallery_image_view_url
from gemini_slide_client import GeminiBrandImageClient, GeminiNoImageInResponse
from generation.edit_prompts import (
    EDIT_GOVERNANCE_SYSTEM,
    build_brand_edit_context_snippet,
    build_edit_user_prompt,
)

logger = logging.getLogger(__name__)


def _estimate_usd_price_per_image(model_id: str, resolution: str, price_table: dict) -> float:
    if model_id == "gemini-3-pro-image-preview":
        return float(price_table[model_id].get(resolution, 0.134))
    return float(price_table.get(model_id, 0.039))


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
    public_origin: str,
    signing_secret: str,
    allowed_models: tuple[str, ...],
    allowed_ratios: tuple[str, ...],
    allowed_sizes: tuple[str, ...],
    price_table: dict,
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
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not configured on the server.")

    try:
        validate_gallery_filename(source_filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid source_filename.") from exc
    if not gallery_file_exists(brand_id, source_filename):
        raise HTTPException(status_code=404, detail="Source image not found in gallery.")

    src_path = resolved_gallery_file_path(brand_id, source_filename)
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
    client = GeminiBrandImageClient(google_api_key)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_png_path = tmp.name
    try:
        client.edit_image_to_file(
            edit_system_prompt=EDIT_GOVERNANCE_SYSTEM,
            edit_user_prompt=user_prompt,
            base_image=base,
            output_file_path=temp_png_path,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            image_size=image_size if model_id == "gemini-3-pro-image-preview" else None,
        )
        commit_temp_file_to_gallery(brand_id, temp_png_path, out_name)
        file_size = resolved_gallery_file_path(brand_id, out_name).stat().st_size
    except GeminiNoImageInResponse as exc:
        detail = str(exc).strip()
        if len(detail) > 1800:
            detail = detail[:1797] + "..."
        hint = (
            " The image model sometimes declines a pass (especially on images already edited once). "
            "Try again with a shorter instruction, edit from the original slide file in Versions, "
            "or switch the edit model to gemini-3-pro-image-preview if your client supports it."
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
    view_url = build_brand_gallery_image_view_url(
        public_api_origin=public_origin,
        signing_secret=signing_secret,
        brand_id=brand_id,
        filename=out_name,
        ttl_seconds=GALLERY_IMAGE_URL_TTL_SECONDS,
    )
    per_image = _estimate_usd_price_per_image(
        model_id,
        image_size if model_id == "gemini-3-pro-image-preview" else "2K",
        price_table,
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
