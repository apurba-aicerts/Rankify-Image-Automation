"""
Rankify HTTP API — multi-brand FastAPI application.

Run::

    uvicorn main:app --host 0.0.0.0 --port 8750

Brand configuration lives under ``data/brands/``; generated images under ``generated-images/<brand_id>/``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from PIL import Image
from pydantic import BaseModel, Field, model_validator

from brands.ai_brand_draft_service import draft_brand_create_payload_from_materials
from brands.demo_brand_template import build_demo_ai_certs_brand
from brands.repository import BRAND_DATA_DIR, BrandRepository
from brands.repository_factory import get_brand_repository
from db.config import database_enabled
from db.session import init_database
from storage.config import STORAGE_BACKEND, s3_enabled
from brands.schemas import (
    BrandAiDraftRequest,
    BrandAiDraftResponse,
    BrandConfiguration,
    BrandCreatePayload,
    BrandSummary,
    validate_brand_id,
)
from gallery_url_signing import verify_brand_gallery_image_view_signature
from generation.campaign_assembler import build_structured_campaign_copy, user_brief_for_image_generation
from generation.image_edit_pipeline import run_gallery_image_edit
from generation.openai_social_copy_service import generate_social_copy_openai
from generation.image_providers.registry import ALLOWED_IMAGE_MODEL_IDS, models_list_payload
from generation.slide_pipeline import run_brand_slide_generation
from logging_config import configure_logging
from gallery_local_store import (
    GALLERY_STORAGE_DIR,
    GalleryFileMetadata,
    logical_gallery_key,
    validate_gallery_filename,
)
from services.brand_assets import resolve_logo_local_path, save_logo_upload
from services.gallery_service import (
    build_gallery_view_url,
    delete_gallery_image,
    gallery_image_exists,
    list_gallery_metadata,
    purge_all_galleries_older_than_hours,
    resolve_gallery_local_path,
)

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)

DEFAULT_LOGO_PATH = Path("assets/default_logo.jpg")

API_KEY: str = os.getenv("API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
# Gallery history retention (default 30 days). Purge job deletes DB rows + S3/local blobs older than this.
IMAGE_TTL_HOURS: int = int(os.getenv("IMAGE_TTL_HOURS", str(30 * 24)))
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

ALLOWED_MODEL_IDS: tuple[str, ...] = ALLOWED_IMAGE_MODEL_IDS

ALLOWED_ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)

ALLOWED_IMAGE_SIZES: tuple[str, ...] = ("1K", "2K", "4K")


def _public_api_origin(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    return str(request.base_url).rstrip("/")


async def _run_periodic_gallery_ttl_cleanup() -> None:
    while True:
        try:
            deleted = purge_all_galleries_older_than_hours(IMAGE_TTL_HOURS)
            if deleted:
                logger.info("Gallery TTL purge removed %s file(s) older than %sh.", deleted, IMAGE_TTL_HOURS)
        except Exception:
            logger.exception("Gallery TTL purge failed; will retry in 900s.")
        await asyncio.sleep(900)


@asynccontextmanager
async def _application_lifespan(app: FastAPI):
    if s3_enabled() and not database_enabled():
        raise RuntimeError("STORAGE_BACKEND=s3 requires DATABASE_URL to be set.")
    if database_enabled():
        init_database()
    logger.info(
        "Rankify API starting | storage=%s db=%s gallery=%s brands=%s ttl_h=%s",
        STORAGE_BACKEND,
        database_enabled(),
        GALLERY_STORAGE_DIR,
        BRAND_DATA_DIR,
        IMAGE_TTL_HOURS,
    )
    task = asyncio.create_task(_run_periodic_gallery_ttl_cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Rankify API shutdown complete.")


app = FastAPI(
    title="Rankify — Multi-brand image API",
    version="3.0.0",
    description="Brand-scoped configuration, Gemini and OpenAI image generation, and per-brand galleries.",
    lifespan=_application_lifespan,
)

@app.middleware("http")
async def _log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "Request failed %s %s (%.1f ms)",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    log_fn = logger.debug if request.url.path == "/health" else logger.info
    log_fn(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Must be False when allow_origins is "*"; auth uses x-api-key header, not cookies.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_rankify_api_key(
    x_api_key: str = Header(..., alias="x-api-key"),
) -> None:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured on the server.",
        )
    if x_api_key != API_KEY:
        logger.warning("Rejected request: invalid or missing API key (x-api-key mismatch).")
        raise HTTPException(status_code=401, detail="Invalid API key.")


class StudioCampaignBrief(BaseModel):
    """Fields from the Creative Studio prompt and studio controls."""

    campaign_goal_id: str = Field(
        default="brand_awareness",
        description="Legacy field for social-copy assembly; studio UI no longer sets this.",
    )
    platforms: list[str] = Field(
        default_factory=list,
        description="Lowercase ids: linkedin, instagram, …",
    )
    voice_tone_label: str = Field(default="Professional", description="Studio tone dropdown label.")
    creativity_tone_label: str = Field(
        ...,
        description="Full AI creativity string, e.g. Balanced — on-brand with light creative stretch",
    )
    intent: str = Field(..., min_length=1, description="User content intent / prompt.")


class BrandStudioSocialCopyRequest(BaseModel):
    """Same studio brief as slide generation; optional gallery file for vision-grounded copy."""

    studio_campaign: StudioCampaignBrief
    image_filename: Optional[str] = Field(
        default=None,
        description="Filename in this brand's gallery (e.g. rankify_slide_….png). When set and file exists, sent to the text model as an image.",
    )


class BrandStudioSocialCopyResponse(BaseModel):
    caption: str
    hashtags: str = Field(..., description="Space-separated hashtags, each starting with #.")
    model_used: str


class BrandSlideGenerateRequest(BaseModel):
    brand_id: str = Field(..., description="Configured brand slug (see GET /api/brands).")
    content: Optional[str] = Field(
        default=None,
        description="Legacy structured post copy (TITLE / SUBTITLE / BODY / CTA). Ignored when `studio_campaign` is set.",
    )
    studio_campaign: Optional[StudioCampaignBrief] = Field(
        default=None,
        description="When set, server builds structured post copy from brand display name + this brief.",
    )
    model_name: str = Field(default="gemini-3-pro-image-preview")
    num_images: int = Field(default=1, ge=1, le=10)
    aspect_ratio: str = Field(default="1:1")
    image_size: Optional[str] = Field(default="2K")

    @model_validator(mode="after")
    def content_or_studio_campaign(self) -> BrandSlideGenerateRequest:
        if self.studio_campaign is not None:
            return self
        if not (self.content or "").strip():
            raise ValueError("Provide `studio_campaign` or a non-empty `content` string.")
        return self


class GalleryImageItem(BaseModel):
    filename: str
    url: str
    storage_path: str
    size_bytes: int
    created_at: str
    age_hours: float


class BrandSlideGenerateResponse(BaseModel):
    images: list[GalleryImageItem]
    model_used: str
    per_image_price_usd: float
    total_price_usd: float
    message: str
    generation_audit_path: Optional[str] = Field(
        default=None,
        description="Server path to UTF-8 audit .txt (full prompts, colors, fonts) if written; see RANKIFY_GENERATION_AUDIT.",
    )


class GalleryListResponse(BaseModel):
    total: int
    images: list[GalleryImageItem]


class GalleryDeleteResponse(BaseModel):
    message: str
    filename: str


class GalleryImageEditRequest(BaseModel):
    """Refine an existing gallery asset with a text instruction (same response shape as generate for one image)."""

    source_filename: str = Field(..., description="Gallery filename to load as the edit source (e.g. rankify_slide_abc_1.png).")
    instruction: str = Field(..., min_length=3, max_length=2000, description="What to change; everything else should stay as-is.")
    model_name: str = Field(
        default="gemini-2.5-flash-image",
        description="Gemini model id or OpenAI namespaced id (e.g. openai:gpt-image-2). Flash is a fast default for edits.",
    )
    aspect_ratio: str = Field(default="1:1")
    image_size: Optional[str] = Field(
        default="2K",
        description="Only used when model_name is gemini-3-pro-image-preview.",
    )


def _build_gallery_image_item(
    *,
    brand_id: str,
    filename: str,
    size_bytes: int,
    last_modified: datetime,
    public_origin: str,
) -> GalleryImageItem:
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - last_modified).total_seconds() / 3600
    view_url = build_gallery_view_url(
        brand_id=brand_id,
        filename=filename,
        public_origin=public_origin,
        signing_secret=API_KEY,
    )
    return GalleryImageItem(
        filename=filename,
        url=view_url,
        storage_path=logical_gallery_key(brand_id, filename),
        size_bytes=size_bytes,
        created_at=last_modified.isoformat(),
        age_hours=round(age_hours, 2),
    )


def _http_media_type_for_image_filename(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


_ALLOWED_LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _logo_suffix_from_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "logo").suffix.lower()
    if suffix not in _ALLOWED_LOGO_SUFFIXES:
        raise HTTPException(status_code=400, detail="Logo must be png, jpg, or webp.")
    return suffix


async def _spool_upload_to_temp(file: UploadFile, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        return tmp.name


def _load_brand_or_404(brand_id: str) -> BrandConfiguration:
    repo = get_brand_repository()
    try:
        return repo.load(brand_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Brand not found: {brand_id}")


def _run_brand_studio_social_copy(
    brand_id: str, body: BrandStudioSocialCopyRequest
) -> BrandStudioSocialCopyResponse:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server.",
        )
    cfg = _load_brand_or_404(brand_id)
    sc = body.studio_campaign
    structured = build_structured_campaign_copy(
        display_name=cfg.display_name or brand_id,
        campaign_goal_id=sc.campaign_goal_id,
        platforms=list(sc.platforms),
        creativity_tone_label=sc.creativity_tone_label,
        voice_tone_label=sc.voice_tone_label,
        intent=sc.intent,
    )
    image_path: Optional[Path] = None
    if body.image_filename and body.image_filename.strip():
        fn = body.image_filename.strip()
        if not gallery_image_exists(brand_id, fn):
            raise HTTPException(status_code=400, detail=f"Gallery image not found: {fn}")
        image_path = resolve_gallery_local_path(brand_id, fn)
    cap, tags, model_used = generate_social_copy_openai(
        cfg=cfg,
        structured_post_copy=structured,
        image_path=image_path,
        openai_api_key=OPENAI_API_KEY,
    )
    resp = BrandStudioSocialCopyResponse(caption=cap, hashtags=tags, model_used=model_used)
    if database_enabled():
        from db.repositories import GeneratedImageDbRepository, SocialCopyDbRepository

        img_id = None
        if body.image_filename and body.image_filename.strip():
            row = GeneratedImageDbRepository().get_by_filename(brand_id, body.image_filename.strip())
            if row is not None:
                img_id = row.id
        SocialCopyDbRepository().insert(
            brand_id=brand_id,
            caption=cap,
            hashtags=tags,
            model_used=model_used,
            generated_image_id=img_id,
        )
    return resp


@app.get("/health")
async def read_health_status() -> dict:
    payload: dict = {
        "status": "ok",
        "storage_backend": STORAGE_BACKEND,
        "database": "enabled" if database_enabled() else "disabled",
        "gallery_root": str(GALLERY_STORAGE_DIR),
        "brand_config_root": str(BRAND_DATA_DIR),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if database_enabled():
        try:
            from db.session import get_engine
            from sqlalchemy import text

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            payload["database_status"] = "ok"
        except Exception as exc:
            payload["status"] = "degraded"
            payload["database_status"] = f"error: {exc}"
    if s3_enabled():
        try:
            from storage.s3_client import get_s3_client
            from storage.config import AWS_S3_BUCKET_NAME

            get_s3_client().head_bucket(Bucket=AWS_S3_BUCKET_NAME)
            payload["s3_status"] = "ok"
        except Exception as exc:
            payload["status"] = "degraded"
            payload["s3_status"] = f"error: {exc}"
    return payload


@app.get(
    "/api/brands",
    dependencies=[Depends(require_rankify_api_key)],
    summary="List onboarded brands",
)
async def list_brands() -> dict:
    repo = get_brand_repository()
    summaries: list[BrandSummary] = repo.list_summaries()
    logger.debug("Listed brands count=%s", len(summaries))
    return {"brands": [s.model_dump(mode="json") for s in summaries], "total": len(summaries)}


@app.post(
    "/api/brands",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Onboard a new brand (multipart: payload JSON + required logo file)",
)
async def create_brand(
    payload: str = Form(..., description="JSON-serialized BrandCreatePayload"),
    logo: UploadFile = File(..., description="Brand logo image (required)"),
) -> BrandConfiguration:
    from pydantic import ValidationError

    try:
        body = BrandCreatePayload.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    cfg = body.to_configuration()
    brand_id = cfg.brand_id
    repo = get_brand_repository()
    if repo.exists(brand_id):
        raise HTTPException(status_code=409, detail="brand_id already exists.")
    suffix = _logo_suffix_from_upload(logo)
    tmp_path = await _spool_upload_to_temp(logo, suffix)
    try:
        repo.save(cfg)
        save_logo_upload(
            brand_id=brand_id,
            temp_path=tmp_path,
            filename=cfg.logo_asset_filename,
            content_type=_http_media_type_for_image_filename(f"x{suffix}"),
        )
    except HTTPException:
        if repo.exists(brand_id):
            repo.delete(brand_id)
        raise
    except Exception as exc:
        if repo.exists(brand_id):
            repo.delete(brand_id)
        raise HTTPException(status_code=500, detail=f"Logo upload failed: {exc}") from exc
    finally:
        try:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
    logger.info("Brand created brand_id=%s display_name=%s (with logo)", brand_id, cfg.display_name)
    return cfg


@app.post(
    "/api/brands/ai-draft",
    response_model=BrandAiDraftResponse,
    dependencies=[Depends(require_rankify_api_key)],
    summary="Draft brand configuration from unstructured notes (OpenAI structured outputs)",
)
async def ai_draft_brand(body: BrandAiDraftRequest) -> BrandAiDraftResponse:
    """
    Returns a validated :class:`BrandCreatePayload` for human review; does not persist.
    Register ``OPENAI_API_KEY`` in the server environment. If ``brand_id`` is omitted, a UUID slug is used.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server.",
        )
    draft = draft_brand_create_payload_from_materials(
        brand_materials=body.brand_materials,
        brand_id=body.brand_id,
        model_name=body.model_name,
        openai_api_key=OPENAI_API_KEY,
    )
    logger.info(
        "Brand AI draft model=%s draft_brand_id=%s display_name=%s",
        body.model_name,
        draft.brand_id,
        draft.display_name,
    )
    return BrandAiDraftResponse(draft=draft, model_used=body.model_name)


