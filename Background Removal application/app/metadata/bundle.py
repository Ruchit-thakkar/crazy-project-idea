"""Metadata preservation (EXIF, DPI, ICC color profile) for round-trips.

The goal is to carry original metadata into the exported PNG without
corrupting already-preserved detail.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import ExifTags, Image, ImageCms

from app.utils.log import get_logger

log = get_logger("metadata")


@dataclass
class MetadataBundle:
    exif_bytes: bytes | None = None
    dpi: tuple[float, float] | None = None
    icc_profile: bytes | None = None

    @classmethod
    def from_loaded(cls, loaded) -> "MetadataBundle":
        icc = getattr(loaded, "icc_profile", None)
        dpi = None
        if loaded.info and getattr(loaded.info, "dpi", None):
            dpi = loaded.info.dpi
        return cls(
            exif_bytes=getattr(loaded, "exif_bytes", None),
            dpi=dpi,
            icc_profile=icc,
        )

    @classmethod
    def from_image_path(cls, path: str | Path) -> "MetadataBundle":
        try:
            with Image.open(path) as img:
                exif = img.info.get("exif") or (img.getexif().tobytes() if img.getexif() else None)
                dpi = None
                d = img.info.get("dpi")
                if isinstance(d, (tuple, list)) and len(d) == 2:
                    try:
                        dpi = (float(d[0]), float(d[1]))
                    except (TypeError, ValueError):
                        dpi = None
                return cls(
                    exif_bytes=exif,
                    dpi=dpi,
                    icc_profile=img.info.get("icc_profile"),
                )
        except Exception:
            return cls()

    def apply_to_png(self, image: Image.Image, preserve: bool) -> dict:
        """Return PNG save-params encoding the preserved metadata."""
        params = {}
        if not preserve:
            return params
        if self.icc_profile:
            params["icc_profile"] = self.icc_profile
        if self.exif_bytes:
            try:
                params["exif"] = self.exif_bytes
            except Exception:
                log.debug("could not embed EXIF into PNG", exc_info=True)
        if self.dpi and self.dpi[0] and self.dpi[1]:
            params["dpi"] = self.dpi
        return params

    def apply_to_tiff(self, image: Image.Image, preserve: bool) -> dict:
        """Return TIFF save-params encoding preserved metadata."""
        params = {}
        if not preserve:
            return params
        if self.icc_profile:
            params["icc_profile"] = self.icc_profile
        if self.exif_bytes:
            try:
                params["exif"] = self.exif_bytes
            except Exception:
                pass
        if self.dpi and self.dpi[0] and self.dpi[1]:
            params["dpi"] = self.dpi
        return params