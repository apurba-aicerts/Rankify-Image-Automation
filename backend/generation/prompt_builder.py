"""Assemble prompts from :class:`~brands.schemas.BrandConfiguration` (brand-agnostic builders)."""

from __future__ import annotations

import logging

from brands.schemas import BrandConfiguration, BrandGenerationRules

logger = logging.getLogger(__name__)


def _template_opens_with_agent_role(template: str) -> bool:
    """True when the governance body already defines the agent (avoid duplicate headers)."""
    first_line = template.strip().split("\n", 1)[0].strip().lower()
    return first_line.startswith("you are ") or first_line.startswith("you're ")


def build_governance_system_prompt(cfg: BrandConfiguration) -> str:
    """
    Build the full system / governance prompt for Gemini image generation.

    ``governance_prompt_template`` is the primary brand constitution. When it already
    opens with an agent role (e.g. \"You are the official N+ ...\"), we skip the generic
    Rankify header to avoid conflicting instructions. Structured JSON fields are always
    appended so sliders, typography notes, and new generation.* blocks reach the model.
    """
    template = cfg.generation.governance_prompt_template.strip()

    if _template_opens_with_agent_role(template):
        opener = (
            f"AUTHORITATIVE BRAND: **{cfg.display_name}**. "
            "The constitution below overrides generic assumptions. "
            "Obey it for every pixel, type choice, and CTA.\n\n"
        )
        if cfg.tagline:
            opener += f"Tagline: {cfg.tagline}\n"
        if cfg.legal_suffix:
            opener += f"Legal line: {cfg.legal_suffix}\n"
        if cfg.tagline or cfg.legal_suffix:
            opener += "\n"
        parts = [opener.strip(), template]
    else:
        header = (
            f"You are the official social media design agent for **{cfg.display_name}**.\n"
            "Respect the brand rules below exactly. Do not introduce conflicting styles, "
            "logos, or palettes from other companies.\n"
        )
        if cfg.tagline:
            header += f"\nBrand tagline: {cfg.tagline}"
        if cfg.legal_suffix:
            header += f"\nTrademark / legal: {cfg.legal_suffix}"
        parts = [header.strip(), template]

    if cfg.generation.design_guidelines.strip():
        parts.append("SUPPLEMENTARY DESIGN GUIDELINES:\n" + cfg.generation.design_guidelines.strip())

    modules = _format_generation_rule_modules(cfg.generation)
    if modules:
        parts.append(modules)

    structured = _format_structured_brand_knobs(cfg)
    if structured:
        parts.append(structured)

    out = "\n\n".join(p for p in parts if p)
    logger.debug(
        "build_governance_system_prompt brand=%s chars=%s",
        cfg.display_name,
        len(out),
    )
    return out


def _format_generation_rule_modules(gen: BrandGenerationRules) -> str:
    """Long-form sections stored beside governance (layout, CTA, visual, avoid)."""
    blocks: list[str] = []
    if gen.layout_spacing_rules.strip():
        blocks.append("LAYOUT, SPACING & COMPOSITION:\n" + gen.layout_spacing_rules.strip())
    if gen.cta_button_rules.strip():
        blocks.append("BUTTON & CTA RULES:\n" + gen.cta_button_rules.strip())
    if gen.visual_style_rules.strip():
        blocks.append("VISUAL & DESIGN STYLE:\n" + gen.visual_style_rules.strip())
    if gen.avoid_rules.strip():
        blocks.append("AVOID (DO NOT):\n" + gen.avoid_rules.strip())
    if not blocks:
        return ""
    return "STRUCTURED CREATIVE MODULES (must influence the image):\n\n" + "\n\n".join(blocks)


def _format_structured_brand_knobs(cfg: BrandConfiguration) -> str:
    """Summarize BrandConfiguration JSON so the model sees every onboarded field."""
    lines: list[str] = []
    g = cfg.generation

    if cfg.colors.primary:
        lines.append("Primary colors: " + ", ".join(cfg.colors.primary))
    if cfg.colors.secondary:
        lines.append("Secondary colors: " + ", ".join(cfg.colors.secondary))
    if cfg.colors.usage_rules.strip():
        lines.append("Color usage: " + cfg.colors.usage_rules.strip())

    typo_bits: list[str] = []
    if cfg.typography.primary_font:
        typo_bits.append(f"primary={cfg.typography.primary_font}")
    if cfg.typography.headline_font:
        typo_bits.append(f"headlines={cfg.typography.headline_font}")
    if cfg.typography.body_font:
        typo_bits.append(f"body={cfg.typography.body_font}")
    if typo_bits:
        lines.append("Typography: " + ", ".join(typo_bits))
    if cfg.typography.notes.strip():
        lines.append("Typography / canvas notes: " + cfg.typography.notes.strip())

    if cfg.voice.tone_keywords:
        lines.append("Tone keywords: " + ", ".join(cfg.voice.tone_keywords))
    if cfg.voice.writing_style.strip():
        lines.append("Writing style: " + cfg.voice.writing_style.strip())
    if cfg.voice.target_audience.strip():
        lines.append("Target audience: " + cfg.voice.target_audience.strip())

    if cfg.content_themes.categories:
        lines.append("Content categories: " + ", ".join(cfg.content_themes.categories))
    if cfg.content_themes.recurring_themes:
        lines.append("Messaging / recurring themes: " + ", ".join(cfg.content_themes.recurring_themes))

    plat = cfg.social_defaults.preferred_platforms
    if plat:
        lines.append("Preferred platforms: " + ", ".join(plat))
    lines.append(
        f"Default generation canvas hints: aspect_ratio={cfg.social_defaults.default_aspect_ratio}, "
        f"image_size={cfg.social_defaults.default_image_size}"
    )

    if cfg.text_preferences.caption_style.strip():
        lines.append("On-image caption style: " + cfg.text_preferences.caption_style.strip())
    if cfg.text_preferences.hashtag_style.strip():
        lines.append("Hashtag style (if text on image): " + cfg.text_preferences.hashtag_style.strip())
    if cfg.text_preferences.banned_phrases:
        lines.append("Banned phrases: " + ", ".join(cfg.text_preferences.banned_phrases))

    if cfg.platform_hints.hints:
        hint_lines = "; ".join(f"{k}: {v}" for k, v in cfg.platform_hints.hints.items())
        lines.append("Platform hints: " + hint_lines)

    if not lines:
        return ""
    return "ONBOARDED BRAND JSON (reinforce with the constitution above):\n" + "\n".join(f"- {line}" for line in lines)


def build_slide_user_prompt(structured_post_copy: str, cfg: BrandConfiguration) -> str:
    """Combine intro, marketer copy, suffix, and optional platform hints."""
    intro = cfg.generation.slide_intro_template.strip()
    if not intro:
        intro = (
            f"Create a professional social slide for **{cfg.display_name}** "
            f"(default canvas 1080×1080 unless platform hints say otherwise).\n\n"
        )
    core = structured_post_copy.strip()
    blocks = [intro + core]
    suffix = cfg.generation.slide_user_prompt_suffix.strip()
    if suffix:
        blocks.append(suffix)
    if cfg.platform_hints.hints:
        hint_lines = "\n".join(f"- {k}: {v}" for k, v in cfg.platform_hints.hints.items())
        blocks.append("PLATFORM HINTS (apply when the post targets that network):\n" + hint_lines)
    out = "\n\n".join(blocks)
    logger.debug("build_slide_user_prompt brand=%s chars=%s", cfg.display_name, len(out))
    return out