@app.post(
    "/api/brands/bootstrap-demo",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Create demo-ai-certs brand from packaged template (idempotent)",
)
async def bootstrap_demo_brand() -> BrandConfiguration:
    repo = get_brand_repository()
    cfg = build_demo_ai_certs_brand("demo-ai-certs")
    if repo.exists(cfg.brand_id):
        logger.debug("Bootstrap demo: brand already exists brand_id=%s", cfg.brand_id)
        return repo.load(cfg.brand_id)
    repo.save(cfg)
    logger.info("Bootstrap demo brand saved brand_id=%s", cfg.brand_id)
    return cfg


@app.get(
    "/api/brands/{brand_id}",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Get brand configuration",
)
async def get_brand(brand_id: str) -> BrandConfiguration:
    return _load_brand_or_404(brand_id)


@app.put(
    "/api/brands/{brand_id}",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Replace brand configuration",
)
async def replace_brand(brand_id: str, body: BrandConfiguration) -> BrandConfiguration:
    validate_brand_id(brand_id)
    if body.brand_id != brand_id:
        raise HTTPException(status_code=400, detail="brand_id in path and body must match.")
    repo = get_brand_repository()
    if not repo.exists(brand_id):
        raise HTTPException(status_code=404, detail="Brand not found.")
    repo.save(body)
    logger.info("Brand updated brand_id=%s", brand_id)
    return body


