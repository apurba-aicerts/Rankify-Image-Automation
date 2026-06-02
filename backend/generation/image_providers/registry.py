"""Model catalog, IDs, and pricing hints for image providers."""

from __future__ import annotations

from typing import Any, Literal

ProviderId = Literal["gemini", "openai", "imagen"]

GEMINI_MODEL_IDS: tuple[str, ...] = (
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
)

OPENAI_MODEL_IDS: tuple[str, ...] = (
    "gpt-image-1",
    "gpt-image-1-mini",
    "gpt-image-1.5",
)

IMAGEN_MODEL_IDS: tuple[str, ...] = (
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-001",
)

# Public API model_name values (legacy Gemini IDs + namespaced OpenAI + Imagen IDs).
ALLOWED_IMAGE_MODEL_IDS: tuple[str, ...] = (
    GEMINI_MODEL_IDS
    + IMAGEN_MODEL_IDS
    + tuple(f"openai:{mid}" for mid in OPENAI_MODEL_IDS)
)

GEMINI_IMAGE_PRICE_TABLE_USD: dict[str, Any] = {
    "gemini-2.5-flash-image": 0.039,
    "gemini-3-pro-image-preview": {
        "1K": 0.134,
        "2K": 0.134,
        "4K": 0.24,
    },
}

OPENAI_IMAGE_PRICE_TABLE_USD: dict[str, Any] = {
    "openai:gpt-image-1": {"1K": 0.07, "2K": 0.1, "4K": 0.16},
    "openai:gpt-image-1-mini": 0.04,
    "openai:gpt-image-1.5": {"1K": 0.075, "2K": 0.11, "4K": 0.17},
}

IMAGEN_PRICE_TABLE_USD: dict[str, Any] = {
    # Pricing varies by region/account; keep as hints only.
    "imagen-4.0-fast-generate-001": {"1K": 0.04, "2K": 0.06, "4K": 0.1},
    "imagen-4.0-generate-001": {"1K": 0.06, "2K": 0.09, "4K": 0.14},
    "imagen-4.0-ultra-generate-001": {"1K": 0.1, "2K": 0.14, "4K": 0.22},
}

IMAGE_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "model_name": "gemini-3-pro-image-preview",
        "provider": "gemini",
        "api_model": "gemini-3-pro-image-preview",
        "supports_image_size": True,
        "supports_generate": True,
        "supports_edit": True,
        "label": "Gemini 3 Pro Image",
    },
    {
        "model_name": "gemini-2.5-flash-image",
        "provider": "gemini",
        "api_model": "gemini-2.5-flash-image",
        "supports_image_size": False,
        "supports_generate": True,
        "supports_edit": True,
        "label": "Gemini 2.5 Flash Image",
    },
    {
        "model_name": "openai:gpt-image-2",
        "provider": "openai",
        "api_model": "gpt-image-2",
        "supports_image_size": True,
        "supports_generate": True,
        "supports_edit": True,
        "label": "OpenAI GPT Image 2",
    },
    {
        "model_name": "openai:gpt-image-1",
        "provider": "openai",
        "api_model": "gpt-image-1",
        "supports_image_size": True,
        "supports_generate": True,
        "supports_edit": True,
        "label": "OpenAI GPT Image 1",
    },
    {
        "model_name": "openai:gpt-image-1-mini",
        "provider": "openai",
        "api_model": "gpt-image-1-mini",
        "supports_image_size": False,
        "supports_generate": True,
        "supports_edit": True,
        "label": "OpenAI GPT Image 1 Mini",
    },
    {
        "model_name": "openai:gpt-image-1.5",
        "provider": "openai",
        "api_model": "gpt-image-1.5",
        "supports_image_size": True,
        "supports_generate": True,
        "supports_edit": True,
        "label": "OpenAI GPT Image 1.5",
    },
    {
        "model_name": "imagen-4.0-fast-generate-001",
        "provider": "imagen",
        "api_model": "imagen-4.0-fast-generate-001",
        "supports_image_size": False,
        "supports_generate": True,
        "supports_edit": False,
        "label": "Imagen 4 Fast",
    },
    {
        "model_name": "imagen-4.0-generate-001",
        "provider": "imagen",
        "api_model": "imagen-4.0-generate-001",
        "supports_image_size": False,
        "supports_generate": True,
        "supports_edit": False,
        "label": "Imagen 4",
    },
    {
        "model_name": "imagen-4.0-ultra-generate-001",
        "provider": "imagen",
        "api_model": "imagen-4.0-ultra-generate-001",
        "supports_image_size": False,
        "supports_generate": True,
        "supports_edit": False,
        "label": "Imagen 4 Ultra",
    },
]


