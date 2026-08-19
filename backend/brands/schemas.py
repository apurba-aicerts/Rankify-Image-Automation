"""
Pydantic models for brand-scoped configuration.

All image and (future) text pipelines consume :class:`BrandConfiguration` so the core
generation code stays brand-agnostic.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_BRAND_ID_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")


def validate_brand_id(brand_id: str) -> str:
    """Return ``brand_id`` if it is a safe lowercase slug; otherwise raise ``ValueError``."""
    s = brand_id.strip().lower()
    msg = (
        "brand_id must be 2–64 chars, lowercase letters, digits, hyphens; "
        "cannot start/end with hyphen."
    )
    if len(s) < 2 or len(s) > 64 or not _BRAND_ID_RE.match(s):
        raise ValueError(msg)
    return s


def resolve_brand_id(brand_id: Optional[str]) -> str:
    """Use ``brand_id`` when provided; otherwise assign a new UUID slug."""
    if brand_id and brand_id.strip():
        return validate_brand_id(brand_id.strip().lower())
    return str(uuid.uuid4()).lower()


class BrandColors(BaseModel):
    """Palette and short rules for the model."""

    primary: list[str] = Field(default_factory=list, description="Hex colors, most important first.")
    secondary: list[str] = Field(default_factory=list)
    usage_rules: str = Field(default="", description="How to apply colors on slides.")


class BrandTypography(BaseModel):
    """Font preferences (descriptive; rendering is model-dependent)."""

    primary_font: str = ""
    headline_font: str = ""
    body_font: str = ""
    notes: str = ""


class BrandVoice(BaseModel):
    """Tone and audience — drives caption/hashtag pipelines when implemented."""

    tone_keywords: list[str] = Field(default_factory=list)
    writing_style: str = ""
    target_audience: str = ""


class BrandSocialDefaults(BaseModel):
    """Default controls for social image generation."""

    preferred_platforms: list[str] = Field(
        default_factory=list,
        description="e.g. linkedin, instagram, x",
    )
    default_aspect_ratio: str = "1:1"
    default_image_size: str = "2K"


class PlatformSpecificHints(BaseModel):
    """Optional per-platform copy or layout hints (platform_id -> short text)."""

    hints: dict[str, str] = Field(default_factory=dict)


class BrandContentThemes(BaseModel):
    """Themes and categories for campaigns."""

    categories: list[str] = Field(default_factory=list)
    recurring_themes: list[str] = Field(default_factory=list)


class BrandTextPreferences(BaseModel):
    """Inputs for future caption/hashtag generators."""

    hashtag_style: str = Field(default="", description="Preferred hashtag tone, count, mix.")
    caption_style: str = Field(default="", description="Length, emoji, CTA habits.")
    banned_phrases: list[str] = Field(default_factory=list)


class BrandGenerationRules(BaseModel):
    """
    Prompt and layout rules. ``governance_prompt_template`` is the main system prompt
    (brand law). Optional structured layout/visual fields are folded into prompts by
    :mod:`generation.prompt_builder` (visual-only; social copy fields are excluded).
    """

    governance_prompt_template: str = Field(
        ...,
        min_length=20,
        description="Full system / governance prompt for image generation (paste full brand bible here).",
    )
    design_guidelines: str = Field(
        default="",
        description="Extra layout/visual rules appended to governance context.",
    )
    layout_spacing_rules: str = Field(
        default="",
        description="Canvas sizes, margins, safe zones, grid, logo placement.",
    )
    cta_button_rules: str = Field(
        default="",
        description="Button shapes, colors, and CTA copy patterns.",
    )
    visual_style_rules: str = Field(
        default="",
        description="Imagery, backgrounds, gradients, mood, stock aesthetic.",
    )
    avoid_rules: str = Field(
        default="",
        description="Explicit do-not list for layouts, colors, and tone.",
    )
    slide_intro_template: str = Field(
        default="",
        description="If empty, a generic intro is used before structured post copy.",
    )
    slide_user_prompt_suffix: str = Field(
        default="",
        description="Appended after structured post copy (design bullets, CTA rules, etc.).",
    )


class BrandConfiguration(BaseModel):
    """
    Single source of truth for one brand. Persisted as JSON under ``data/brands/<brand_id>/``.
    """

    brand_id: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=200)
    tagline: str = ""
    legal_suffix: str = Field(default="", description="Trademark or ® line if needed.")

    colors: BrandColors = Field(default_factory=BrandColors)
    typography: BrandTypography = Field(default_factory=BrandTypography)
    voice: BrandVoice = Field(default_factory=BrandVoice)
    social_defaults: BrandSocialDefaults = Field(default_factory=BrandSocialDefaults)
    platform_hints: PlatformSpecificHints = Field(default_factory=PlatformSpecificHints)
    content_themes: BrandContentThemes = Field(default_factory=BrandContentThemes)
    text_preferences: BrandTextPreferences = Field(default_factory=BrandTextPreferences)
    generation: BrandGenerationRules

    logo_asset_filename: str = Field(default="logo.png", description="Filename under brand assets/.")

    updated_at: Optional[datetime] = None

    @field_validator("brand_id")
    @classmethod
    def _brand_slug(cls, value: str) -> str:
        return validate_brand_id(value.strip().lower())


class BrandSummary(BaseModel):
    """Lightweight list view."""

    brand_id: str
    display_name: str
    updated_at: Optional[datetime] = None


class BrandCreatePayload(BaseModel):
    """Body for creating a brand (``display_name`` + ``generation`` required; ``brand_id`` optional)."""

    brand_id: Optional[str] = Field(
        default=None,
        description="If omitted or empty, server assigns a UUID slug.",
    )
    display_name: str
    tagline: str = ""
    legal_suffix: str = ""
    colors: BrandColors = Field(default_factory=BrandColors)
    typography: BrandTypography = Field(default_factory=BrandTypography)
    voice: BrandVoice = Field(default_factory=BrandVoice)
    social_defaults: BrandSocialDefaults = Field(default_factory=BrandSocialDefaults)
    platform_hints: PlatformSpecificHints = Field(default_factory=PlatformSpecificHints)
    content_themes: BrandContentThemes = Field(default_factory=BrandContentThemes)
    text_preferences: BrandTextPreferences = Field(default_factory=BrandTextPreferences)
    generation: BrandGenerationRules
    logo_asset_filename: str = "logo.png"

    @field_validator("brand_id", mode="before")
    @classmethod
    def _optional_slug(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        return validate_brand_id(s.lower())

    def to_configuration(self) -> BrandConfiguration:
        return BrandConfiguration(
            brand_id=resolve_brand_id(self.brand_id),
            display_name=self.display_name,
            tagline=self.tagline,
            legal_suffix=self.legal_suffix,
            colors=self.colors,
            typography=self.typography,
            voice=self.voice,
            social_defaults=self.social_defaults,
            platform_hints=self.platform_hints,
            content_themes=self.content_themes,
            text_preferences=self.text_preferences,
            generation=self.generation,
            logo_asset_filename=self.logo_asset_filename,
            updated_at=datetime.now(timezone.utc),
        )


class BrandAiDraftRequest(BaseModel):
    """Unstructured brand notes → structured draft (review before ``POST /api/brands``)."""

    brand_materials: str = Field(..., min_length=30, max_length=120_000)
    brand_id: Optional[str] = Field(
        default=None,
        description="If set, this slug is required in the model output; if omitted, server picks a UUID.",
    )
    model_name: str = Field(default="gpt-4o-2024-08-06")

    @field_validator("brand_id", mode="before")
    @classmethod
    def _normalize_optional_brand_id(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        return validate_brand_id(s.lower())


class BrandAiDraftResponse(BaseModel):
    """Validated create payload ready for the wizard or ``POST /api/brands``."""

    draft: BrandCreatePayload
    model_used: str