@app.delete(
    "/api/brands/{brand_id}",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Delete brand configuration, assets, and generated gallery for that brand",
)
async def delete_brand(brand_id: str) -> dict:
    repo = get_brand_repository()
    if not repo.exists(brand_id):
        raise HTTPException(status_code=404, detail="Brand not found.")
    repo.delete(brand_id)
    gdir = GALLERY_STORAGE_DIR / validate_brand_id(brand_id)
    if gdir.is_dir():
        shutil.rmtree(gdir, ignore_errors=True)
    logger.info("Brand deleted brand_id=%s (config + gallery)", brand_id)
    return {"message": f"Brand {brand_id} and its gallery folder removed.", "brand_id": brand_id}


@app.post(
    "/api/brands/{brand_id}/assets/logo",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Upload or replace default logo PNG/JPG",
)
async def upload_brand_logo(
    brand_id: str,
    file: UploadFile = File(..., description="Logo image"),
) -> dict:
    cfg = _load_brand_or_404(brand_id)
    get_brand_repository().ensure_layout(brand_id)
    suffix = _logo_suffix_from_upload(file)
    content_type = _http_media_type_for_image_filename(f"x{suffix}")
    tmp_path = await _spool_upload_to_temp(file, suffix)
    try:
        stored = save_logo_upload(
            brand_id=brand_id,
            temp_path=tmp_path,
            filename=cfg.logo_asset_filename,
            content_type=content_type,
        )
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info("Logo uploaded brand_id=%s stored=%s", brand_id, stored)
    return {"message": "Logo saved.", "path": stored}


