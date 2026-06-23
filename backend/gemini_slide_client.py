"""
HTTP client for Google Gemini **slide image** generation (``generateContent`` with IMAGE modality).

Encodes governance + slide prompts and a reference logo, calls the Generative Language API,
and writes the returned raster to a file path.
"""

from __future__ import annotations

import logging
import base64
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)


class GeminiNoImageInResponse(Exception):
    """HTTP 200 from Gemini but no raster in candidates (IMAGE_OTHER, safety, empty parts, etc.)."""

    __slots__ = ("finish_reason",)

    def __init__(self, message: str, *, finish_reason: str | None = None) -> None:
        super().__init__(message)
        self.finish_reason = finish_reason


class GeminiBrandImageClient:
    """
    Calls Gemini image-capable models to render one branded slide per request.

    Parameters
    ----------
    google_api_key:
        Value of ``GOOGLE_API_KEY``; sent as a query parameter on the REST URL.
    """

    def __init__(self, google_api_key: str) -> None:
        self._google_api_key = google_api_key

    def _encode_pil_logo_as_gemini_inline_image(self, logo: Image.Image) -> dict:
        """Serialize a Pillow image to the ``inlineData`` part shape expected by Gemini."""
        buffer = BytesIO()
        logo.save(buffer, format="PNG")
        return {
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(buffer.getvalue()).decode("utf-8"),
            }
        }

    def generate_brand_slide_to_file(
        self,
        *,
        brand_governance_prompt: str,
        slide_user_prompt: str,
        logo: Image.Image,
        style_reference: Optional[Image.Image] = None,
        output_file_path: str,
        model_id: str = "gemini-3-pro-image-preview",
        aspect_ratio: str = "1:1",
        image_size: Optional[str] = "2K",
    ) -> str:
        """
        Request one image from Gemini and save it to ``output_file_path``.

        ``image_size`` is only sent for ``gemini-3-pro-image-preview``; pass ``None`` for Flash.

        Returns
        -------
        str
            The same path passed in ``output_file_path`` after a successful write.
        """
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model_id}:generateContent"
            f"?key={self._google_api_key}"
        )

        parts: list[dict] = [
            {"text": brand_governance_prompt},
            {"text": slide_user_prompt},
            {"text": "BRAND LOGO (use this exact logo in the final design):"},
            self._encode_pil_logo_as_gemini_inline_image(logo),
        ]
        if style_reference is not None:
            parts.extend(
                [
                    {
                        "text": (
                            "STYLE / LAYOUT REFERENCE (inspiration only; "
                            "see REFERENCE RULES in the prompt above):"
                        )
                    },
                    self._encode_pil_logo_as_gemini_inline_image(style_reference),
                ]
            )

        contents = [{"parts": parts}]

        image_config: dict = {"aspectRatio": aspect_ratio}
        if model_id == "gemini-3-pro-image-preview" and image_size:
            image_config["image_size"] = image_size

        payload = {
            "contents": contents,
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": image_config,
            },
        }

        logger.info(
            "Gemini generateContent request model=%s aspect_ratio=%s image_size=%s",
            model_id,
            aspect_ratio,
            image_size if model_id == "gemini-3-pro-image-preview" else None,
        )
        response = requests.post(url, json=payload, timeout=120)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body_preview = (response.text or "")[:500]
            logger.error(
                "Gemini API HTTP error status=%s model=%s body_preview=%r",
                response.status_code,
                model_id,
                body_preview,
            )
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {body_preview}") from exc
        data = response.json()

        try:
            image_b64 = self._extract_first_inline_image_b64(data)
        except GeminiNoImageInResponse:
            logger.warning("Gemini slide response contained no image payload model=%s", model_id)
            raise
        except RuntimeError as exc:
            logger.error(
                "Gemini response missing image payload keys=%s",
                list(data.keys()) if isinstance(data, dict) else type(data),
            )
            raise RuntimeError(f"No image returned:\n{data}") from exc

        image = Image.open(BytesIO(base64.b64decode(image_b64)))
        image.save(output_file_path)
        logger.info("Gemini image saved path=%s model=%s", output_file_path, model_id)
        return output_file_path

    @staticmethod
    def _candidate_image_failure_message(candidate: dict) -> str:
        """Human-readable explanation when a candidate has no image parts."""
        finish_reason = candidate.get("finishReason")
        finish_message = (candidate.get("finishMessage") or "").strip()
        if finish_message:
            return finish_message
        if finish_reason:
            return (
                f"The model returned no image (finishReason={finish_reason!r}). "
                "Try a simpler or more specific edit, or retry."
            )
        return "The model returned no image. Try rephrasing the request or retry."

    @staticmethod
    def _extract_first_inline_image_b64(data: dict) -> str:
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected Gemini response type: {type(data)}")

        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            prompt_fb = data.get("promptFeedback") or data.get("prompt_feedback")
            raise GeminiNoImageInResponse(
                f"No candidates in Gemini response. promptFeedback={prompt_fb!r}",
                finish_reason=None,
            )

        cand0 = candidates[0]
        if not isinstance(cand0, dict):
            raise GeminiNoImageInResponse("Invalid candidate shape in Gemini response.", finish_reason=None)

        content = cand0.get("content")
        if not isinstance(content, dict):
            raise GeminiNoImageInResponse(
                GeminiBrandImageClient._candidate_image_failure_message(cand0),
                finish_reason=cand0.get("finishReason") if isinstance(cand0.get("finishReason"), str) else None,
            )

        parts = content.get("parts")
        if not isinstance(parts, list):
            raise GeminiNoImageInResponse(
                GeminiBrandImageClient._candidate_image_failure_message(cand0),
                finish_reason=cand0.get("finishReason") if isinstance(cand0.get("finishReason"), str) else None,
            )

        for part in parts:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData")
            if isinstance(inline, dict) and inline.get("data"):
                return str(inline["data"])

        raise GeminiNoImageInResponse(
            GeminiBrandImageClient._candidate_image_failure_message(cand0)
            + " (response had no inline image data in parts.)",
            finish_reason=cand0.get("finishReason") if isinstance(cand0.get("finishReason"), str) else None,
        )

    def edit_image_to_file(
        self,
        *,
        edit_system_prompt: str,
        edit_user_prompt: str,
        base_image: Image.Image,
        output_file_path: str,
        model_id: str = "gemini-2.5-flash-image",
        aspect_ratio: str = "1:1",
        image_size: Optional[str] = "2K",
    ) -> str:
        """
        Image-to-image refinement: instruction text + source raster, one edited image out.

        ``image_size`` is only sent for ``gemini-3-pro-image-preview``; pass ``None`` for Flash.
        """
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model_id}:generateContent"
            f"?key={self._google_api_key}"
        )

        buf = BytesIO()
        # RGB avoids palette issues when re-saving as PNG after decode.
        base_image.convert("RGB").save(buf, format="PNG")
        inline = {
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(buf.getvalue()).decode("utf-8"),
            }
        }

        contents = [
            {
                "parts": [
                    {"text": edit_system_prompt},
                    {"text": edit_user_prompt},
                    inline,
                ]
            }
        ]

        image_config: dict = {"aspectRatio": aspect_ratio}
        if model_id == "gemini-3-pro-image-preview" and image_size:
            image_config["image_size"] = image_size

        payload = {
            "contents": contents,
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": image_config,
            },
        }

        logger.info(
            "Gemini edit generateContent model=%s aspect_ratio=%s image_size=%s",
            model_id,
            aspect_ratio,
            image_size if model_id == "gemini-3-pro-image-preview" else None,
        )
        response = requests.post(url, json=payload, timeout=120)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body_preview = (response.text or "")[:500]
            logger.error(
                "Gemini edit HTTP error status=%s model=%s body_preview=%r",
                response.status_code,
                model_id,
                body_preview,
            )
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {body_preview}") from exc
        data = response.json()

        try:
            image_b64 = self._extract_first_inline_image_b64(data)
        except GeminiNoImageInResponse as exc:
            logger.warning(
                "Gemini edit returned no image model=%s finish_reason=%s detail=%s",
                model_id,
                getattr(exc, "finish_reason", None),
                exc,
            )
            raise

        image = Image.open(BytesIO(base64.b64decode(image_b64)))
        image.save(output_file_path)
        logger.info("Gemini edit image saved path=%s model=%s", output_file_path, model_id)
        return output_file_path
