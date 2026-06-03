"""Database configuration from environment."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def database_enabled() -> bool:
    return bool(database_url())
