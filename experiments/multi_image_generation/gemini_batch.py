"""Gemini multi-image experiments (one generateContent call per strategy)."""

from __future__ import annotations

import base64
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from lib_io import (
    make_run_dir,
    multi_image_prompt,
    save_manifest,
    save_png_from_b64,
)


def _logo_inline_part(logo_path: Path) -> dict:
    img = Image.open(logo_path)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(buf.getvalue()).decode("utf-8"),
        }
    }


def extract_all_inline_images(data: dict) -> list[dict[str, Any]]:
    """Collect every inline image across candidates and parts."""
    found: list[dict[str, Any]] = []
    candidates = data.get("candidates") or []
    for ci, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            continue
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        for pi, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if isinstance(inline, dict) and inline.get("data"):
                found.append(
                    {
                        "candidate_index": ci,
                        "part_index": pi,
                        "mime": inline.get("mimeType") or inline.get("mime_type") or "image/png",
                        "b64": str(inline["data"]),
                        "text_nearby": (part.get("text") or "")[:200],
                    }
                )
            elif part.get("text"):
                found.append(
                    {
                        "candidate_index": ci,
                        "part_index": pi,
                        "type": "text",
                        "text_preview": str(part.get("text"))[:500],
                    }
                )
    return found


def run_gemini_strategy(
    *,
    api_key: str,
    model: str,
    strategy: str,
    count: int,
    prompt: str,
    logo_path: Path,
    aspect_ratio: str = "1:1",
    image_size: str | None = "2K",
) -> dict[str, Any]:
    """
    Strategies:
      - image_only: responseModalities=[IMAGE], multi-image prompt
      - text_and_image: responseModalities=[TEXT, IMAGE], multi-image prompt
      - candidate_count: candidateCount=count (often rejected by API)
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={api_key}"
    )
    user_text = multi_image_prompt(prompt, count)

    parts: list[dict] = [
        {"text": "Brand governance: professional B2B marketing slides, on-brand colors, readable typography."},
        {"text": user_text},
        _logo_inline_part(logo_path),
    ]

    image_config: dict = {"aspectRatio": aspect_ratio}
    if model == "gemini-3-pro-image-preview" and image_size:
        image_config["image_size"] = image_size

    gen_config: dict[str, Any] = {"imageConfig": image_config}

    if strategy == "image_only":
        gen_config["responseModalities"] = ["IMAGE"]
    elif strategy == "text_and_image":
        gen_config["responseModalities"] = ["TEXT", "IMAGE"]
    elif strategy == "candidate_count":
        gen_config["responseModalities"] = ["IMAGE"]
        gen_config["candidateCount"] = count
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": gen_config,
    }

    run_dir = make_run_dir("gemini", f"{model}_{strategy}_n{count}")
    t0 = time.perf_counter()
    error: str | None = None
    http_status: int | None = None
    raw: dict | None = None
    saved_files: list[str] = []

    try:
        resp = requests.post(url, json=payload, timeout=180)
        http_status = resp.status_code
        if not resp.ok:
            error = resp.text[:2000]
        else:
            raw = resp.json()
            parts_out = extract_all_inline_images(raw)
            image_idx = 0
            for item in parts_out:
                if "b64" not in item:
                    continue
                image_idx += 1
                out_path = run_dir / f"image_{image_idx:02d}.png"
                save_png_from_b64(item["b64"], out_path)
                saved_files.append(out_path.name)
    except Exception as exc:
        error = str(exc)

    elapsed = time.perf_counter() - t0
    image_parts = [p for p in (extract_all_inline_images(raw) if raw else []) if "b64" in p]
    text_parts = [p for p in (extract_all_inline_images(raw) if raw else []) if p.get("type") == "text"]

    record: dict[str, Any] = {
        "provider": "gemini",
        "model": model,
        "strategy": strategy,
        "requested_count": count,
        "elapsed_seconds": round(elapsed, 2),
        "http_status": http_status,
        "error": error,
        "images_saved": len(saved_files),
        "saved_files": saved_files,
        "image_parts_in_response": len(image_parts),
        "text_parts_in_response": len(text_parts),
        "finish_reasons": [
            (c.get("finishReason") if isinstance(c, dict) else None)
            for c in (raw or {}).get("candidates") or []
        ],
        "run_dir": str(run_dir),
    }
    if raw and not error:
        # Store compact response metadata (no base64 in manifest)
        record["response_meta"] = {
            "candidates": len(raw.get("candidates") or []),
            "prompt_feedback": raw.get("promptFeedback"),
            "part_summary": [
                {k: v for k, v in p.items() if k != "b64"}
                for p in extract_all_inline_images(raw)
            ],
        }
    save_manifest(run_dir, record)
    return record
