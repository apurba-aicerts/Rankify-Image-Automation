"""
Placeholder for caption / hashtag / edit pipelines.

These will call a text modality model using :class:`~brands.schemas.BrandConfiguration`
(``voice``, ``text_preferences``, ``platform_hints``) without changing storage layout here.
"""

from __future__ import annotations

import logging

from brands.schemas import BrandConfiguration

logger = logging.getLogger(__name__)


def caption_pipeline_status() -> dict:
    logger.debug("Caption pipeline status queried (not implemented)")
    return {
        "implemented": False,
        "detail": "POST /api/brands/{brand_id}/text/captions will use BrandConfiguration.text_preferences.",
    }


def hashtag_pipeline_status() -> dict:
    logger.debug("Hashtag pipeline status queried (not implemented)")
    return {
        "implemented": False,
        "detail": "POST /api/brands/{brand_id}/text/hashtags will use BrandConfiguration.text_preferences.",
    }


def build_caption_prompt_stub(cfg: BrandConfiguration, platform: str, topic: str) -> str:
    """Return a deterministic prompt string for future LLM caption generation."""
    logger.debug("build_caption_prompt_stub platform=%s topic=%s", platform, topic[:80] if topic else "")
    prefs = cfg.text_preferences.caption_style or "Match brand voice."
    voice = ", ".join(cfg.voice.tone_keywords) or cfg.voice.writing_style or "on-brand"
    return (
        f"Platform: {platform}\nTopic: {topic}\n"
        f"Audience: {cfg.voice.target_audience}\nStyle notes: {prefs}\nVoice: {voice}"
    )
