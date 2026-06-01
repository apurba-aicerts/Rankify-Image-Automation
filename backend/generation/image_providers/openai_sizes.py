"""Map Rankify aspect_ratio + image_size to OpenAI Images API ``size`` (WxH)."""

from __future__ import annotations

# gpt-image-1, gpt-image-1-mini: API only allows these sizes (2K/4K tiers map to same).
_OPENAI_SIZE_STANDARD: dict[str, str] = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "4:5": "1024x1536",
    "5:4": "1536x1024",
    "21:9": "1536x1024",
}

# gpt-image-2: larger resolutions allowed (multiples of 16, ratio ≤ 3:1).
_OPENAI_SIZE_GPT_IMAGE_2: dict[tuple[str, str], str] = {
    ("1:1", "1K"): "1024x1024",
    ("1:1", "2K"): "2048x2048",
    ("1:1", "4K"): "2048x2048",
    ("16:9", "1K"): "1536x1024",
    ("16:9", "2K"): "2048x1152",
    ("16:9", "4K"): "3840x2160",
    ("9:16", "1K"): "1024x1536",
    ("9:16", "2K"): "1024x1536",
    ("9:16", "4K"): "2160x3840",
    ("4:3", "1K"): "1536x1152",
    ("4:3", "2K"): "2048x1536",
    ("4:3", "4K"): "2048x1536",
    ("3:4", "1K"): "1152x1536",
    ("3:4", "2K"): "1536x2048",
    ("3:4", "4K"): "1536x2048",
    ("3:2", "1K"): "1536x1024",
    ("3:2", "2K"): "2048x1365",
    ("3:2", "4K"): "2048x1365",
    ("2:3", "1K"): "1024x1536",
    ("2:3", "2K"): "1365x2048",
    ("2:3", "4K"): "1365x2048",
    ("4:5", "1K"): "1024x1280",
    ("4:5", "2K"): "1638x2048",
    ("4:5", "4K"): "1638x2048",
    ("5:4", "1K"): "1280x1024",
    ("5:4", "2K"): "2048x1638",
    ("5:4", "4K"): "2048x1638",
    ("21:9", "1K"): "1792x768",
    ("21:9", "2K"): "2048x878",
    ("21:9", "4K"): "3840x1646",
}

# Only gpt-image-2 accepts arbitrary high-res sizes from _OPENAI_SIZE_GPT_IMAGE_2.
_LARGE_SIZE_MODELS = frozenset({"gpt-image-2"})


def _uses_standard_openai_sizes(api_model: str) -> bool:
    return api_model not in _LARGE_SIZE_MODELS


def openai_size_for_aspect(aspect_ratio: str, image_size: str, *, api_model: str = "gpt-image-2") -> str:
    """Return OpenAI Images API ``size`` for aspect, tier, and model (generate / reference flows)."""
    ratio = (aspect_ratio or "1:1").strip()
    tier = image_size if image_size in ("1K", "2K", "4K") else "2K"

    if _uses_standard_openai_sizes(api_model):
        return _OPENAI_SIZE_STANDARD.get(ratio, "1024x1024")

    key = (ratio, tier)
    if key in _OPENAI_SIZE_GPT_IMAGE_2:
        return _OPENAI_SIZE_GPT_IMAGE_2[key]
    return _OPENAI_SIZE_GPT_IMAGE_2.get(("1:1", tier), "1024x1024")


def openai_size_for_gallery_edit(
    aspect_ratio: str,
    image_size: str,
    *,
    api_model: str,
) -> str:
    """
    Size for ``images.edit`` on an existing gallery asset.

    Standard GPT Image models support ``auto`` so output tracks the source image.
    ``gpt-image-2`` uses explicit dimensions from aspect + tier.
    """
    if _uses_standard_openai_sizes(api_model):
        return "auto"
    return openai_size_for_aspect(aspect_ratio, image_size, api_model=api_model)
