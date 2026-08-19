"""
Write a human-readable audit file for each image-generation run.

Contains the exact strings sent to Gemini (governance + slide user), the marketer
structured post copy input, and a snapshot of brand colors, typography, voice, etc.

Disable with env ``RANKIFY_GENERATION_AUDIT=0`` (default: on).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from brands.schemas import BrandConfiguration
from gallery_local_store import gallery_dir_for_brand, validate_brand_id

logger = logging.getLogger(__name__)


def generation_audit_enabled() -> bool:
    v = (os.getenv("RANKIFY_GENERATION_AUDIT", "1") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _rule_block(title: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return f"\n--- {title} ---\n(empty)\n"
    return f"\n--- {title} ---\n{body}\n"


def build_generation_audit_text(
    *,
    brand_id: str,
    batch_id: str,
    model_id: str,
    aspect_ratio: str,
    image_size: str,
    slide_count: int,
    logo_description: str,
    config: BrandConfiguration,
    structured_post_copy: str,
    governance_system_prompt: str,
    slide_user_prompt: str,
) -> str:
    """Single UTF-8 document for disk (and optional echo)."""
    bid = validate_brand_id(brand_id)
    now = datetime.now(timezone.utc).isoformat()
    c = config.colors
    t = config.typography
    v = config.voice
    sd = config.social_defaults
    g = config.generation
    lines: list[str] = [
        "=" * 80,
        "RANKIFY — GENERATION AUDIT (full payload sent to image model)",
        "=" * 80,
        f"Generated at (UTC): {now}",
        f"brand_id: {bid}",
        f"batch_id: {batch_id}",
        f"display_name: {config.display_name}",
        f"tagline: {config.tagline or '(none)'}",
        f"legal_suffix: {config.legal_suffix or '(none)'}",
        "",
        "--- API / IMAGE PARAMETERS ---",
        f"model_id: {model_id}",
        f"aspect_ratio: {aspect_ratio}",
        f"image_size: {image_size}",
        f"slide_count (images requested): {slide_count}",
        f"logo_source: {logo_description}",
        "",
        "--- COLORS (brand profile) ---",
        f"primary: {', '.join(c.primary) if c.primary else '(none)'}",
        f"secondary: {', '.join(c.secondary) if c.secondary else '(none)'}",
        _rule_block("COLOR USAGE RULES", c.usage_rules),
        "--- TYPOGRAPHY (brand profile) ---",
        f"primary_font: {t.primary_font or '(none)'}",
        f"headline_font: {t.headline_font or '(none)'}",
        f"body_font: {t.body_font or '(none)'}",
        _rule_block("TYPOGRAPHY NOTES", t.notes),
        "--- VOICE (brand profile) ---",
        f"tone_keywords: {', '.join(v.tone_keywords) if v.tone_keywords else '(none)'}",
        _rule_block("WRITING STYLE", v.writing_style),
        _rule_block("TARGET AUDIENCE", v.target_audience),
        "--- SOCIAL DEFAULTS ---",
        f"preferred_platforms: {', '.join(sd.preferred_platforms) if sd.preferred_platforms else '(none)'}",
        f"default_aspect_ratio (brand): {sd.default_aspect_ratio}",
        f"default_image_size (brand): {sd.default_image_size}",
        "--- PLATFORM HINTS ---",
    ]
    if config.platform_hints.hints:
        for plat, hint in config.platform_hints.hints.items():
            lines.append(f"  [{plat}] {hint}")
    else:
        lines.append("  (none)")
    lines.extend(
        [
            "--- CONTENT THEMES ---",
            f"categories: {', '.join(config.content_themes.categories) or '(none)'}",
            f"recurring_themes: {', '.join(config.content_themes.recurring_themes) or '(none)'}",
            "--- TEXT PREFERENCES ---",
            _rule_block("caption_style", config.text_preferences.caption_style),
            _rule_block("hashtag_style", config.text_preferences.hashtag_style),
            f"banned_phrases: {', '.join(config.text_preferences.banned_phrases) or '(none)'}",
            "--- GENERATION RULES (from brand; folded into assembled governance) ---",
            _rule_block("governance_prompt_template (raw from brand.json)", g.governance_prompt_template),
            _rule_block("design_guidelines", g.design_guidelines),
            _rule_block("layout_spacing_rules", g.layout_spacing_rules),
            _rule_block("cta_button_rules", g.cta_button_rules),
            _rule_block("visual_style_rules", g.visual_style_rules),
            _rule_block("avoid_rules", g.avoid_rules),
            _rule_block("slide_intro_template", g.slide_intro_template),
            _rule_block("slide_user_prompt_suffix", g.slide_user_prompt_suffix),
            "=" * 80,
            "STRUCTURED POST COPY — exact `content` field from the client (TITLE / SUBTITLE / …)",
            "=" * 80,
            structured_post_copy.rstrip() + "\n",
            "=" * 80,
            "ASSEMBLED GOVERNANCE SYSTEM PROMPT — exact text block 1 sent to Gemini",
            "=" * 80,
            governance_system_prompt.rstrip() + "\n",
            "=" * 80,
            "ASSEMBLED SLIDE USER PROMPT — exact text block 2 sent to Gemini",
            "=" * 80,
            slide_user_prompt.rstrip() + "\n",
            "=" * 80,
            "END OF AUDIT",
            "=" * 80,
        ]
    )
    return "\n".join(lines)


def write_generation_audit_file(
    *,
    brand_id: str,
    batch_id: str,
    model_id: str,
    aspect_ratio: str,
    image_size: str,
    slide_count: int,
    logo_description: str,
    config: BrandConfiguration,
    structured_post_copy: str,
    governance_system_prompt: str,
    slide_user_prompt: str,
) -> Optional[Path]:
    """
    Write ``<gallery>/<brand_id>/_audit/generation_<batch>_<utc>.txt``.

    Returns path if written, ``None`` if disabled or write failed.
    """
    if not generation_audit_enabled():
        return None
    bid = validate_brand_id(brand_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit_dir = gallery_dir_for_brand(bid) / "_audit"
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
        path = audit_dir / f"generation_{batch_id}_{stamp}.txt"
        text = build_generation_audit_text(
            brand_id=bid,
            batch_id=batch_id,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            slide_count=slide_count,
            logo_description=logo_description,
            config=config,
            structured_post_copy=structured_post_copy,
            governance_system_prompt=governance_system_prompt,
            slide_user_prompt=slide_user_prompt,
        )
        path.write_text(text, encoding="utf-8")
        return path.resolve()
    except OSError as exc:
        logger.warning("Could not write generation audit file under %s: %s", audit_dir, exc)
        return None
