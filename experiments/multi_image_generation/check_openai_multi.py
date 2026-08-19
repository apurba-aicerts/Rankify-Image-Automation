"""
Minimal OpenAI multi-image capability check.

This checks that the Images API returns multiple outputs in ONE request via `n`.

Run (PowerShell):
  cd experiments\multi_image_generation
  pip install -r requirements.txt
  python check_openai_multi.py --n 3 --model gpt-image-1-mini

Requires OPENAI_API_KEY in backend/.env (or environment).
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main() -> int:
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    backend = repo / "backend"
    load_dotenv(backend / ".env")
    load_dotenv(repo / ".env")

    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Number of images to request (1-10)")
    parser.add_argument("--model", default="gpt-image-1-mini")
    parser.add_argument("--size", default="1024x1024")
    args = parser.parse_args()

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY (set it in backend/.env)")

    if args.n < 1 or args.n > 10:
        raise SystemExit("--n must be 1..10")

    out_dir = here / "output" / "openai_multi_check"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(api_key=api_key)
    prompt = (
        "Generate exactly {n} distinct images. "
        "Each should be a different clean, modern marketing slide background (no text), "
        "using a blue accent color. "
        "Return separate images, not a collage."
    ).format(n=args.n)

    rsp = client.images.generate(
        model=args.model,
        prompt=prompt,
        n=args.n,
        size=args.size,
        quality="high",
        output_format="png",
    )

    data = rsp.data or []
    print(f"OpenAI returned {len(data)} image(s) for n={args.n} (model={args.model}).")

    saved = 0
    for i, item in enumerate(data, start=1):
        if not getattr(item, "b64_json", None):
            continue
        path = out_dir / f"image_{i:02d}.png"
        path.write_bytes(base64.b64decode(item.b64_json))
        saved += 1

    print(f"Saved {saved} file(s) to: {out_dir}")
    if len(data) >= args.n and saved >= args.n:
        print("PASS: multi-image generation via `n` works.")
        return 0
    print("FAIL: did not receive/save the requested number of images.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

