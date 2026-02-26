"""
FastAPI backend for AI CERTs® Image Generator.

Endpoints
─────────
POST   /api/generate              – Generate carousel images (JSON body)
POST   /api/generate-with-logo    – Generate with custom logo (multipart form)
GET    /api/models                – List available Gemini models
GET    /api/image-sizes           – List available image sizes & aspect ratios
GET    /api/gallery               – List every image in the gallery (from S3)
GET    /api/gallery/{filename}    – Download / view a single image (presigned S3 URL)
DELETE /api/gallery/{filename}    – Remove a single image from S3
GET    /health                    – Health check

Authentication
──────────────
Every request must include the header:
    x-api-key: <value from .env → API_KEY>

Image Lifecycle
───────────────
Images are generated locally (temp), uploaded to AWS S3, then the local
copy is removed.  A background scheduler purges S3 objects older than
IMAGE_TTL_HOURS automatically.
"""

import os
import uuid
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from botocore.exceptions import ClientError
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Header,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image
from dotenv import load_dotenv

from generator import AICertsImageGenerator
from prompts import BRAND_PROMPT, build_content_prompt
from helpers.s3_helper import (
    upload_file as s3_upload,
    generate_presigned_url as s3_presigned_url,
    delete_object as s3_delete,
    head_object as s3_head,
    list_objects as s3_list,
    delete_objects_older_than as s3_cleanup,
    s3_key,
    S3_BUCKET_NAME,
    S3_PREFIX,
)

# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────
load_dotenv()

DEFAULT_LOGO_PATH = Path("assets/default_logo.jpg")

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
    """Periodically delete S3 objects older than IMAGE_TTL_HOURS."""
    while True:
        try:
            s3_cleanup(IMAGE_TTL_HOURS)
        except Exception:
            pass  # don't crash the scheduler
        await asyncio.sleep(900)  # run every 15 minutes


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
    version="2.0.0",
    description="Generate branded carousel images for AI CERTs® social media. Images stored on AWS S3.",
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
    s3_key: str
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
def _build_image_meta_s3(filename: str, size_bytes: int, last_modified: datetime) -> ImageMeta:
    """Build ImageMeta from S3 object metadata."""
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last_modified).total_seconds() / 3600
    presigned_url = s3_presigned_url(filename)
    return ImageMeta(
        filename=filename,
        url=presigned_url,
        s3_key=s3_key(filename),
        size_bytes=size_bytes,
        created_at=last_modified.isoformat(),
        age_hours=round(age, 2),
    )


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "storage": "s3",
        "s3_bucket": S3_BUCKET_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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

        # Generate to a temporary local file, then upload to S3
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            generator.generate_and_save(
                brand_prompt=BRAND_PROMPT,
                content_prompt=content_prompt,
                logo=logo_image,
                model=_model,
                aspect_ratio=_ratio,
                image_size=_size if _model == "gemini-3-pro-image-preview" else None,
                output_path=tmp_path,
            )

            # Upload to S3
            s3_upload(tmp_path, filename)

            # Get file size before removing local copy
            file_size = os.path.getsize(tmp_path)
        except ClientError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"S3 upload failed for image {i}: {str(exc)}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Image generation failed for image {i}: {str(exc)}",
            )
        finally:
            # Always clean up the local temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        meta = _build_image_meta_s3(
            filename=filename,
            size_bytes=file_size,
            last_modified=datetime.now(timezone.utc),
        )
        generated.append(meta)

    per_price = _get_image_price(_model, _size)
    total_price = round(per_price * _num, 3)

    return GenerateResponse(
        images=generated,
        model_used=_model,
        per_image_price_usd=per_price,
        total_price_usd=total_price,
        message=f"Successfully generated {_num} image(s) and uploaded to S3.",
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
    """Return metadata for every image currently stored in S3."""
    try:
        s3_objects = s3_list()
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list S3 objects: {str(exc)}")

    images: list[ImageMeta] = []
    # Sort newest first
    s3_objects.sort(key=lambda o: o["LastModified"], reverse=True)

    for obj in s3_objects:
        key: str = obj["Key"]
        # Skip the prefix-only entry (folder marker)
        if key == S3_PREFIX:
            continue
        filename = key.removeprefix(S3_PREFIX)
        if not filename:
            continue
        # Only include image files
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        images.append(
            _build_image_meta_s3(
                filename=filename,
                size_bytes=obj["Size"],
                last_modified=obj["LastModified"],
            )
        )

    return GalleryResponse(total=len(images), images=images)


# ──────────────────────────────────────────────
# GET /api/gallery/{filename}
# ──────────────────────────────────────────────
@app.get(
    "/api/gallery/{filename}",
    dependencies=[Depends(verify_api_key)],
    summary="Download / view a single image (redirects to presigned S3 URL)",
)
async def get_image(filename: str):
    """
    Returns a temporary presigned S3 URL for the requested image.
    The client is redirected (HTTP 307) to the presigned URL.
    """
    try:
        s3_head(filename)  # verify it exists
    except ClientError:
        raise HTTPException(status_code=404, detail="Image not found in S3.")

    presigned_url = s3_presigned_url(filename)
    return RedirectResponse(url=presigned_url, status_code=307)


# ──────────────────────────────────────────────
# DELETE /api/gallery/{filename}
# ──────────────────────────────────────────────
@app.delete(
    "/api/gallery/{filename}",
    response_model=DeleteResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Delete a single image from S3",
)
async def delete_image(filename: str):
    """Delete an image from the S3 bucket."""
    try:
        s3_head(filename)  # verify it exists
    except ClientError:
        raise HTTPException(status_code=404, detail="Image not found in S3.")

    try:
        s3_delete(filename)
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to delete from S3: {str(exc)}")

    return DeleteResponse(message="Image deleted successfully from S3.", filename=filename)
