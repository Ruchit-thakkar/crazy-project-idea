"""Logging helpers for the whole application."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def setup_logging(
    app_dir: str | Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configure a single root logger for the app.

    Returns the application logger. Safe to call multiple times.
    """
    global _configured
    logger = logging.getLogger("bgremove")

    if _configured:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT)

    if console:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if app_dir is not None:
        log_dir = Path(app_dir)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "bgremove.log",
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            logger.warning("Could not create log file in %s", log_dir)

    logger.propagate = False
    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the application logger."""
    return logging.getLogger(f"bgremove.{name}")


def debug_enabled() -> bool:
    return logging.getLogger("bgremove").isEnabledFor(logging.DEBUG)