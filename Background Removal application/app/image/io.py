"""Lossless export of final transparent images.

The hard rules enforced here:
  * never re-encode to JPEG
  * never resize the pixels we are given
  * PNG only, in the original bit depth where possible
  * metadata preservation is optional but pixel data is never degraded

Pillow cannot build a 16-bit RGBA image from pixel arrays, so 16-bit PNGs
are written by a small built-in lossless encoder (RGBA16, filter type 0).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

from app.metadata.bundle import MetadataBundle
from app.utils.exceptions import ExportError
from app.utils.log import get_logger

log = get_logger("image.io")

# -------------------------------------------------------------------------
# 16-bit lossless RGBA PNG writer (bit depth 16, color type 6)
# -------------------------------------------------------------------------


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def save_rgba16_png(
    path: str | Path,
    rgb16: np.ndarray,
    alpha16: np.ndarray,
    dpi: tuple[float, float] | None = None,
    exif_bytes: bytes | None = None,
    compression_level: int = 6,
) -> Path:
    """Write a lossless 16-bit-per-channel RGBA PNG (big-endian samples).

    Optionally embeds a pHYs (DPI) chunk and an eXIf (EXIF) chunk.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    h, w = rgb16.shape[:2]
    if rgb16.shape[:2] != alpha16.shape[:2]:
        raise ValueError("rgb and alpha must share dimensions")

    rgb16 = np.ascontiguousarray(rgb16.astype(np.uint16))
    alpha16 = np.ascontiguousarray(alpha16.astype(np.uint16))

    # scanlines: filter byte 0 then RGBA big-endian 16-bit (8 bytes/pixel)
    raw = np.empty((h, w * 8), dtype=np.uint8)
    stacked = np.concatenate([rgb16, alpha16[..., None]], axis=2)  # (h, w, 4)
    hi = (stacked >> 8).astype(np.uint8).reshape(h, w * 4)
    lo = (stacked & 0xFF).astype(np.uint8).reshape(h, w * 4)
    # target offsets: pixel p channel c -> p*8 + c*2 (two bytes, BE)
    flat = np.arange(w * 4)
    col_pair = (flat // 4) * 8 + (flat % 4) * 2
    raw[:, col_pair] = hi
    raw[:, col_pair + 1] = lo

    scanlines = np.empty((h, w * 8 + 1), dtype=np.uint8)
    scanlines[:, 0] = 0
    scanlines[:, 1:] = raw
    payload = zlib.compress(scanlines.tobytes(), compression_level)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 16, 6, 0, 0, 0)
    chunks = _chunk(b"IHDR", ihdr)

    if dpi and dpi[0] and dpi[1]:
        # pixels per meter (1 inch = 0.0254 m)
        xppm = int(round(dpi[0] / 0.0254))
        yppm = int(round(dpi[1] / 0.0254))
        chunks += _chunk(b"pHYs", struct.pack(">IIB", xppm, yppm, 1))

    if exif_bytes:
        # eXIf is a chunk carrying the raw EXIF payload (PNG 1.2+)
        chunks += _chunk(b"eXIf", exif_bytes)

    chunks += _chunk(b"IDAT", payload)
    chunks += _chunk(b"IEND", b"")

    try:
        out.write_bytes(sig + chunks)
    except OSError as exc:
        raise ExportError(f"Could not write 16-bit PNG to '{out}': {exc}") from exc
    return out


def _rgb_float_to_uint16(rgb: np.ndarray) -> np.ndarray:
    """Scale float32 [0,1] to original 16-bit range losslessly."""
    return (np.clip(rgb, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)


def _rgb_float_to_uint8(rgb: np.ndarray) -> np.ndarray:
    return (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def assemble_rgba(
    rgb: np.ndarray,
    alpha: np.ndarray,
    bit_depth: int | None = None,
) -> Image.Image:
    """Build a PIL RGBA (8-bit) image from float RGB + float alpha.

    For 16-bit sources call :func:`save_rgba16_png` instead.
    """
    if rgb.shape[:2] != alpha.shape[:2]:
        raise ValueError(
            f"rgb {rgb.shape[:2]} and alpha {alpha.shape[:2]} must match"
        )

    if bit_depth == 16:
        raise ValueError("16-bit RGBA is not a supported PIL image mode; use save_rgba16_png")

    rgb8 = _rgb_float_to_uint8(rgb)
    a8 = (np.clip(alpha, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    stacked = np.concatenate([rgb8, a8[..., None]], axis=2)
    return Image.fromarray(stacked, mode="RGBA")


def save_png(
    image: Image.Image,
    path: str | Path,
    metadata: MetadataBundle | None = None,
    preserve_metadata: bool = True,
    optimize: bool = True,
    compression_level: int = 9,
) -> Path:
    """Save an RGBA image as an optimized lossless PNG."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if image.mode == "RGBA":
        final = image
    else:
        final = image.convert("RGBA")

    params: dict = {}
    if metadata is not None:
        params.update(metadata.apply_to_png(final, preserve_metadata))

    params["compress_level"] = compression_level

    try:
        final.save(
            out,
            format="PNG",
            optimize=optimize,
            **params,
        )
    except Exception as exc:
        raise ExportError(f"Could not write PNG to '{out}': {exc}") from exc

    if not out.exists() or out.stat().st_size == 0:
        raise ExportError(f"Output PNG is empty or missing: {out}")

    return out


def export_transparent_png(
    rgb_float: np.ndarray,
    alpha_float: np.ndarray,
    path: str | Path,
    bit_depth: int | None = None,
    metadata: MetadataBundle | None = None,
    preserve_metadata: bool = True,
    optimize: bool = True,
) -> Path:
    """One-stop lossless PNG export from float RGB + float alpha."""
    if bit_depth == 16:
        rgb16 = _rgb_float_to_uint16(rgb_float)
        a16 = (np.clip(alpha_float, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)
        dpi = metadata.dpi if (metadata and preserve_metadata) else None
        exif = metadata.exif_bytes if (metadata and preserve_metadata and metadata.exif_bytes) else None
        if exif is not None and not isinstance(exif, bytes):
            exif = None
        return save_rgba16_png(path, rgb16, a16, dpi=dpi, exif_bytes=exif)

    pil_image = assemble_rgba(rgb_float, alpha_float, bit_depth=bit_depth)
    return save_png(
        pil_image,
        path,
        metadata=metadata,
        preserve_metadata=preserve_metadata,
        optimize=optimize,
    )


def write_tiff_composite(
    rgb_float: np.ndarray,
    alpha_float: np.ndarray,
    path: str | Path,
    metadata: MetadataBundle | None = None,
    preserve_metadata: bool = True,
) -> Path:
    """Write an RGBA TIFF (lossless) for workflows that need TIFF output."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image = assemble_rgba(rgb_float, alpha_float, bit_depth=None).convert("RGBA")
    params: dict = {}
    if metadata is not None:
        params.update(metadata.apply_to_tiff(image, preserve_metadata))
    params["compression"] = "tiff_adobe_deflate"
    try:
        image.save(out, format="TIFF", save_all=False, **params)
    except Exception as exc:
        raise ExportError(f"Could not write TIFF to '{out}': {exc}") from exc
    return out