#!/usr/bin/env python3
"""
Smoke-test OpenAI gallery edit (Images API).

Usage (from backend/):
  python scripts/verify_openai_edit.py
  python scripts/verify_openai_edit.py --brand b1 --source rankify_slide_f67562f1_1.png
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Allow imports from backend/
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv(_BACKEND / ".env")


def _make_test_png(path: Path) -> None:
    img = Image.new("RGB", (512, 512), color=(30, 40, 60))
    draw = ImageDraw.Draw(img)
    draw.rectangle([64, 64, 448, 448], outline=(110, 180, 255), width=4)
    draw.text((140, 240), "Rankify edit test", fill=(255, 255, 255))
    img.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify OpenAI images.edit gallery path")
    parser.add_argument("--brand", default="verify-openai")
    parser.add_argument("--source", default="")
    parser.add_argument("--model", default="openai:gpt-image-1-mini")
    args = parser.parse_args()

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        print("FAIL: OPENAI_API_KEY not set in backend/.env")
        return 1

    from generation.edit_prompts import build_edit_user_prompt
    from generation.image_providers.runner import edit_image_to_file
    from generation.image_providers.openai_sizes import openai_size_for_gallery_edit
    from generation.image_providers.registry import normalize_model_id

    provider, api_model = normalize_model_id(args.model)
    if provider != "openai":
        print(f"FAIL: --model must be an OpenAI image model, got {args.model!r}")
        return 1

    size = openai_size_for_gallery_edit("1:1", "2K", api_model=api_model)
    print(f"Model: {api_model} | edit size param: {size}")

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.png"
        out = Path(tmp) / "edited.png"
        _make_test_png(src)
        with Image.open(src) as base:
            user_prompt = build_edit_user_prompt(
                "Change the rectangle outline color to orange. Keep everything else the same.",
                "Brand display name: Verify Brand",
            )
            edit_image_to_file(
                model_id=args.model,
                edit_system_prompt="(unused for OpenAI)",
                edit_user_prompt=user_prompt,
                base_image=base.copy(),
                output_file_path=str(out),
                aspect_ratio="1:1",
                image_size="2K",
                google_api_key="",
                openai_api_key=api_key,
            )
        if not out.is_file() or out.stat().st_size < 1000:
            print(f"FAIL: output missing or too small ({out.stat().st_size if out.is_file() else 0} bytes)")
            return 1
        print(f"OK: isolated edit wrote {out.stat().st_size} bytes")

    # Optional: hit real gallery file via API pipeline
    if args.source:
        from brands.repository import BrandRepository
        from generation.image_edit_pipeline import run_gallery_image_edit
        from gallery_local_store import gallery_file_exists

        brand_id = args.brand
        if not gallery_file_exists(brand_id, args.source):
            print(f"SKIP: gallery file not found for brand {brand_id}: {args.source}")
            return 0

        repo = BrandRepository()
        cfg = repo.load(brand_id)
        raw = run_gallery_image_edit(
            brand_id=brand_id,
            config=cfg,
            source_filename=args.source,
            instruction="Make the background slightly darker. Do not change text or layout.",
            model_id=args.model,
            aspect_ratio="1:1",
            image_size="2K",
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            openai_api_key=api_key,
            public_origin="http://127.0.0.1:9600",
            signing_secret=os.getenv("API_KEY", "test"),
            allowed_models=(args.model,),
            allowed_ratios=("1:1", "16:9", "9:16"),
            allowed_sizes=("1K", "2K", "4K"),
        )
        fn = raw["images"][0]["filename"]
        print(f"OK: pipeline edit -> {fn} ({raw['images'][0]['size_bytes']} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