@app.get(
    "/api/brands/{brand_id}/assets/logo",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Download configured logo file (if present)",
)
async def get_brand_logo(brand_id: str) -> FileResponse:
    cfg = _load_brand_or_404(brand_id)
    path = resolve_logo_local_path(brand_id, cfg.logo_asset_filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="No logo file for this brand yet.")
    return FileResponse(path, media_type=_http_media_type_for_image_filename(path.name))


@app.post(
    "/api/brands/{brand_id}/text/social-copy",
    dependencies=[Depends(require_rankify_api_key)],
    response_model=BrandStudioSocialCopyResponse,
    summary="Generate caption + hashtags (OpenAI; optional vision on a gallery image)",
)
async def brand_text_social_copy(
    brand_id: str, body: BrandStudioSocialCopyRequest
) -> BrandStudioSocialCopyResponse:
    return _run_brand_studio_social_copy(brand_id, body)


@app.post(
    "/api/brands/{brand_id}/text/captions",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Caption + hashtags via OpenAI (same payload as social-copy)",
)
async def brand_text_captions(brand_id: str, body: BrandStudioSocialCopyRequest) -> BrandStudioSocialCopyResponse:
    """Kept for older clients; returns the full social-copy object (caption + hashtags)."""
    return _run_brand_studio_social_copy(brand_id, body)