def normalize_model_id(model_id: str) -> tuple[ProviderId, str]:
    """
  Return ``(provider, api_model_id)`` for a client-facing ``model_name``.

  Accepts legacy Gemini IDs and ``openai:<model>`` namespaced IDs.
    """
    mid = (model_id or "").strip()
    if mid.startswith("openai:"):
        api = mid[7:].strip()
        if api not in OPENAI_MODEL_IDS:
            raise ValueError(f"Unknown OpenAI image model: {api!r}")
        return "openai", api
    if mid.startswith("imagen:"):
        api = mid[6:].strip()
        if api not in IMAGEN_MODEL_IDS:
            raise ValueError(f"Unknown Imagen model: {api!r}")
        return "imagen", api
    if mid.startswith("gemini:"):
        api = mid[7:].strip()
        if api not in GEMINI_MODEL_IDS:
            raise ValueError(f"Unknown Gemini image model: {api!r}")
        return "gemini", api
    if mid in GEMINI_MODEL_IDS:
        return "gemini", mid
    if mid in IMAGEN_MODEL_IDS:
        return "imagen", mid
    if mid in OPENAI_MODEL_IDS:
        return "openai", mid
    raise ValueError(f"Unknown image model: {mid!r}")


def provider_for_model(model_id: str) -> ProviderId:
    return normalize_model_id(model_id)[0]


def catalog_entry(model_id: str) -> dict[str, Any] | None:
    for row in IMAGE_MODEL_CATALOG:
        if row["model_name"] == model_id:
            return row
    return None


def model_supports_image_size(model_id: str) -> bool:
    row = catalog_entry(model_id)
    return bool(row and row.get("supports_image_size"))


def requires_google_api_key(model_id: str) -> bool:
    return provider_for_model(model_id) in ("gemini", "imagen")


def requires_openai_api_key(model_id: str) -> bool:
    return provider_for_model(model_id) == "openai"


def estimate_price_usd(model_id: str, image_size: str) -> float:
    if model_id in GEMINI_IMAGE_PRICE_TABLE_USD:
        price = GEMINI_IMAGE_PRICE_TABLE_USD[model_id]
        if isinstance(price, dict):
            return float(price.get(image_size, 0.134))
        return float(price)
    price = OPENAI_IMAGE_PRICE_TABLE_USD.get(model_id)
    if isinstance(price, dict):
        return float(price.get(image_size, 0.12))
    if isinstance(price, (int, float)):
        return float(price)
    price = IMAGEN_PRICE_TABLE_USD.get(model_id)
    if isinstance(price, dict):
        return float(price.get(image_size, 0.06))
    return 0.1


def models_list_payload() -> list[dict[str, Any]]:
    """Shape for ``GET /api/models``."""
    out: list[dict[str, Any]] = []
    for row in IMAGE_MODEL_CATALOG:
        model_name = row["model_name"]
        item: dict[str, Any] = {
            "model_name": model_name,
            "provider": row["provider"],
            "label": row["label"],
            "supports_image_size": row["supports_image_size"],
            "supports_generate": row["supports_generate"],
            "supports_edit": row["supports_edit"],
        }
        gemini_price = GEMINI_IMAGE_PRICE_TABLE_USD.get(model_name)
        openai_price = OPENAI_IMAGE_PRICE_TABLE_USD.get(model_name)
        imagen_price = IMAGEN_PRICE_TABLE_USD.get(model_name)
        price = gemini_price if gemini_price is not None else openai_price
        if price is None:
            price = imagen_price
        if isinstance(price, dict):
            item["pricing"] = price
        elif price is not None:
            item["price_per_image_usd"] = price
        out.append(item)
    return out
