"""
AWS S3 helper functions for the AI CERTs® Image Generator.

Handles all interactions with Amazon S3:
  • client initialisation
  • upload / download / delete / list / head
  • presigned-URL generation
  • TTL-based cleanup of old objects
"""

import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Configuration (read once at import time)
# ──────────────────────────────────────────────
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME: str = os.getenv("AWS_S3_BUCKET_NAME", "aicerts-image-generator")
S3_PREFIX: str = "generated-images/"  # key prefix inside the bucket
PRESIGNED_URL_EXPIRY: int = 3600  # seconds (1 hour)

# ──────────────────────────────────────────────
# S3 client (module-level singleton)
# ──────────────────────────────────────────────
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID or None,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY or None,
)


# ──────────────────────────────────────────────
# Key helpers
# ──────────────────────────────────────────────
def s3_key(filename: str) -> str:
    """Return the full S3 object key for a given filename."""
    return f"{S3_PREFIX}{filename}"


# ──────────────────────────────────────────────
# CRUD operations
# ──────────────────────────────────────────────
def upload_file(local_path: str, filename: str) -> str:
    """
    Upload a local file to S3.

    Returns the S3 object key.
    Raises ``botocore.exceptions.ClientError`` on failure.
    """
    key = s3_key(filename)
    s3_client.upload_file(
        Filename=local_path,
        Bucket=S3_BUCKET_NAME,
        Key=key,
        ExtraArgs={"ContentType": "image/png"},
    )
    return key


def generate_presigned_url(filename: str, expiry: int = PRESIGNED_URL_EXPIRY) -> str:
    """Generate a presigned GET URL for the given filename."""
    key = s3_key(filename)
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET_NAME, "Key": key},
        ExpiresIn=expiry,
    )


def delete_object(filename: str) -> None:
    """Delete a single object from S3 by filename."""
    key = s3_key(filename)
    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=key)


def head_object(filename: str) -> dict:
    """
    Return metadata for a single S3 object.

    Raises ``botocore.exceptions.ClientError`` (404) if the object
    does not exist.
    """
    key = s3_key(filename)
    return s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=key)


def list_objects() -> list[dict]:
    """
    List all objects under ``S3_PREFIX``.

    Returns a list of dicts with keys ``Key``, ``Size``,
    ``LastModified`` (as returned by the S3 API).
    """
    objects: list[dict] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            objects.append(obj)
    return objects


# ──────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────
def delete_objects_older_than(hours: int) -> int:
    """
    Delete every object under ``S3_PREFIX`` whose ``LastModified``
    timestamp is older than *hours* hours.

    Returns the number of objects deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    deleted = 0
    for obj in list_objects():
        last_modified = obj["LastModified"]
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=timezone.utc)
        if last_modified < cutoff:
            try:
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])
                deleted += 1
            except ClientError:
                pass
    return deleted
