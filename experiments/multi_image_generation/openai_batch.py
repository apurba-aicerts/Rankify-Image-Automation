"""OpenAI multi-image experiments (single request with n=count)."""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from lib_io import make_run_dir, multi_image_prompt, save_manifest, save_png_from_b64


def _logo_bytes(logo_path: Path) -> bytes:
    img = Image.open(logo_path)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def run_openai_mode(
    *,
    api_key: str,
    model: str,
    mode: str,
    count: int,
    prompt: str,
    logo_path: Path,
    size: str = "1024x1024",
) -> dict[str, Any]:
    """
    Modes:
      - generate: images.generate(prompt=..., n=count) — text only, no logo
      - edit_reference: images.edit(image=logo, prompt=..., n=count) — production-like
    """
    client = OpenAI(api_key=api_key)
    run_dir = make_run_dir("openai", f"{model}_{mode}_n{count}")
    user_prompt = multi_image_prompt(prompt, count)

    t0 = time.perf_counter()
    error: str | None = None
    saved_files: list[str] = []
    returned_n = 0

    try:
        if mode == "generate":
            result = client.images.generate(
                model=model,
                prompt=user_prompt[:32000],
                size=size,
                quality="high",
                output_format="png",
                n=count,
            )
        elif mode == "edit_reference":
            logo = _logo_bytes(logo_path)
            kwargs: dict[str, Any] = {
                "model": model,
                "image": ("brand_logo.png", logo, "image/png"),
                "prompt": (
                    f"{user_prompt}\n\n"
                    "Use the attached brand logo in each output slide."
                )[:32000],
                "size": size,
                "quality": "high",
                "output_format": "png",
                "n": count,
            }
            if model in ("gpt-image-1", "gpt-image-1.5"):
                kwargs["input_fidelity"] = "high"
            result = client.images.edit(**kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        data = result.data or []
        returned_n = len(data)
        for i, item in enumerate(data, start=1):
            b64 = item.b64_json
            if not b64:
                continue
            out_path = run_dir / f"image_{i:02d}.png"
            save_png_from_b64(b64, out_path)
            saved_files.append(out_path.name)
    except Exception as exc:
        error = str(exc)

    elapsed = time.perf_counter() - t0
    record: dict[str, Any] = {
        "provider": "openai",
        "model": model,
        "mode": mode,
        "requested_count": count,
        "returned_count": returned_n,
        "images_saved": len(saved_files),
        "saved_files": saved_files,
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
        "size": size,
        "run_dir": str(run_dir),
        "batch_in_one_request": True,
    }
    save_manifest(run_dir, record)
    return record


def run_openai_sequential_baseline(
    *,
    api_key: str,
    model: str,
    mode: str,
    count: int,
    prompt: str,
    logo_path: Path,
    size: str = "1024x1024",
) -> dict[str, Any]:
    """Same as production today: N separate API calls with n=1."""
    run_dir = make_run_dir("openai", f"{model}_{mode}_sequential_n{count}")
    t0 = time.perf_counter()
    saved_files: list[str] = []
    errors: list[str] = []

    for i in range(1, count + 1):
        try:
            rec = run_openai_mode(
                api_key=api_key,
                model=model,
                mode=mode,
                count=1,
                prompt=prompt + f"\n\n(This is variation {i} of {count}.)",
                logo_path=logo_path,
                size=size,
            )
            if rec.get("saved_files"):
                src_dir = Path(rec["run_dir"])
                for name in rec["saved_files"]:
                    src = src_dir / name
                    dst = run_dir / f"image_{i:02d}.png"
                    dst.write_bytes(src.read_bytes())
                    saved_files.append(dst.name)
            if rec.get("error"):
                errors.append(f"call_{i}: {rec['error']}")
        except Exception as exc:
            errors.append(f"call_{i}: {exc}")

    elapsed = time.perf_counter() - t0
    record = {
        "provider": "openai",
        "model": model,
        "mode": mode,
        "requested_count": count,
        "images_saved": len(saved_files),
        "saved_files": saved_files,
        "elapsed_seconds": round(elapsed, 2),
        "errors": errors,
        "run_dir": str(run_dir),
        "batch_in_one_request": False,
    }
    save_manifest(run_dir, record)
    return record
