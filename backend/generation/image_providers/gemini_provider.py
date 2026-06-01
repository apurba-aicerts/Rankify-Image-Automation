"""Gemini image generation — thin wrapper around :class:`GeminiBrandImageClient`."""

from __future__ import annotations

from PIL import Image

from gemini_slide_client import GeminiBrandImageClient, GeminiNoImageInResponse
from generation.image_providers.exceptions import ImageProviderNoOutput


def _wrap_gemini_no_image(exc: GeminiNoImageInResponse) -> ImageProviderNoOutput:
    return ImageProviderNoOutput(
        str(exc),
        provider="gemini",
        finish_reason=getattr(exc, "finish_reason", None),
    )


def generate_brand_slide_to_file(
    *,
    google_api_key: str,
    api_model: str,
    brand_governance_prompt: str,
    slide_user_prompt: str,
    logo: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str | None,
) -> str:
    client = GeminiBrandImageClient(google_api_key)
    try:
        return client.generate_brand_slide_to_file(
            brand_governance_prompt=brand_governance_prompt,
            slide_user_prompt=slide_user_prompt,
            logo=logo,
            output_file_path=output_file_path,
            model_id=api_model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    except GeminiNoImageInResponse as exc:
        raise _wrap_gemini_no_image(exc) from exc


def edit_image_to_file(
    *,
    google_api_key: str,
    api_model: str,
    edit_system_prompt: str,
    edit_user_prompt: str,
    base_image: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str | None,
) -> str:
    client = GeminiBrandImageClient(google_api_key)
    try:
        return client.edit_image_to_file(
            edit_system_prompt=edit_system_prompt,
            edit_user_prompt=edit_user_prompt,
            base_image=base_image,
            output_file_path=output_file_path,
            model_id=api_model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    except GeminiNoImageInResponse as exc:
        raise _wrap_gemini_no_image(exc) from exc
