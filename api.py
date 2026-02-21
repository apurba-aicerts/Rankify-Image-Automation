"""
FastAPI backend for AI CERTs® Image Generator.

Endpoints
─────────
POST   /api/generate              – Generate carousel images (JSON body)
POST   /api/generate-with-logo    – Generate with custom logo (multipart form)
GET    /api/models                – List available Gemini models
GET    /api/image-sizes           – List available image sizes & aspect ratios
GET    /api/gallery               – List every image in the gallery
GET    /api/gallery/{filename}    – Download / view a single image
DELETE /api/gallery/{filename}    – Remove a single image
GET    /health                    – Health check

Authentication
──────────────
Every request must include the header:
    x-api-key: <value from .env → API_KEY>

Image Lifecycle
───────────────
Images are stored on disk under `outputs/`.
A background scheduler purges files older than 24 hours automatically.
"""

import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Header,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image
from dotenv import load_dotenv

from generator import AICertsImageGenerator
from prompts import BRAND_PROMPT, build_content_prompt

# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────
load_dotenv()

OUTPUT_DIR = Path("outputs")
DEFAULT_LOGO_PATH = Path("assets/default_logo.jpg")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY: str = os.getenv("API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
IMAGE_TTL_HOURS: int = int(os.getenv("IMAGE_TTL_HOURS", "24"))

ALLOWED_MODELS = [
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
]

ALLOWED_ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "21:9",
]

ALLOWED_IMAGE_SIZES = ["1K", "2K", "4K"]

# ── Pricing table (same as Streamlit app) ─────
PRICE_TABLE = {
    "gemini-2.5-flash-image": 0.039,
    "gemini-3-pro-image-preview": {
        "1K": 0.134,
        "2K": 0.134,
        "4K": 0.24,
    },
}


def _get_image_price(model: str, resolution: str = "2K") -> float:
    if model == "gemini-3-pro-image-preview":
        return PRICE_TABLE[model].get(resolution, 0.134)
    return PRICE_TABLE.get(model, 0.039)


# ──────────────────────────────────────────────
# Background cleanup scheduler
# ──────────────────────────────────────────────
async def _cleanup_old_images():
    """Periodically delete images older than IMAGE_TTL_HOURS."""
    while True:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=IMAGE_TTL_HOURS)
        for file in OUTPUT_DIR.iterdir():
            if file.is_file() and file.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                mtime = datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    try:
                        file.unlink()
                    except OSError:
                        pass
        await asyncio.sleep(3600)  # run every hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    task = asyncio.create_task(_cleanup_old_images())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ──────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────
app = FastAPI(
    title="AI CERTs® Image Generator API",
    version="1.0.0",
    description="Generate branded carousel images for AI CERTs® social media.",
    lifespan=lifespan,
)

# CORS – allow all origins during MVP; tighten later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Auth dependency
# ──────────────────────────────────────────────
async def verify_api_key(x_api_key: str = Header(..., alias="x-api-key")):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured on the server.",
        )
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────
class GenerateRequest(BaseModel):
    content: str = Field(..., description="Post content in TITLE / SUBTITLE / BODY / CTA format.")
    model_name: str = Field(
        default="gemini-3-pro-image-preview",
        description="Gemini model to use.",
    )
    num_images: int = Field(default=1, ge=1, le=10, description="Number of images to generate (1-10).")
    aspect_ratio: str = Field(default="1:1", description="Aspect ratio.")
    image_size: Optional[str] = Field(
        default="2K",
        description="Image resolution (only for gemini-3-pro-image-preview). Options: 1K, 2K, 4K.",
    )


class ImageMeta(BaseModel):
    filename: str
    url: str
    size_bytes: int
    created_at: str
    age_hours: float


class GenerateResponse(BaseModel):
    images: List[ImageMeta]
    model_used: str
    per_image_price_usd: float
    total_price_usd: float
    message: str


class GalleryResponse(BaseModel):
    total: int
    images: List[ImageMeta]


class DeleteResponse(BaseModel):
    message: str
    filename: str


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _build_image_meta(filepath: Path, base_url: str = "/api/gallery") -> ImageMeta:
    stat = filepath.stat()
    created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    age = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    return ImageMeta(
        filename=filepath.name,
        url=f"{base_url}/{filepath.name}",
        size_bytes=stat.st_size,
        created_at=created.isoformat(),
        age_hours=round(age, 2),
    )


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ──────────────────────────────────────────────
# GET /api/models  – available model names
# ──────────────────────────────────────────────
@app.get(
    "/api/models",
    dependencies=[Depends(verify_api_key)],
    summary="List available Gemini models",
)
async def list_models():
    """Return every model name the frontend can pass to the generate endpoint."""
    models = []
    for m in ALLOWED_MODELS:
        price = PRICE_TABLE.get(m)
        if isinstance(price, dict):
            models.append({
                "model_name": m,
                "supports_image_size": True,
                "pricing": price,
            })
        else:
            models.append({
                "model_name": m,
                "supports_image_size": False,
                "price_per_image_usd": price,
            })
    return {"models": models}


# ──────────────────────────────────────────────
# GET /api/image-sizes  – available image resolutions
# ──────────────────────────────────────────────
@app.get(
    "/api/image-sizes",
    dependencies=[Depends(verify_api_key)],
    summary="List available image sizes / resolutions",
)
async def list_image_sizes():
    """Return the supported image resolutions and which models they apply to."""
    return {
        "image_sizes": ALLOWED_IMAGE_SIZES,
        "note": "Image size selection applies only to gemini-3-pro-image-preview. "
                "For gemini-2.5-flash-image the size is managed automatically.",
        "aspect_ratios": ALLOWED_ASPECT_RATIOS,
    }


