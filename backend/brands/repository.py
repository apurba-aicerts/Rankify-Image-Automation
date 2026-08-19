"""
Filesystem persistence for :class:`~brands.schemas.BrandConfiguration`.

Layout::

    <BRAND_DATA_DIR>/
      <brand_id>/
        brand.json      # BrandConfiguration
        assets/
          logo.png      # required on create; replace via API

``BRAND_DATA_DIR`` defaults to ``data/brands`` under the process cwd (``backend/`` when running uvicorn).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from brands.schemas import BrandConfiguration, validate_brand_id

load_dotenv()

logger = logging.getLogger(__name__)

_raw = os.getenv("BRAND_DATA_DIR", "").strip()
BRAND_DATA_DIR = Path(_raw if _raw else "data/brands").resolve()


class BrandRepository:
    """Load, save, list, and delete brand configuration directories."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or BRAND_DATA_DIR

    def _brand_dir(self, brand_id: str) -> Path:
        return self._root / validate_brand_id(brand_id)

    def _config_path(self, brand_id: str) -> Path:
        return self._brand_dir(brand_id) / "brand.json"

    def _assets_dir(self, brand_id: str) -> Path:
        return self._brand_dir(brand_id) / "assets"

    def ensure_layout(self, brand_id: str) -> None:
        """Create brand root and assets directory."""
        self._brand_dir(brand_id).mkdir(parents=True, exist_ok=True)
        self._assets_dir(brand_id).mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured brand layout brand_id=%s", brand_id)

    def exists(self, brand_id: str) -> bool:
        return self._config_path(brand_id).is_file()

    def load(self, brand_id: str) -> BrandConfiguration:
        path = self._config_path(brand_id)
        if not path.is_file():
            raise FileNotFoundError(f"Unknown brand_id: {brand_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = BrandConfiguration.model_validate(data)
        logger.debug("Loaded brand config brand_id=%s path=%s", brand_id, path)
        return cfg

    def save(self, config: BrandConfiguration) -> None:
        bid = validate_brand_id(config.brand_id)
        self.ensure_layout(bid)
        config = config.model_copy(
            update={"updated_at": datetime.now(timezone.utc)},
        )
        tmp = self._config_path(bid).with_suffix(".json.tmp")
        tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self._config_path(bid))
        logger.info("Saved brand config brand_id=%s", bid)

    def delete(self, brand_id: str) -> None:
        bid = validate_brand_id(brand_id)
        path = self._brand_dir(bid)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Deleted brand directory brand_id=%s", bid)

    def list_summaries(self) -> list[BrandConfiguration]:
        if not self._root.is_dir():
            return []
        out: list[BrandConfiguration] = []
        for child in sorted(self._root.iterdir()):
            if not child.is_dir():
                continue
            try:
                bid = validate_brand_id(child.name)
            except ValueError:
                continue
            cfg_path = child / "brand.json"
            if not cfg_path.is_file():
                continue
            try:
                out.append(self.load(bid))
            except (json.JSONDecodeError, OSError, ValueError):
                continue
        return out

    def logo_path(self, brand_id: str) -> Path:
        """Resolved path to configured logo file (may not exist yet)."""
        cfg = self.load(brand_id)
        return self._assets_dir(brand_id) / cfg.logo_asset_filename

    def list_brand_ids(self) -> list[str]:
        return [s.brand_id for s in self.list_summaries()]
