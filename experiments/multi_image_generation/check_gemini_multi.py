"""
Minimal Gemini multi-image capability check (single request).

Gemini image endpoints don't expose a clean `n` parameter like OpenAI. This script:
  - makes ONE generateContent call
  - asks for N separate images
  - counts how many inline images were returned in the response parts

Run (PowerShell):
  cd experiments\multi_image_generation
  pip install -r requirements.txt
  python check_gemini_multi.py --n 3 --model gemini-2.5-flash-image

Requires GOOGLE_API_KEY in backend/.env (or environment).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image


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


def _extract_inline_images(resp_json: dict) -> list[str]:
    out: list[str] = []
    candidates = resp_json.get("candidates") or []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData")
            if isinstance(inline, dict) and inline.get("data"):
                out.append(str(inline["data"]))
    return out


def main() -> int:
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    backend = repo / "backend"
    load_dotenv(backend / ".env")
    load_dotenv(repo / ".env")

    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Requested image count (prompted)")
    parser.add_argument("--model", default="gemini-2.5-flash-image")
    parser.add_argument("--aspect", default="1:1")
    args = parser.parse_args()

    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Missing GOOGLE_API_KEY (set it in backend/.env)")

    logo_path = backend / "assets" / "default_logo.jpg"
    if not logo_path.is_file():
        raise SystemExit(f"Logo not found: {logo_path}")

    out_dir = here / "output" / "gemini_multi_check"
    out_dir.mkdir(parents=True, exist_ok=True)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{args.model}:generateContent?key={api_key}"
    )

    prompt = (
        f"Generate exactly {args.n} separate, distinct full-frame images as output. "
        f"Each must be a complete standalone marketing slide background (no text), not a collage. "
        f"Make each variation noticeably different."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    _logo_inline_part(logo_path),
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": args.aspect},
        },
    }

    r = requests.post(url, json=payload, timeout=180)
    if not r.ok:
        print(f"Gemini HTTP {r.status_code}")
        print((r.text or "")[:2000])
        return 2

    data = r.json()
    (out_dir / "response_meta.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "requested": args.n,
                "candidate_count": len(data.get("candidates") or []),
                "has_prompt_feedback": bool(data.get("promptFeedback")),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    imgs = _extract_inline_images(data)
    print(f"Gemini returned {len(imgs)} inline image part(s) (requested={args.n}, model={args.model}).")

    saved = 0
    for i, b64 in enumerate(imgs, start=1):
        path = out_dir / f"image_{i:02d}.png"
        path.write_bytes(base64.b64decode(b64))
        saved += 1

    print(f"Saved {saved} file(s) to: {out_dir}")
    if saved >= args.n:
        print("PASS: Gemini returned >=N inline images in one call.")
        return 0
    print("NOTE: Gemini did not return N separate images in one call. This is common; sequential calls may be required.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