@app.post(
    "/api/brands/{brand_id}/text/hashtags",
    dependencies=[Depends(require_rankify_api_key)],
    summary="Caption + hashtags via OpenAI (same payload as social-copy)",
)
async def brand_text_hashtags(brand_id: str, body: BrandStudioSocialCopyRequest) -> BrandStudioSocialCopyResponse:
    """Kept for older clients; returns the full social-copy object (caption + hashtags)."""
    return _run_brand_studio_social_copy(brand_id, body)


@app.get(
    "/api/models",
    dependencies=[Depends(require_rankify_api_key)],
)
async def list_supported_image_models() -> dict:
    return {"models": models_list_payload()}


@app.get(
    "/api/image-sizes",
    dependencies=[Depends(require_rankify_api_key)],
)
async def list_supported_image_sizes_and_ratios() -> dict:
    return {
        "image_sizes": list(ALLOWED_IMAGE_SIZES),
        "note": "Image size applies to gemini-3-pro-image-preview and OpenAI gpt-image-1 / gpt-image-2 models.",
        "aspect_ratios": list(ALLOWED_ASPECT_RATIOS),
    }


@app.post(
    "/api/generate",
    response_model=BrandSlideGenerateResponse,
    dependencies=[Depends(require_rankify_api_key)],
    summary="Generate slides (JSON; uses brand logo or assets/default)",
)
async def generate_brand_slides_from_json(
    request: Request,
    body: BrandSlideGenerateRequest,
) -> BrandSlideGenerateResponse:
    cfg = _load_brand_or_404(body.brand_id)
    if body.studio_campaign is not None:
        structured_post_copy = user_brief_for_image_generation(body.studio_campaign.intent)
        logger.debug("Using verbatim studio_campaign intent for brand_id=%s", body.brand_id)
    else:
        structured_post_copy = (body.content or "").strip()
    logger.info(
        "Generate JSON brand_id=%s model=%s num_images=%s aspect_ratio=%s",
        body.brand_id,
        body.model_name,
        body.num_images,
        body.aspect_ratio,
    )
    raw = run_brand_slide_generation(
        brand_id=body.brand_id,
        config=cfg,
        structured_post_copy=structured_post_copy,
        model_id=body.model_name,
        slide_count=body.num_images,
        aspect_ratio=body.aspect_ratio,
        image_size=body.image_size or "2K",
        logo_override=None,
        logo_fallback_path=DEFAULT_LOGO_PATH,
        google_api_key=GOOGLE_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        public_origin=_public_api_origin(request),
        signing_secret=API_KEY,
        allowed_models=ALLOWED_MODEL_IDS,
        allowed_ratios=ALLOWED_ASPECT_RATIOS,
        allowed_sizes=ALLOWED_IMAGE_SIZES,
    )
    logger.info(
        "Generate JSON complete brand_id=%s images=%s total_usd=%s",
        body.brand_id,
        len(raw.get("images", [])),
        raw.get("total_price_usd"),
    )
    return BrandSlideGenerateResponse.model_validate(raw)


