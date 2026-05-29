"""
Pydantic shape for OpenAI ``chat.completions.parse`` structured outputs.

OpenAI strict JSON schema does **not** accept open ``dict[str, str]`` (e.g.
``PlatformSpecificHints.hints``). We use ``entries: list[{platform_id, hint}]``
and convert to :class:`PlatformSpecificHints` after the API returns.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from brands.schemas import (
    BrandColors,
    BrandContentThemes,
    BrandCreatePayload,
    BrandGenerationRules,
    BrandSocialDefaults,
    BrandTextPreferences,
    BrandTypography,
    BrandVoice,
    PlatformSpecificHints,
    validate_brand_id,
)


class PlatformHintEntry(BaseModel):
    """One platform-specific hint (replaces a single key in ``hints`` dict)."""

    platform_id: str = Field(
        ...,
        description="Lowercase platform key, e.g. linkedin, instagram, x.",
    )
    hint: str = Field(
        default="",
        description="Short layout or copy hint for that platform.",
    )


class OpenAIPlatformHints(BaseModel):
    """Structured-output-safe stand-in for ``PlatformSpecificHints``."""

    entries: list[PlatformHintEntry] = Field(
        default_factory=list,
        description="Per-platform hints; empty list if none.",
    )


class OpenAIBrandCreateDraft(BaseModel):
    """
    Same information as ``BrandCreatePayload``, but ``platform_hints`` uses
    ``entries`` instead of a string-to-string map so OpenAI strict schema validates.
    """

    brand_id: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=200)
    tagline: str = ""
    legal_suffix: str = ""
    colors: BrandColors = Field(default_factory=BrandColors)
    typography: BrandTypography = Field(default_factory=BrandTypography)
    voice: BrandVoice = Field(default_factory=BrandVoice)
    social_defaults: BrandSocialDefaults = Field(default_factory=BrandSocialDefaults)
    platform_hints: OpenAIPlatformHints = Field(default_factory=OpenAIPlatformHints)
    content_themes: BrandContentThemes = Field(default_factory=BrandContentThemes)
    text_preferences: BrandTextPreferences = Field(default_factory=BrandTextPreferences)
    generation: BrandGenerationRules
    logo_asset_filename: str = "logo.png"

    @field_validator("brand_id")
    @classmethod
    def _brand_slug(cls, value: str) -> str:
        return validate_brand_id(value.strip().lower())


def openai_draft_to_create_payload(draft: OpenAIBrandCreateDraft) -> BrandCreatePayload:
    hints: dict[str, str] = {}
    for row in draft.platform_hints.entries:
        key = (row.platform_id or "").strip().lower()
        if key:
            hints[key] = row.hint
    return BrandCreatePayload(
        brand_id=draft.brand_id,
        display_name=draft.display_name,
        tagline=draft.tagline,
        legal_suffix=draft.legal_suffix,
        colors=draft.colors,
        typography=draft.typography,
        voice=draft.voice,
        social_defaults=draft.social_defaults,
        platform_hints=PlatformSpecificHints(hints=hints),
        content_themes=draft.content_themes,
        text_preferences=draft.text_preferences,
        generation=draft.generation,
        logo_asset_filename=draft.logo_asset_filename,
    )
