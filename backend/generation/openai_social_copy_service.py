"""OpenAI caption + hashtag generation for a brand and optional gallery image."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

from brands.schemas import BrandConfiguration

logger = logging.getLogger(__name__)

SOCIAL_COPY_MODEL = "gpt-4o-mini"


class OpenAISocialCopyParsed(BaseModel):
    """Structured output from the chat model."""

    caption: str = Field(
        ...,
        description="Single social post caption only; no hashtags in this field.",
        max_length=2200,
    )
    hashtags: list[str] = Field(
        ...,
        min_length=3,
        max_length=14,
        description="5–12 concise tags; each may include # or plain word.",
    )


def _mime_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _normalize_hashtag_line(tags: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        body = (raw or "").strip().lstrip("#").strip().replace(" ", "")
        if not body:
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append("#" + body)
        if len(out) >= 12:
            break
    if len(out) < 3:
        for filler in ("socialfirst", "brandstory", "creators"):
            t = "#" + filler
            if t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
            if len(out) >= 3:
                break
    return " ".join(out)


def _brand_context_block(cfg: BrandConfiguration) -> str:
    banned = ", ".join(cfg.text_preferences.banned_phrases[:24]) if cfg.text_preferences.banned_phrases else "(none listed)"
    tones = ", ".join(cfg.voice.tone_keywords[:12]) if cfg.voice.tone_keywords else ""
    return (
        f"Brand display name: {cfg.display_name}\n"
        f"Tagline: {cfg.tagline}\n"
        f"Voice tone keywords: {tones}\n"
        f"Writing style: {cfg.voice.writing_style}\n"
        f"Target audience: {cfg.voice.target_audience}\n"
        f"Caption style prefs: {cfg.text_preferences.caption_style}\n"
        f"Hashtag style prefs: {cfg.text_preferences.hashtag_style}\n"
        f"Banned phrases (do not use): {banned}\n"
    )


def _system_prompt() -> str:
    return (
        "You write social post copy for marketing teams. "
        "Follow the brand context strictly: tone, audience, caption/hashtag prefs, and banned phrases. "
        "The user supplies structured slide/post copy that was used to generate the visual—align the caption with that story. "
        "If an image is attached, describe what you see only to make the caption and tags accurate; do not invent claims that contradict the image. "
        "Output valid structured fields only: one caption (no hashtags inside it) and a list of 5–12 hashtags. "
        "Hashtags should be short, camel-free single tokens suitable for LinkedIn/Instagram (mixed case OK). "
        "Prefer a mix of brand-adjacent and topic tags; avoid empty or duplicate tags."
    )


def generate_social_copy_openai(
    *,
    cfg: BrandConfiguration,
    structured_post_copy: str,
    image_path: Optional[Path],
    openai_api_key: str,
    model_name: str = SOCIAL_COPY_MODEL,
) -> tuple[str, str, str]:
    """
    Return ``(caption, hashtags_space_separated, model_used)``.
    """
    client = OpenAI(api_key=openai_api_key)
    brand_block = _brand_context_block(cfg)
    text_part = (
        f"{brand_block}\n"
        "--- Structured post / slide copy (context for the visual) ---\n"
        f"{structured_post_copy.strip()}\n"
    )

    user_content: list[dict] = [{"type": "text", "text": text_part}]
    if image_path is not None and image_path.is_file():
        mime = _mime_for_path(image_path)
        if mime == "application/octet-stream":
            raise HTTPException(status_code=400, detail="Unsupported image type for vision.")
        b64 = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )

    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": user_content},
    ]

    try:
        completion = client.chat.completions.parse(
            model=model_name,
            messages=messages,
            response_format=OpenAISocialCopyParsed,
        )
    except Exception as exc:
        logger.warning("OpenAI social-copy parse failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI social copy failed: {exc}",
        ) from exc

    msg = completion.choices[0].message
    if getattr(msg, "refusal", None):
        raise HTTPException(status_code=422, detail=str(msg.refusal))
    if msg.parsed is None:
        raise HTTPException(status_code=422, detail="Model returned no structured social copy.")

    cap = (msg.parsed.caption or "").strip()
    if not cap:
        raise HTTPException(status_code=422, detail="Empty caption from model.")
    tags_line = _normalize_hashtag_line(msg.parsed.hashtags)
    used = getattr(completion, "model", None) or model_name
    return cap, tags_line, used