@app.post(
    "/api/generate-with-logo",
    response_model=BrandSlideGenerateResponse,
    dependencies=[Depends(require_rankify_api_key)],
    summary="Generate slides (multipart; optional logo override for this batch)",
)
async def generate_brand_slides_from_multipart(
    request: Request,
    brand_id: str = Form(..., description="Brand slug."),
    content: str = Form(...),
    model_name: str = Form("gemini-3-pro-image-preview"),
    num_images: int = Form(1, ge=1, le=10),
    aspect_ratio: str = Form("1:1"),
    image_size: str = Form("2K"),
    logo: Optional[UploadFile] = File(None),
) -> BrandSlideGenerateResponse:
    cfg = _load_brand_or_404(brand_id)
    logo_override = Image.open(logo.file) if logo else None
    logger.info(
        "Generate multipart brand_id=%s model=%s num_images=%s logo_override=%s",
        brand_id,
        model_name,
        num_images,
        bool(logo),
    )
    try:
        raw = run_brand_slide_generation(
            brand_id=brand_id,
            config=cfg,
            structured_post_copy=content,
            model_id=model_name,
            slide_count=num_images,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            logo_override=logo_override,
            logo_fallback_path=DEFAULT_LOGO_PATH,
            google_api_key=GOOGLE_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            public_origin=_public_api_origin(request),
            signing_secret=API_KEY,
            allowed_models=ALLOWED_MODEL_IDS,
            allowed_ratios=ALLOWED_ASPECT_RATIOS,
            allowed_sizes=ALLOWED_IMAGE_SIZES,
        )
    finally:
        if logo_override is not None:
            try:
                logo_override.close()
            except Exception:
                pass
    logger.info(
        "Generate multipart complete brand_id=%s images=%s",
        brand_id,
        len(raw.get("images", [])),
    )
    return BrandSlideGenerateResponse.model_validate(raw)


