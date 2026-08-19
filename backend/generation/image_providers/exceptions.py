"""Shared errors when an image model returns no raster."""

from __future__ import annotations


class ImageProviderNoOutput(Exception):
    """Provider HTTP succeeded but no image bytes were returned."""

    __slots__ = ("finish_reason", "provider")

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        finish_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.finish_reason = finish_reason
