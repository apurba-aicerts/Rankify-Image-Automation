"""Google Imagen 4 provider using google-genai SDK (batch via number_of_images)."""

from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

from generation.image_providers.exceptions import ImageProviderNoOutput

logger = logging.getLogger(__name__)


def _aspect_to_imagen(aspect_ratio: str) -> str:
    # Imagen expects "1:1" style strings; pass through with safe default.
    r = (aspect_ratio or "1:1").strip()
    return r if ":" in r else "1:1"


def generate_images_bytes(
    *,
    google_api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    number_of_images: int,
) -> list[bytes]:
    """
    Return a list of JPEG/PNG bytes for Imagen 4 generate_images.

    Imagen 4 supports up to 4 outputs per call.
    """
    if number_of_images < 1:
        raise ValueError("number_of_images must be >= 1")
    if number_of_images > 4:
        raise ValueError("Imagen 4 supports up to 4 images per call")
    if not google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured on the server.")

    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "google-genai is not installed. Add it to backend/requirements.txt to use Imagen."
        ) from exc

    client = genai.Client(api_key=google_api_key)
    logger.info("Imagen generate_images model=%s n=%s aspect=%s", model, number_of_images, aspect_ratio)

    rsp = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=number_of_images,
            aspect_ratio=_aspect_to_imagen(aspect_ratio),
        ),
    )

    out: list[bytes] = []
    for gi in getattr(rsp, "generated_images", []) or []:
        img = getattr(gi, "image", None)
        if not img:
            continue
        b = getattr(img, "image_bytes", None)
        if b:
            out.append(b)

    if not out:
        raise ImageProviderNoOutput("Imagen returned no image bytes.", provider="imagen")
    return out


def ensure_png_bytes(image_bytes: bytes) -> bytes:
    """Convert Imagen bytes to PNG bytes for consistent storage."""
    im = Image.open(BytesIO(image_bytes))
    out = BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()

