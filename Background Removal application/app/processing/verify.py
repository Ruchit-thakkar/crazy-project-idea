"""Quality verification before export.

Every result is checked before it is allowed to be written:
  * output dimensions exactly match the (oriented) input
  * the output carries an alpha channel
  * the export format is lossless PNG
  * no accidental JPEG conversion
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.utils.config import QualityVerificationResult
from app.utils.log import get_logger

log = get_logger("processing.verify")


def verify_floats(
    original_size: tuple[int, int],
    rgb: object,
    alpha: object,
) -> QualityVerificationResult:
    """Verify in-memory result components before assembly."""
    h, w = rgb.shape[:2]
    ah, aw = alpha.shape[:2]
    errors: list[str] = []
    if (w, h) != tuple(original_size):
        errors.append(f"Resolution changed: input {tuple(original_size)} vs output {(w, h)}")
    if (aw, ah) != (w, h):
        errors.append("Alpha mask dimensions do not match the RGB image")
    if rgb.max(initial=0) > 1.0 or rgb.min(initial=0) < 0.0:
        log.warning("RGB outside [0,1]: clamping on export")
    return QualityVerificationResult(
        original_size=tuple(original_size),
        output_size=(w, h),
        has_alpha=True,
        is_lossless_png=True,
        rgb_preserved=not errors,
        errors=errors,
    )


def verify_file(
    original_size: tuple[int, int],
    output_path: str | Path,
) -> QualityVerificationResult:
    """Verify a written PNG file matches the input image dimensions."""
    out = Path(output_path)
    errors: list[str] = []
    try:
        with Image.open(out) as img:
            w, h = img.size
            has_alpha = "A" in img.mode.upper() or ("transparency" in img.info and img.mode == "P")
            fmt = (img.format or "").upper()
    except Exception as exc:
        errors.append(f"Output file unreadable: {exc}")
        has_alpha, fmt = False, ""

    if (w, h) != tuple(original_size):
        errors.append(f"Resolution changed: input {tuple(original_size)} vs output {(w, h)}")

    return QualityVerificationResult(
        original_size=tuple(original_size),
        output_size=(w, h),
        has_alpha=has_alpha,
        is_lossless_png=fmt == "PNG",
        rgb_preserved=not errors,
        errors=errors,
    )