@app.post(
    "/api/generate-with-reference",
    response_model=BrandSlideGenerateResponse,
    dependencies=[Depends(require_rankify_api_key)],
    summary="Generate slides (multipart; optional style/layout reference + optional logo override)",
)
async def generate_brand_slides_with_reference(
    request: Request,
    brand_id: str = Form(..., description="Brand slug."),
    studio_campaign: str = Form(..., description="JSON object matching StudioCampaignBrief."),
    model_name: str = Form("gemini-3-pro-image-preview"),
    num_images: int = Form(1, ge=1, le=10),
    aspect_ratio: str = Form("1:1"),
    image_size: str = Form("2K"),
    reference_image: Optional[UploadFile] = File(None, description="Optional style/layout inspiration image."),
    logo: Optional[UploadFile] = File(None, description="Optional logo override for this batch."),
) -> BrandSlideGenerateResponse:
    cfg = _load_brand_or_404(brand_id)
    try:
        brief = StudioCampaignBrief.model_validate_json(studio_campaign)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid studio_campaign JSON: {exc}") from exc

    structured_post_copy = user_brief_for_image_generation(brief.intent)

    logo_override = Image.open(logo.file) if logo else None
    reference_override = Image.open(reference_image.file) if reference_image else None
    logger.info(
        "Generate with reference brand_id=%s model=%s num_images=%s reference=%s logo_override=%s",
        brand_id,
        model_name,
        num_images,
        bool(reference_image),
        bool(logo),
    )
    try:
        raw = run_brand_slide_generation(
            brand_id=brand_id,
            config=cfg,
            structured_post_copy=structured_post_copy,
            model_id=model_name,
            slide_count=num_images,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            logo_override=logo_override,
            logo_fallback_path=DEFAULT_LOGO_PATH,
            reference_override=reference_override,
            google_api_key=GOOGLE_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            public_origin=_public_api_origin(request),
            signing_secret=API_KEY,
            allowed_models=ALLOWED_MODEL_IDS,
            allowed_ratios=ALLOWED_ASPECT_RATIOS,
            allowed_sizes=ALLOWED_IMAGE_SIZES,
        )
    finally:
        for img in (logo_override, reference_override):
            if img is not None:
                try:
                    img.close()
                except Exception:
                    pass
    logger.info(
        "Generate with reference complete brand_id=%s images=%s",
        brand_id,
        len(raw.get("images", [])),
    )
    return BrandSlideGenerateResponse.model_validate(raw)


@app.get(
    "/api/brands/{brand_id}/gallery",
    response_model=GalleryListResponse,
    dependencies=[Depends(require_rankify_api_key)],
)
async def list_brand_gallery(brand_id: str, request: Request) -> GalleryListResponse:
    _ = _load_brand_or_404(brand_id)
    public_origin = _public_api_origin(request)
    try:
        rows: list[GalleryFileMetadata] = list_gallery_metadata(brand_id)
    except OSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    rows.sort(key=lambda r: r.last_modified_utc, reverse=True)
    items = [
        _build_gallery_image_item(
            brand_id=brand_id,
            filename=m.filename,
            size_bytes=m.size_bytes,
            last_modified=m.last_modified_utc,
            public_origin=public_origin,
        )
        for m in rows
    ]
    logger.debug("Gallery list brand_id=%s total=%s", brand_id, len(items))
    return GalleryListResponse(total=len(items), images=items)


@app.post(
    "/api/brands/{brand_id}/gallery/edit",
    response_model=BrandSlideGenerateResponse,
    dependencies=[Depends(require_rankify_api_key)],
    summary="AI-edit an existing gallery image (instruction + source image; preserves layout by prompt policy)",
)
async def edit_brand_gallery_image(
    brand_id: str,
    request: Request,
    body: GalleryImageEditRequest,
) -> BrandSlideGenerateResponse:
    """
    Loads ``source_filename`` from the brand gallery, sends it to the selected image model (Gemini or OpenAI)
    with strict preservation prompts, and writes a new ``rankify_edit_*.png`` file.
    """
    cfg = _load_brand_or_404(brand_id)
    logger.info(
        "Gallery edit brand_id=%s source=%s model=%s aspect=%s",
        brand_id,
        body.source_filename,
        body.model_name,
        body.aspect_ratio,
    )
    raw = run_gallery_image_edit(
        brand_id=brand_id,
        config=cfg,
        source_filename=body.source_filename,
        instruction=body.instruction,
        model_id=body.model_name,
        aspect_ratio=body.aspect_ratio,
        image_size=body.image_size or "2K",
        google_api_key=GOOGLE_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        public_origin=_public_api_origin(request),
        signing_secret=API_KEY,
        allowed_models=ALLOWED_MODEL_IDS,
        allowed_ratios=ALLOWED_ASPECT_RATIOS,
        allowed_sizes=ALLOWED_IMAGE_SIZES,
    )
    return BrandSlideGenerateResponse.model_validate(raw)


