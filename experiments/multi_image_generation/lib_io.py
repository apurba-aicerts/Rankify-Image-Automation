"""Shared helpers for multi-image experiments."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_BACKEND = _REPO / "backend"
OUTPUT_ROOT = _HERE / "output"


def bootstrap_paths() -> None:
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))
    load_dotenv(_BACKEND / ".env")
    load_dotenv(_REPO / ".env")


def require_key(name: str) -> str:
    val = (os.getenv(name) or "").strip()
    if not val:
        raise SystemExit(f"Missing {name} in backend/.env")
    return val


def default_logo_path() -> Path:
    p = _BACKEND / "assets" / "default_logo.jpg"
    if not p.is_file():
        raise SystemExit(f"Logo not found: {p}")
    return p


def load_prompt(path: Path | None) -> str:
    if path and path.is_file():
        return path.read_text(encoding="utf-8").strip()
    sample = _HERE / "sample_prompt.txt"
    return sample.read_text(encoding="utf-8").strip()


def make_run_dir(provider: str, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = label.replace(" ", "_").replace("/", "-")[:48]
    run_dir = OUTPUT_ROOT / f"{stamp}_{provider}_{safe}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_png_from_b64(b64_data: str, path: Path) -> int:
    raw = base64.b64decode(b64_data)
    img = Image.open(BytesIO(raw))
    img.save(path)
    return path.stat().st_size


def save_manifest(run_dir: Path, record: dict[str, Any]) -> Path:
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path


def multi_image_prompt(base: str, count: int) -> str:
    return (
        f"{base.strip()}\n\n"
        f"IMPORTANT: Produce exactly {count} separate, distinct full-frame images as output. "
        f"Each image must be a complete standalone slide (not a collage, not a comic strip, "
        f"not a single image split into panels). Number them conceptually as variation 1 through {count} "
        f"with noticeably different layout or visual treatment while keeping the same message."
    )