# ──────────────────────────────────────────────
# Shared generation logic
# ──────────────────────────────────────────────
def _run_generation(
    _content: str,
    _model: str,
    _num: int,
    _ratio: str,
    _size: str,
    logo_image: Image.Image,
) -> GenerateResponse:
    """Core generation logic shared by JSON and multipart endpoints."""

    if _model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model. Choose from {ALLOWED_MODELS}")

    if _ratio not in ALLOWED_ASPECT_RATIOS:
        raise HTTPException(status_code=400, detail=f"Invalid aspect_ratio. Choose from {ALLOWED_ASPECT_RATIOS}")

    if _model == "gemini-3-pro-image-preview" and _size not in ALLOWED_IMAGE_SIZES:
        raise HTTPException(status_code=400, detail=f"Invalid image_size. Choose from {ALLOWED_IMAGE_SIZES}")

    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not configured on the server.")

    generator = AICertsImageGenerator(GOOGLE_API_KEY)
    content_prompt = build_content_prompt(_content)

    generated: list[ImageMeta] = []
    batch_id = uuid.uuid4().hex[:8]

    for i in range(1, _num + 1):
        filename = f"aicerts_{batch_id}_{i}.png"
        output_path = OUTPUT_DIR / filename

        try:
            generator.generate_and_save(
                brand_prompt=BRAND_PROMPT,
                content_prompt=content_prompt,
                logo=logo_image,
                model=_model,
                aspect_ratio=_ratio,
                image_size=_size if _model == "gemini-3-pro-image-preview" else None,
                output_path=str(output_path),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Image generation failed for image {i}: {str(exc)}",
            )

        generated.append(_build_image_meta(output_path))

    per_price = _get_image_price(_model, _size)
    total_price = round(per_price * _num, 3)

    return GenerateResponse(
        images=generated,
        model_used=_model,
        per_image_price_usd=per_price,
        total_price_usd=total_price,
        message=f"Successfully generated {_num} image(s).",
    )


# ──────────────────────────────────────────────
# POST /api/generate  (JSON body – no logo upload)
# ──────────────────────────────────────────────
@app.post(
    "/api/generate",
    response_model=GenerateResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Generate carousel images (JSON)",
)
async def generate_images_json(body: GenerateRequest):
    """
    Generate branded AI CERTs® carousel images.

    Send a JSON body. Uses the default logo stored on the server.
    """
    logo_image = Image.open(DEFAULT_LOGO_PATH)
    return _run_generation(
        _content=body.content,
        _model=body.model_name,
        _num=body.num_images,
        _ratio=body.aspect_ratio,
        _size=body.image_size or "2K",
        logo_image=logo_image,
    )


# ──────────────────────────────────────────────
# POST /api/generate-with-logo  (multipart form – optional logo upload)
# ──────────────────────────────────────────────
@app.post(
    "/api/generate-with-logo",
    response_model=GenerateResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Generate carousel images with custom logo (multipart form)",
)
async def generate_images_form(
    content: str = Form(..., description="Post content in TITLE / SUBTITLE / BODY / CTA format."),
    model_name: str = Form("gemini-3-pro-image-preview"),
    num_images: int = Form(1, ge=1, le=10),
    aspect_ratio: str = Form("1:1"),
    image_size: str = Form("2K"),
    logo: Optional[UploadFile] = File(None, description="Custom logo image (png/jpg). Falls back to default."),
):
    """
    Generate branded AI CERTs® carousel images with an optional custom logo.

    Use **multipart/form-data** for this endpoint.
    """
    logo_image = Image.open(logo.file) if logo else Image.open(DEFAULT_LOGO_PATH)
    return _run_generation(
        _content=content,
        _model=model_name,
        _num=num_images,
        _ratio=aspect_ratio,
        _size=image_size,
        logo_image=logo_image,
    )


# ──────────────────────────────────────────────
# GET /api/gallery
# ──────────────────────────────────────────────
@app.get(
    "/api/gallery",
    response_model=GalleryResponse,
    dependencies=[Depends(verify_api_key)],
    summary="List all images in the gallery",
)
async def list_gallery():
    """Return metadata for every image currently stored on the server."""
    images: list[ImageMeta] = []
    for f in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            images.append(_build_image_meta(f))
    return GalleryResponse(total=len(images), images=images)


# ──────────────────────────────────────────────
# GET /api/gallery/{filename}
# ──────────────────────────────────────────────
@app.get(
    "/api/gallery/{filename}",
    dependencies=[Depends(verify_api_key)],
    summary="Download / view a single image",
)
async def get_image(filename: str):
    filepath = OUTPUT_DIR / filename
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(filepath, media_type="image/png", filename=filename)


# ──────────────────────────────────────────────
# DELETE /api/gallery/{filename}
# ──────────────────────────────────────────────
@app.delete(
    "/api/gallery/{filename}",
    response_model=DeleteResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Delete a single image",
)
async def delete_image(filename: str):
    filepath = OUTPUT_DIR / filename
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    filepath.unlink()
    return DeleteResponse(message="Image deleted successfully.", filename=filename)
