"""OpenAI-backed draft of :class:`~brands.schemas.BrandCreatePayload` from unstructured notes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from openai import OpenAI

from brands.openai_brand_draft import OpenAIBrandCreateDraft, openai_draft_to_create_payload
from brands.schemas import BrandCreatePayload, resolve_brand_id

logger = logging.getLogger(__name__)

ALLOWED_OPENAI_DRAFT_MODELS: tuple[str, ...] = (
    "gpt-4o-2024-08-06",
    "gpt-4o-mini",
    "gpt-4o",
)

SYSTEM_PROMPT = """You are a brand configuration assistant for a multi-brand creative automation product.

Your job: infer a complete brand profile from the user's unstructured notes (guidelines, marketing copy, design notes, etc.).

Output rules (structured response — no markdown, no commentary outside the schema):
- platform_hints must use the field ``entries``: an array of objects like {"platform_id": "linkedin", "hint": "..."}. Use lowercase platform_id values (linkedin, instagram, x, etc.). Use an empty array if you have no per-platform hints.
- content_themes must be an object with exactly two array fields: ``categories`` and ``recurring_themes``. Never return content_themes as a bare array.
- generation.governance_prompt_template: strong brand constitution (>= 20 characters) for an image generation system prompt. Mention logo placement, palette, typography, tone when inferable.
- generation.design_guidelines: concise visual direction.
- Prefer concrete hex colors, font names, and platform ids when the notes support them; otherwise use conservative professional defaults.
- If information is missing, infer cautiously from context only.
"""


def _messages(brand_slug: str, user_blob: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"The brand_id in your response must be exactly:\n{brand_slug}\n\n"
                "--- Brand materials (unstructured) ---\n"
                f"{user_blob.strip()}"
            ),
        },
    ]


def _draft_with_parse(client: OpenAI, model: str, messages: list[dict[str, str]]) -> BrandCreatePayload:
    completion = client.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=OpenAIBrandCreateDraft,
    )
    msg = completion.choices[0].message
    if getattr(msg, "refusal", None):
        raise HTTPException(status_code=422, detail=str(msg.refusal))
    if msg.parsed is None:
        raise HTTPException(status_code=422, detail="Model returned no structured draft (empty parse).")
    return openai_draft_to_create_payload(msg.parsed)


def _draft_with_json_object(client: OpenAI, model: str, messages: list[dict[str, str]]) -> BrandCreatePayload:
    schema_reminder = (
        "Respond with one JSON object only. Required shapes:\n"
        '- "content_themes": { "categories": string[], "recurring_themes": string[] } — never a bare array.\n'
        '- "platform_hints": { "entries": [ { "platform_id": string, "hint": string } ] }.\n'
        '- Include all top-level keys for a Rankify brand profile (colors, typography, voice, '
        "social_defaults, text_preferences, generation, logo_asset_filename, etc.)."
    )
    completion = client.chat.completions.create(
        model=model,
        messages=list(messages) + [{"role": "user", "content": schema_reminder}],
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise HTTPException(status_code=502, detail="OpenAI returned an empty message.")
    try:
        draft = OpenAIBrandCreateDraft.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Model JSON did not match the expected draft schema: {exc}",
        ) from exc
    return openai_draft_to_create_payload(draft)


def draft_brand_create_payload_from_materials(
    *,
    brand_materials: str,
    brand_id: Optional[str],
    model_name: str,
    openai_api_key: str,
) -> BrandCreatePayload:
    """
    Call OpenAI structured outputs (with json_object fallback) and return a validated
    :class:`BrandCreatePayload`. ``brand_id`` may be ``None`` to assign a new UUID slug.
    """
    if model_name not in ALLOWED_OPENAI_DRAFT_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model_name. Choose from {list(ALLOWED_OPENAI_DRAFT_MODELS)}",
        )

    brand_slug = resolve_brand_id(brand_id)
    messages = _messages(brand_slug, brand_materials)
    client = OpenAI(api_key=openai_api_key)

    try:
        payload = _draft_with_parse(client, model_name, messages)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("OpenAI parse() failed, using json_object fallback: %s", exc)
        try:
            payload = _draft_with_json_object(client, model_name, messages)
        except HTTPException:
            raise
        except Exception as exc2:
            logger.exception("OpenAI brand draft failed after fallback")
            raise HTTPException(
                status_code=502,
                detail=f"OpenAI brand draft failed: {exc2}",
            ) from exc2

    return payload.model_copy(update={"brand_id": brand_slug})
