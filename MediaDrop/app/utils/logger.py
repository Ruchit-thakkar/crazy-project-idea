"""Structured logging setup for MediaDrop."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_dir: Path | None = None, debug: bool = False) -> logging.Logger:
    """Initialize application logger with rotating file and console handlers."""
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mediadrop.log"

    logger = logging.getLogger("MediaDrop")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Avoid duplicate handlers if reconfigured
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (max 5 MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(console_handler)

    return logger


logger = logging.getLogger("MediaDrop")
