"""End-to-end slide generation for one brand (config + Gemini + gallery)."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from PIL import Image

from brands.repository_factory import get_brand_repository
from brands.schemas import BrandConfiguration
from generation.generation_audit import write_generation_audit_file
from generation.image_providers import ImageProviderNoOutput, estimate_price_usd, generate_slide_to_file
from generation.image_providers.registry import model_supports_image_size, normalize_model_id
from generation.prompt_builder import build_governance_system_prompt, build_slide_user_prompt
from gallery_local_store import logical_gallery_key
from services.brand_assets import resolve_logo_local_path
from services.gallery_service import build_gallery_view_url, commit_generated_image

logger = logging.getLogger(__name__)


def run_brand_slide_generation(
    *,
    brand_id: str,
    config: BrandConfiguration,
    structured_post_copy: str,
    model_id: str,
    slide_count: int,
    aspect_ratio: str,
    image_size: str,
    logo_override: Optional[Image.Image],
    logo_fallback_path: Path,
    google_api_key: str,
    openai_api_key: str,
    public_origin: str,
    signing_secret: str,
    allowed_models: tuple[str, ...],
    allowed_ratios: tuple[str, ...],
    allowed_sizes: tuple[str, ...],
) -> dict[str, Any]:
    """
    Execute validation, Gemini calls, and gallery writes.

    Returns a dict suitable for ``BrandSlideGenerateResponse.model_validate``.
    """
    if model_id not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model. Choose from {list(allowed_models)}",
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

    batch_id = uuid.uuid4().hex[:8]

    repo = get_brand_repository()
    governance = build_governance_system_prompt(config)
    # INFO: short line only (full prompt is huge and is easy to "lose" in the terminal).
    logger.info(
        "Governance prompt ready brand_id=%s chars=%s",
        brand_id,
        len(governance),
    )
    logger.debug(
        "Governance prompt preview (first 2000 chars) brand_id=%s:\n%s",
        brand_id,
        governance,
    )
    slide_user = build_slide_user_prompt(structured_post_copy, config)
    logger.info("Slide user prompt ready brand_id=%s chars=%s", brand_id, len(slide_user))
    logger.debug(
        "Slide user prompt preview (first 2000 chars) brand_id=%s:\n%s",
        brand_id,
        slide_user,
    )

    if logo_override is not None:
        logo_image = logo_override
        logo_description = "multipart logo override (this request only)"
    else:
        logo_path = resolve_logo_local_path(brand_id, config.logo_asset_filename)
        if logo_path is not None and logo_path.is_file():
            logo_image = Image.open(logo_path)
            logo_description = f"brand logo file: {logo_path.resolve()}"
        else:
            logo_image = Image.open(logo_fallback_path)
            logo_description = f"default fallback logo: {logo_fallback_path.resolve()}"

    audit_path = write_generation_audit_file(
        brand_id=brand_id,
        batch_id=batch_id,
        model_id=model_id,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        slide_count=slide_count,
        logo_description=logo_description,
        config=config,
        structured_post_copy=structured_post_copy,
        governance_system_prompt=governance,
        slide_user_prompt=slide_user,
    )
    audit_path_str: Optional[str] = str(audit_path) if audit_path is not None else None
    logger.info(
        "Generation audit: %s",
        audit_path_str
        or "(not written — RANKIFY_GENERATION_AUDIT=0, or disk error; see logs)",
    )

    images_out: list[dict[str, Any]] = []
    logger.info(
        "Slide generation started brand_id=%s batch=%s slides=%s model=%s aspect=%s",
        brand_id,
        batch_id,
        slide_count,
        model_id,
        aspect_ratio,
    )

    provider, api_model = normalize_model_id(model_id)

    def _commit_one(index: int, temp_png_path: str) -> tuple[str, int]:
        filename_local = f"rankify_slide_{batch_id}_{index}.png"
        filename, sz, _ = commit_generated_image(
            brand_id=brand_id,
            temp_source_path=temp_png_path,
            filename=filename_local,
            batch_id=batch_id,
            slide_index=index,
            model_id=model_id,
        )
        return filename, sz

    def _view_url(filename: str) -> str:
        return build_gallery_view_url(
            brand_id=brand_id,
            filename=filename,
            public_origin=public_origin,
            signing_secret=signing_secret,
        )

    # OpenAI supports multi-image in one request via n (logo reference via images.edit).
    if provider == "openai" and slide_count > 1:
        from generation.image_providers.openai_provider import generate_brand_slides_b64
        import base64
        from io import BytesIO

        b64_list = generate_brand_slides_b64(
            openai_api_key=openai_api_key,
            api_model=api_model,
            brand_governance_prompt=governance,
            slide_user_prompt=slide_user,
            logo=logo_image,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            n=slide_count,
        )

        for index, b64_img in enumerate(b64_list[:slide_count], start=1):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_png_path = tmp.name
            try:
                img = Image.open(BytesIO(base64.b64decode(b64_img)))
                img.save(temp_png_path)
                filename, file_size = _commit_one(index, temp_png_path)
                logger.info(
                    "Slide %s/%s written brand_id=%s file=%s bytes=%s (openai batch)",
                    index,
                    slide_count,
                    brand_id,
                    filename,
                    file_size,
                )
            finally:
                if os.path.isfile(temp_png_path):
                    try:
                        os.unlink(temp_png_path)
                    except OSError:
                        pass

            now = datetime.now(timezone.utc)
            images_out.append(
                {
                    "filename": filename,
                    "url": _view_url(filename),
                    "storage_path": logical_gallery_key(brand_id, filename),
                    "size_bytes": file_size,
                    "created_at": now.isoformat(),
                    "age_hours": 0.0,
                }
            )
        per_image = estimate_price_usd(model_id, image_size)
        total = round(per_image * slide_count, 3)
        logger.info(
            "Slide generation finished brand_id=%s batch=%s images=%s total_usd=%s",
            brand_id,
            batch_id,
            len(images_out),
            total,
        )
        return {
            "images": images_out,
            "model_used": model_id,
            "per_image_price_usd": per_image,
            "total_price_usd": total,
            "message": f"Successfully generated {len(images_out)} slide(s) for brand '{brand_id}'.",
            "generation_audit_path": audit_path_str,
        }

    # Imagen 4 supports multi-image in one request via number_of_images (max 4).
    if provider == "imagen":
        from generation.image_providers.imagen_provider import ensure_png_bytes, generate_images_bytes

        remaining = slide_count
        index = 1
        while remaining > 0:
            chunk = 4 if remaining > 4 else remaining
            imgs = generate_images_bytes(
                google_api_key=google_api_key,
                model=api_model,
                prompt=slide_user,
                aspect_ratio=aspect_ratio,
                number_of_images=chunk,
            )
            for b in imgs:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    temp_png_path = tmp.name
                try:
                    Path(temp_png_path).write_bytes(ensure_png_bytes(b))
                    filename, file_size = _commit_one(index, temp_png_path)
                finally:
                    if os.path.isfile(temp_png_path):
                        try:
                            os.unlink(temp_png_path)
                        except OSError:
                            pass

                now = datetime.now(timezone.utc)
                images_out.append(
                    {
                        "filename": filename,
                        "url": _view_url(filename),
                        "storage_path": logical_gallery_key(brand_id, filename),
                        "size_bytes": file_size,
                        "created_at": now.isoformat(),
                        "age_hours": 0.0,
                    }
                )
                index += 1
            remaining -= chunk

        per_image = estimate_price_usd(model_id, image_size)
        total = round(per_image * slide_count, 3)
        logger.info(
            "Slide generation finished brand_id=%s batch=%s images=%s total_usd=%s",
            brand_id,
            batch_id,
            len(images_out),
            total,
        )
        return {
            "images": images_out,
            "model_used": model_id,
            "per_image_price_usd": per_image,
            "total_price_usd": total,
            "message": f"Successfully generated {len(images_out)} slide(s) for brand '{brand_id}'.",
            "generation_audit_path": audit_path_str,
        }

    for index in range(1, slide_count + 1):
        filename = f"rankify_slide_{batch_id}_{index}.png"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            temp_png_path = tmp.name
        try:
            generate_slide_to_file(
                model_id=model_id,
                brand_governance_prompt=governance,
                slide_user_prompt=slide_user,
                logo=logo_image,
                output_file_path=temp_png_path,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                google_api_key=google_api_key,
                openai_api_key=openai_api_key,
            )
            filename, file_size, _ = commit_generated_image(
                brand_id=brand_id,
                temp_source_path=temp_png_path,
                filename=filename,
                batch_id=batch_id,
                slide_index=index,
                model_id=model_id,
            )
            logger.info(
                "Slide %s/%s written brand_id=%s file=%s bytes=%s",
                index,
                slide_count,
                brand_id,
                filename,
                file_size,
            )
        except ImageProviderNoOutput as exc:
            logger.warning(
                "Slide %s %s returned no image brand_id=%s finish_reason=%s",
                index,
                exc.provider,
                brand_id,
                getattr(exc, "finish_reason", None),
            )
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            logger.warning("Slide %s validation error brand_id=%s: %s", index, brand_id, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Slide %s generation failed brand_id=%s", index, brand_id)
            raise HTTPException(
                status_code=502,
                detail=f"Image generation failed for slide {index}: {str(exc)}",
            ) from exc
        finally:
            if os.path.isfile(temp_png_path):
                try:
                    os.unlink(temp_png_path)
                except OSError:
                    pass

        now = datetime.now(timezone.utc)
        images_out.append(
            {
                "filename": filename,
                "url": _view_url(filename),
                "storage_path": logical_gallery_key(brand_id, filename),
                "size_bytes": file_size,
                "created_at": now.isoformat(),
                "age_hours": 0.0,
            }
        )

    per_image = estimate_price_usd(model_id, image_size)
    total = round(per_image * slide_count, 3)

    logger.info(
        "Slide generation finished brand_id=%s batch=%s images=%s total_usd=%s",
        brand_id,
        batch_id,
        len(images_out),
        total,
    )
    return {
        "images": images_out,
        "model_used": model_id,
        "per_image_price_usd": per_image,
        "total_price_usd": total,
        "message": f"Successfully generated {slide_count} slide(s) for brand '{brand_id}'.",
        "generation_audit_path": audit_path_str,
    }