@app.get(
    "/api/brands/{brand_id}/gallery/{filename}",
    dependencies=[Depends(require_rankify_api_key)],
)
async def redirect_brand_gallery_image(brand_id: str, filename: str, request: Request) -> RedirectResponse:
    _ = _load_brand_or_404(brand_id)
    try:
        validate_gallery_filename(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not gallery_image_exists(brand_id, filename):
        raise HTTPException(status_code=404, detail="Image not found.")
    url = build_gallery_view_url(
        brand_id=brand_id,
        filename=filename,
        public_origin=_public_api_origin(request),
        signing_secret=API_KEY,
    )
    return RedirectResponse(url=url, status_code=307)


@app.get("/api/brands/{brand_id}/gallery/raw/{filename}")
async def stream_brand_gallery_image(brand_id: str, filename: str, exp: int, sig: str) -> FileResponse:
    brand_id = unquote(brand_id)
    filename = unquote(filename)
    try:
        validate_brand_id(brand_id)
        validate_gallery_filename(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid brand_id or filename.")
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY is not configured.")
    if not verify_brand_gallery_image_view_signature(
        signing_secret=API_KEY,
        brand_id=brand_id,
        filename=filename,
        exp=exp,
        sig=sig,
    ):
        logger.warning(
            "Gallery raw denied: invalid or expired signature brand_id=%s filename=%s exp=%s",
            brand_id,
            filename,
            exp,
        )
        raise HTTPException(status_code=401, detail="Invalid or expired signature.")
    if not gallery_image_exists(brand_id, filename):
        raise HTTPException(status_code=404, detail="Image not found.")
    path = resolve_gallery_local_path(brand_id, filename)
    logger.debug("Gallery raw served brand_id=%s filename=%s", brand_id, filename)
    return FileResponse(
        path,
        media_type=_http_media_type_for_image_filename(filename),
        filename=filename,
    )


@app.delete(
    "/api/brands/{brand_id}/gallery/{filename}",
    response_model=GalleryDeleteResponse,
    dependencies=[Depends(require_rankify_api_key)],
)
async def delete_brand_gallery_image(brand_id: str, filename: str) -> GalleryDeleteResponse:
    _ = _load_brand_or_404(brand_id)
    try:
        validate_gallery_filename(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not gallery_image_exists(brand_id, filename):
        raise HTTPException(status_code=404, detail="Image not found.")
    try:
        delete_gallery_image(brand_id, filename)
    except OSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info("Gallery image deleted brand_id=%s filename=%s", brand_id, filename)
    return GalleryDeleteResponse(message="Image deleted.", filename=filename)


@app.get("/api/gallery", include_in_schema=False)
async def legacy_gallery_gone() -> None:
    raise HTTPException(
        status_code=410,
        detail="Use GET /api/brands/{brand_id}/gallery. Onboard brands via POST /api/brands or POST /api/brands/bootstrap-demo.",
    )


@app.get("/api/gallery/{filename}", include_in_schema=False)
async def legacy_gallery_item_gone(filename: str) -> None:
    raise HTTPException(status_code=410, detail="Use brand-scoped gallery URLs under /api/brands/{brand_id}/gallery/...")


@app.get("/api/gallery/raw/{filename}", include_in_schema=False)
async def legacy_raw_gone(filename: str) -> None:
    raise HTTPException(status_code=410, detail="Use GET /api/brands/{brand_id}/gallery/raw/{filename}")


@app.delete("/api/gallery/{filename}", include_in_schema=False)
async def legacy_delete_gone(filename: str) -> None:
    raise HTTPException(status_code=410, detail="Use DELETE /api/brands/{brand_id}/gallery/{filename}")
