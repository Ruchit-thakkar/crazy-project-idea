"""Resource and asset locator compatible with source and PyInstaller bundles."""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Return base directory whether running from script or PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore
    return Path(__file__).resolve().parent.parent.parent


def get_asset_path(relative_path: str) -> Path:
    """Return absolute path to an asset."""
    base = get_base_path()
    return base / "assets" / relative_path
