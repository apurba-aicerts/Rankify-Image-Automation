"""
Central logging setup for the Rankify backend.

Set ``LOG_LEVEL`` (default ``INFO``): DEBUG, INFO, WARNING, ERROR, CRITICAL.
Call :func:`configure_logging` once at process startup (e.g. from ``main``).
"""

from __future__ import annotations

import logging
import os
import sys


class _SuppressVerboseHttpSdkLogs(logging.Filter):
    """Drop DEBUG/INFO from HTTP clients and OpenAI SDK (avoids base64 in the terminal)."""

    _QUIET_PREFIXES = ("openai", "httpx", "httpcore", "urllib3")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        return not any(record.name.startswith(p) for p in self._QUIET_PREFIXES)


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
        handler.addFilter(_SuppressVerboseHttpSdkLogs())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            if not any(isinstance(f, _SuppressVerboseHttpSdkLogs) for f in handler.filters):
                handler.addFilter(_SuppressVerboseHttpSdkLogs())

    root.setLevel(level)

    for name in (
        "urllib3",
        "urllib3.connectionpool",
        "httpx",
        "httpcore",
        "openai",
        "openai._base_client",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in list(logging.root.manager.loggerDict):
        if isinstance(name, str) and name.startswith("openai"):
            logging.getLogger(name).setLevel(logging.WARNING)
