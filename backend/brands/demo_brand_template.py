"""
Packaged :class:`~brands.schemas.BrandConfiguration` for the **AI CERTs** demo tenant.

Used by ``POST /api/brands/bootstrap-demo`` and optional local tools (e.g. Streamlit lab).
"""

from __future__ import annotations

import logging

from brands.demo_ai_certs_governance import DEMO_AI_CERTS_GOVERNANCE_PROMPT
from brands.schemas import (
    BrandColors,
    BrandConfiguration,
    BrandContentThemes,
    BrandGenerationRules,
    BrandSocialDefaults,
    BrandTextPreferences,
    BrandTypography,
    BrandVoice,
    PlatformSpecificHints,
)

_DEFAULT_SLIDE_SUFFIX = """
DESIGN REQUIREMENTS:
- Place brand logo at the top-left
- Use primary gold highlights for keywords where appropriate
- Dark navy / midnight blue gradient background
- Modern tech visuals, glowing UI elements
- Clean text hierarchy
"""

logger = logging.getLogger(__name__)


def build_demo_ai_certs_brand(brand_id: str = "demo-ai-certs") -> BrandConfiguration:
    """Return a ready-to-persist configuration for the packaged AI CERTs demo."""
    logger.info("Building demo AI CERTs brand template brand_id=%s", brand_id)
    return BrandConfiguration(
        brand_id=brand_id,
        display_name="AI CERTs",
        tagline="Become Certified. Become AI-Ready.",
        legal_suffix="AI CERTs®",
        colors=BrandColors(
            primary=["#CFA935", "#F4F4F4"],
            secondary=["#E4E4E4", "#4D5060", "#098A7D", "#072557", "#1A1A2E", "#0056B3", "#176C90"],
            usage_rules="Gold (#CFA935) for highlights and CTAs; dark navy dominates modern layouts.",
        ),
        typography=BrandTypography(
            primary_font="Open Sans",
            headline_font="Montserrat Bold / ExtraBold",
            body_font="Poppins Regular / SemiBold",
            notes="Maintain clear hierarchy; carousel canvas 1080x1080.",
        ),
        voice=BrandVoice(
            tone_keywords=["Professional", "Modern", "Educational", "Trust-driven"],
            writing_style="Short, high-impact statements; industry-expert voice.",
            target_audience="Professionals upskilling with recognized certifications.",
        ),
        social_defaults=BrandSocialDefaults(
            preferred_platforms=["linkedin", "instagram"],
            default_aspect_ratio="1:1",
            default_image_size="2K",
        ),
        platform_hints=PlatformSpecificHints(
            hints={
                "linkedin": "Professional layouts, authority, educational structure.",
                "instagram": "Bold visuals, scroll-stopping energy.",
                "x": "Concise hooks and strong readability.",
            },
        ),
        content_themes=BrandContentThemes(
            categories=["Certification", "Career growth", "AI readiness"],
            recurring_themes=["Future-proof", "Upskill", "Toolkit"],
        ),
        text_preferences=BrandTextPreferences(
            hashtag_style="Mix trending, niche, and campaign tags; align with platform norms.",
            caption_style="Platform-aware length; clear CTA; match voice.tone_keywords.",
            banned_phrases=[],
        ),
        generation=BrandGenerationRules(
            governance_prompt_template=DEMO_AI_CERTS_GOVERNANCE_PROMPT.strip(),
            design_guidelines="Logo top-left; mandatory CTA; no invented brand marks.",
            slide_intro_template="Create a professional 1080x1080 LinkedIn carousel-style social media post.\n\n",
            slide_user_prompt_suffix=_DEFAULT_SLIDE_SUFFIX.strip(),
        ),
        logo_asset_filename="logo.png",
    )
