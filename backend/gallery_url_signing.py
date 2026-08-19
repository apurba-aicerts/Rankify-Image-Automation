"""
HMAC-signed URLs for brand-scoped gallery images.

Message format: ``brand_id:filename:exp`` so signatures cannot be reused across tenants.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from urllib.parse import quote

from brands.schemas import validate_brand_id
from gallery_local_store import validate_gallery_filename

GALLERY_IMAGE_URL_TTL_SECONDS = 3600

logger = logging.getLogger(__name__)


def _hmac_sha256_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def build_brand_gallery_image_view_url(
    *,
    public_api_origin: str,
    signing_secret: str,
    brand_id: str,
    filename: str,
    ttl_seconds: int = GALLERY_IMAGE_URL_TTL_SECONDS,
) -> str:
    validate_brand_id(brand_id)
    validate_gallery_filename(filename)
    exp = int(time.time()) + ttl_seconds
    msg = f"{brand_id}:{filename}:{exp}"
    sig = _hmac_sha256_hex(signing_secret, msg)
    b_enc = quote(brand_id, safe="")
    f_enc = quote(filename, safe="")
    url = f"{public_api_origin}/api/brands/{b_enc}/gallery/raw/{f_enc}?exp={exp}&sig={sig}"
    logger.debug("Built signed gallery URL brand_id=%s filename=%s ttl_s=%s", brand_id, filename, ttl_seconds)
    return url


def verify_brand_gallery_image_view_signature(
    *,
    signing_secret: str,
    brand_id: str,
    filename: str,
    exp: int,
    sig: str,
) -> bool:
    if exp < int(time.time()):
        logger.debug("Gallery URL verify failed: expired brand_id=%s filename=%s exp=%s", brand_id, filename, exp)
        return False
    try:
        validate_brand_id(brand_id)
        validate_gallery_filename(filename)
    except ValueError:
        logger.debug("Gallery URL verify failed: invalid id or filename brand_id=%s filename=%s", brand_id, filename)
        return False
    expected = _hmac_sha256_hex(signing_secret, f"{brand_id}:{filename}:{exp}")
    ok = hmac.compare_digest(expected, sig)
    if not ok:
        logger.debug("Gallery URL verify failed: bad signature brand_id=%s filename=%s", brand_id, filename)
    return ok


def build_brand_logo_view_url(
    *,
    public_api_origin: str,
    signing_secret: str,
    brand_id: str,
    ttl_seconds: int = GALLERY_IMAGE_URL_TTL_SECONDS,
) -> str:
    """HMAC URL for GET /api/brands/{brand_id}/assets/logo/raw (local storage)."""
    validate_brand_id(brand_id)
    exp = int(time.time()) + ttl_seconds
    msg = f"{brand_id}:logo:{exp}"
    sig = _hmac_sha256_hex(signing_secret, msg)
    b_enc = quote(brand_id, safe="")
    return f"{public_api_origin}/api/brands/{b_enc}/assets/logo/raw?exp={exp}&sig={sig}"


def verify_brand_logo_view_signature(
    *,
    signing_secret: str,
    brand_id: str,
    exp: int,
    sig: str,
) -> bool:
    if exp < int(time.time()):
        logger.debug("Logo URL verify failed: expired brand_id=%s exp=%s", brand_id, exp)
        return False
    try:
        validate_brand_id(brand_id)
    except ValueError:
        logger.debug("Logo URL verify failed: invalid brand_id=%s", brand_id)
        return False
    expected = _hmac_sha256_hex(signing_secret, f"{brand_id}:logo:{exp}")
    ok = hmac.compare_digest(expected, sig)
    if not ok:
        logger.debug("Logo URL verify failed: bad signature brand_id=%s", brand_id)
    return ok
