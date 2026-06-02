"""Dispatch slide generate / gallery edit to Gemini, OpenAI, or Imagen."""

from __future__ import annotations

from fastapi import HTTPException
from PIL import Image

from generation.image_providers import gemini_provider, openai_provider
from generation.image_providers.registry import provider_for_model
from generation.image_providers.registry import (
    model_supports_image_size,
    normalize_model_id,
    requires_google_api_key,
    requires_openai_api_key,
)


def _check_api_keys(
    model_id: str,
    *,
    google_api_key: str,
    openai_api_key: str,
) -> None:
    if requires_google_api_key(model_id) and not google_api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY is not configured on the server (required for Google image models).",
        )
    if requires_openai_api_key(model_id) and not openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server (required for OpenAI image models).",
        )


def generate_slide_to_file(
    *,
    model_id: str,
    brand_governance_prompt: str,
    slide_user_prompt: str,
    logo: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str,
    google_api_key: str,
    openai_api_key: str,
) -> str:
    _check_api_keys(model_id, google_api_key=google_api_key, openai_api_key=openai_api_key)
    provider, api_model = normalize_model_id(model_id)
    gemini_size = image_size if api_model == "gemini-3-pro-image-preview" else None
    openai_size = image_size if model_supports_image_size(model_id) else "2K"

    if provider == "gemini":
        return gemini_provider.generate_brand_slide_to_file(
            google_api_key=google_api_key,
            api_model=api_model,
            brand_governance_prompt=brand_governance_prompt,
            slide_user_prompt=slide_user_prompt,
            logo=logo,
            output_file_path=output_file_path,
            aspect_ratio=aspect_ratio,
            image_size=gemini_size,
        )
    if provider == "openai":
        return openai_provider.generate_brand_slide_to_file(
            openai_api_key=openai_api_key,
            api_model=api_model,
            brand_governance_prompt=brand_governance_prompt,
            slide_user_prompt=slide_user_prompt,
            logo=logo,
            output_file_path=output_file_path,
            aspect_ratio=aspect_ratio,
            image_size=openai_size,
        )
    raise HTTPException(status_code=400, detail=f"Model provider not supported for generate: {provider_for_model(model_id)}")


def edit_image_to_file(
    *,
    model_id: str,
    edit_system_prompt: str,
    edit_user_prompt: str,
    base_image: Image.Image,
    output_file_path: str,
    aspect_ratio: str,
    image_size: str,
    google_api_key: str,
    openai_api_key: str,
) -> str:
    _check_api_keys(model_id, google_api_key=google_api_key, openai_api_key=openai_api_key)
    provider, api_model = normalize_model_id(model_id)
    gemini_size = image_size if api_model == "gemini-3-pro-image-preview" else None
    openai_size = image_size if model_supports_image_size(model_id) else "2K"

    if provider == "gemini":
        return gemini_provider.edit_image_to_file(
            google_api_key=google_api_key,
            api_model=api_model,
            edit_system_prompt=edit_system_prompt,
            edit_user_prompt=edit_user_prompt,
            base_image=base_image,
            output_file_path=output_file_path,
            aspect_ratio=aspect_ratio,
            image_size=gemini_size,
        )
    if provider == "openai":
        return openai_provider.edit_image_to_file(
            openai_api_key=openai_api_key,
            api_model=api_model,
            edit_system_prompt=edit_system_prompt,
            edit_user_prompt=edit_user_prompt,
            base_image=base_image,
            output_file_path=output_file_path,
            aspect_ratio=aspect_ratio,
            image_size=openai_size,
        )
    raise HTTPException(status_code=400, detail=f"Model provider not supported for edit: {provider_for_model(model_id)}")
