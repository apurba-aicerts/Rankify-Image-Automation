"""OpenAI Images API — generate (with logo reference) and edit."""

from __future__ import annotations

import base64
import logging
from io import BytesIO

from openai import OpenAI
from PIL import Image

from generation.image_providers.exceptions import ImageProviderNoOutput
from generation.image_providers.openai_sizes import openai_size_for_aspect, openai_size_for_gallery_edit

logger = logging.getLogger(__name__)

# Models that accept ``input_fidelity`` (not gpt-image-2).
_INPUT_FIDELITY_MODELS = frozenset({"gpt-image-1", "gpt-image-1.5"})

# Gemini edit prompts mention "inline image data"; OpenAI sends the raster as a file.
_OPENAI_EDIT_SYSTEM = """You are a precision image editor for branded social marketing assets.

The user message includes an attached SOURCE IMAGE file. Treat every pixel outside the explicit edit request as ground truth to preserve.

NON-NEGOTIABLE RULES:
1) Apply ONLY what the USER EDIT REQUEST asks for. Make the smallest change that fulfills the request.
2) Do NOT fully regenerate or redesign the piece. Do NOT replace layout or crop unless the user explicitly asks.
3) Preserve unless the user explicitly asks to change them: on-image typography, logo placement, subject placement, and brand look.
4) Do NOT add watermarks, device frames, or spurious UI.
5) Output exactly ONE full-frame raster image; match the source framing unless the user asked otherwise.
"""


def _pil_to_png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _save_b64_to_file(b64_json: str | None, output_file_path: str) -> None:
    if not b64_json:
        raise ImageProviderNoOutput(
            "OpenAI returned no image data (empty b64_json).",
            provider="openai",
        )
    raw = base64.b64decode(b64_json)
    if not raw:
        raise ImageProviderNoOutput("OpenAI returned empty image bytes.", provider="openai")
    image = Image.open(BytesIO(raw))
    image.save(output_file_path)


def _as_upload_file(png_bytes: bytes, filename: str) -> tuple[str, bytes, str]:
    """Multipart file tuple for the OpenAI Python SDK."""
    return (filename, png_bytes, "image/png")


def _build_edit_kwargs(
    *,
    api_model: str,
    prompt: str,
    image_bytes_list: list[bytes],
    image_filenames: list[str],
    aspect_ratio: str,
    image_size: str,
    gallery_edit: bool = False,
) -> dict:
    if gallery_edit:
        size = openai_size_for_gallery_edit(aspect_ratio, image_size, api_model=api_model)
    else:
        size = openai_size_for_aspect(aspect_ratio, image_size, api_model=api_model)
    files = [
        _as_upload_file(b, image_filenames[i] if i < len(image_filenames) else f"input_{i}.png")
        for i, b in enumerate(image_bytes_list)
    ]
    kwargs: dict = {
        "model": api_model,
        "image": files if len(files) > 1 else files[0],
        "prompt": prompt[:32000],
        "size": size,
        "quality": "high",
        "output_format": "png",
        "n": 1,
    }
    if api_model in _INPUT_FIDELITY_MODELS:
        kwargs["input_fidelity"] = "high"
    return kwargs


def generate_brand_slide_to_file(
    *,
    openai_api_key: str,
    api_model: str,
    brand_governance_prompt: str,
    slide_user_prompt: str,
    logo: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str,
) -> str:
    """
    Generate a branded slide using the logo as a reference image (Images API edit workflow).
    """
    client = OpenAI(api_key=openai_api_key)
    combined = (
        f"{brand_governance_prompt.strip()}\n\n"
        f"---\n\n"
        f"{slide_user_prompt.strip()}\n\n"
        "Use the attached brand logo faithfully in the slide layout. "
        "Output one complete social/marketing slide image."
    )
    logo_bytes = _pil_to_png_bytes(logo)
    kwargs = _build_edit_kwargs(
        api_model=api_model,
        prompt=combined,
        image_bytes_list=[logo_bytes],
        image_filenames=["brand_logo.png"],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    logger.info(
        "OpenAI images.edit (slide generate) model=%s size=%s aspect=%s",
        api_model,
        kwargs["size"],
        aspect_ratio,
    )
    try:
        result = client.images.edit(**kwargs)
    except Exception as exc:
        logger.exception("OpenAI slide generation failed model=%s", api_model)
        raise RuntimeError(f"OpenAI image generation failed: {exc}") from exc

    data = result.data or []
    if not data:
        raise ImageProviderNoOutput("OpenAI returned no images in response.", provider="openai")
    _save_b64_to_file(data[0].b64_json, output_file_path)
    logger.info("OpenAI slide saved path=%s model=%s", output_file_path, api_model)
    return output_file_path


def edit_image_to_file(
    *,
    openai_api_key: str,
    api_model: str,
    edit_system_prompt: str,
    edit_user_prompt: str,
    base_image: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str,
) -> str:
    """Refine an existing gallery image with OpenAI Images API edit."""
    client = OpenAI(api_key=openai_api_key)
    combined = f"{_OPENAI_EDIT_SYSTEM.strip()}\n\n{edit_user_prompt.strip()}"
    base_bytes = _pil_to_png_bytes(base_image)
    kwargs = _build_edit_kwargs(
        api_model=api_model,
        prompt=combined,
        image_bytes_list=[base_bytes],
        image_filenames=["source_slide.png"],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        gallery_edit=True,
    )
    logger.info(
        "OpenAI images.edit (gallery) model=%s size=%s aspect=%s",
        api_model,
        kwargs["size"],
        aspect_ratio,
    )
    try:
        result = client.images.edit(**kwargs)
    except Exception as exc:
        logger.exception("OpenAI gallery edit failed model=%s", api_model)
        raise RuntimeError(f"OpenAI image edit failed: {exc}") from exc

    data = result.data or []
    if not data:
        raise ImageProviderNoOutput("OpenAI edit returned no images.", provider="openai")
    _save_b64_to_file(data[0].b64_json, output_file_path)
    logger.info("OpenAI edit saved path=%s model=%s", output_file_path, api_model)
    return output_file_path
