"""
Assemble TITLE / SUBTITLE / BODY / CTA structured post copy for slide generation.

Canonical logic for the Creative Studio lives here so prompts stay consistent regardless
of which client calls ``POST /api/generate``. Legacy clients may still send raw ``content``.
"""

from __future__ import annotations

PLATFORM_LABELS: dict[str, str] = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "x": "X",
    "facebook": "Facebook",
    "threads": "Threads",
    "tiktok": "TikTok",
    "youtube": "YouTube",
}

GOAL_LABELS: dict[str, str] = {
    "brand_awareness": "Brand awareness",
    "webinar": "Webinar promotion",
    "product_launch": "Product launch",
    "hiring": "Hiring",
    "event_countdown": "Event countdown",
    "educational_carousel": "Educational carousel",
    "founder": "Founder branding",
    "blog": "Blog promotion",
    "cert_launch": "AI certification launch",
    "student_story": "Student success story",
}

CTA_BY_GOAL: dict[str, str] = {
    "webinar": "Save your seat",
    "hiring": "View open roles",
    "product_launch": "Explore the launch",
    "event_countdown": "Add to calendar",
    "cert_launch": "Get certified",
    "student_story": "Read the story",
    "blog": "Read the article",
    "founder": "Follow the journey",
    "educational_carousel": "Start learning",
    "brand_awareness": "Learn more",
}


def goal_label(goal_id: str) -> str:
    return GOAL_LABELS.get(goal_id, "Campaign")


def humanize_platform_list(platform_ids: list[str]) -> str:
    ids = [str(p).strip().lower() for p in (platform_ids or []) if str(p).strip()]
    if not ids:
        return "your social channels"
    labels = [PLATFORM_LABELS.get(i, i) for i in ids]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _build_image_title(display_name: str, campaign_goal_id: str) -> str:
    name = (display_name or "Brand").strip()
    gid = (campaign_goal_id or "").strip()
    if gid == "hiring":
        return f"We're hiring — {name}"
    if gid == "webinar":
        return f"{name} · Join our live session"
    if gid == "cert_launch":
        return f"{name} · New certification"
    if gid == "product_launch":
        return f"{name} · Introducing something new"
    if gid == "event_countdown":
        return f"{name} · Save the date"
    if gid == "student_story":
        return f"{name} · Success story"
    if gid == "blog":
        return f"{name} · New read"
    if gid == "founder":
        return f"{name} · From our founder"
    if gid == "educational_carousel":
        return f"{name} · Learn with us"
    if gid == "brand_awareness":
        return name
    return f"{name} — {goal_label(gid)}"


def _build_image_subtitle(
    platforms: list[str],
    campaign_goal_id: str,
    voice_tone_label: str,
) -> str:
    surfaces = humanize_platform_list(platforms)
    voice = (voice_tone_label or "Professional").strip() or "Professional"
    ids_lower = [str(p).strip().lower() for p in (platforms or []) if str(p).strip()]
    has_li = "linkedin" in ids_lower
    has_ig = "instagram" in ids_lower
    li_ig = has_li and has_ig

    gid = (campaign_goal_id or "").strip()
    role = "Campaign"
    if gid == "hiring":
        role = "Hiring announcement"
    elif gid == "webinar":
        role = "Webinar promo"
    elif gid == "product_launch":
        role = "Product launch"
    elif gid == "cert_launch":
        role = "Certification launch"

    if li_ig:
        return (
            f"{role} for {surfaces}: one square hero that reads as trustworthy and editorial "
            "for LinkedIn in-feed, and stays bold, high-contrast, and legible at small size for "
            f"Instagram (feed + profile grid). Voice: {voice}. No channel UI chrome—just the creative."
        )
    if has_li:
        return (
            f"{role} for {surfaces}: professional B2B in-feed legibility, clear hierarchy, credible tone. "
            f"Voice: {voice}."
        )
    if has_ig:
        return (
            f"{role} for {surfaces}: thumb-stopping contrast, simple headline block, square-safe composition. "
            f"Voice: {voice}."
        )
    return (
        f"{role} for {surfaces}. Voice: {voice}. Optimize layout and type for those feeds."
    )


def infer_cta(goal_id: str) -> str:
    return CTA_BY_GOAL.get(goal_id, "Learn more")


def build_structured_campaign_copy(
    *,
    display_name: str,
    campaign_goal_id: str,
    platforms: list[str],
    creativity_tone_label: str,
    voice_tone_label: str,
    intent: str,
) -> str:
    """Return the same block format previously built in ``frontend/.../campaignAssembler.js``."""
    goal = goal_label(campaign_goal_id)
    plat_human = humanize_platform_list(platforms)
    voice = (voice_tone_label or "").strip() or "Professional"
    title = _build_image_title(display_name, campaign_goal_id)
    subtitle = _build_image_subtitle(platforms, campaign_goal_id, voice)
    intent_clean = (intent or "").strip() or "(Describe what success looks like for this campaign.)"

    body_parts = [
        f"CAMPAIGN GOAL: {goal}",
        f"PRIMARY CHANNELS: {plat_human}",
        f"CREATIVE VOICE (copy tone): {voice}",
        f"AI CREATIVITY: {creativity_tone_label}",
        "",
        "CONTENT INTENT:",
        intent_clean,
        "",
        "VISUAL OUTPUT: Produce one strong hero image for this campaign—clear hierarchy, on-brand, scroll-stopping.",
        "",
        "VISUAL MANDATE: Respect brand governance, palette, typography, and logo placement from the system prompt.",
    ]
    cta = infer_cta(campaign_goal_id)
    return "\n\n".join(
        [
            f"TITLE:\n{title}",
            f"SUBTITLE:\n{subtitle}",
            f"BODY:\n" + "\n".join(body_parts),
            f"CTA BUTTON:\n{cta}",
        ]
    )
