"""
Central logging setup for the Rankify backend.

Set ``LOG_LEVEL`` (default ``INFO``): DEBUG, INFO, WARNING, ERROR, CRITICAL.
Call :func:`configure_logging` once at process startup (e.g. from ``main``).
"""

from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    """Attach a stderr handler to the root logger if none exists; set level from env."""
    level_name = (os.getenv("LOG_LEVEL", "INFO") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
    root.setLevel(level)

    for name in ("urllib3", "urllib3.connectionpool", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
