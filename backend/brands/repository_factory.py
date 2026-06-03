"""Select filesystem or database brand persistence."""

from __future__ import annotations

from typing import Union

from brands.repository import BrandRepository
from db.config import database_enabled
from db.repositories import BrandDbRepository

BrandRepositoryLike = Union[BrandRepository, BrandDbRepository]


def get_brand_repository() -> BrandRepositoryLike:
    if database_enabled():
        return BrandDbRepository()
    return BrandRepository()
