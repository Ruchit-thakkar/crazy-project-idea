"""Image loading that preserves original data as exactly as possible.

Strategy:
  * decode the file exactly once at native resolution
  * apply EXIF orientation so the image is upright
  * convert pixel data to an internal float32 RGB (0..1) representation,
    tracking the original bit depth so export can restore exact values
The float32 RGB form is monotonic w.r.t. the original uint8/uint16 values
(float32 has a 24-bit mantissa, so every 8- and 16-bit sample maps exactly).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageCms, ImageOps

from app.image.info import ImageInfo, analyze
from app.utils.exceptions import CorruptImageError, UnsupportedImageError, ImageLoadError
from app.utils.log import get_logger

log = get_logger("image.loader")

_ORIENTATION_TAG = 274


def _apply_exif_orientation(image: Image.Image) -> Image.Image:
    try:
        exif = image.getexif()
        orientation = int(exif.get(_ORIENTATION_TAG, 1))
    except (AttributeError, ValueError, TypeError):
        orientation = 1

    transform_map = {
        2: Image.Transpose.FLIP_LEFT_RIGHT,
        3: Image.Transpose.ROTATE_180,
        4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE,
        6: Image.Transpose.ROTATE_270,
        7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_90,
    }
    if orientation in transform_map:
        image = image.transpose(transform_map[orientation])
    return image


def _to_rgb_float(image: Image.Image) -> np.ndarray:
    """Return HxWx3 float32 in [0, 1], stripping but honoring alpha."""
    mode = image.mode
    arr: np.ndarray | None = None

    if mode in ("RGB", "L", "1", "I", "I;16", "I;16B", "F", "P"):
        arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    elif mode == "RGBA":
        rgba = np.asarray(image, dtype=np.float32) / 255.0
        arr = rgba[..., :3]
    elif mode == "LA":
        la = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        arr = la[..., :3]
    elif mode == "CMYK":
        arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    elif mode == "YCbCr":
        arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    else:
        arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0

    return np.clip(arr, 0.0, 1.0).astype(np.float32, copy=False)


@dataclass
class LoadedImage:
    rgb: np.ndarray            # HxWx3 float32 in [0, 1], oriented, full resolution
    info: ImageInfo
    bit_depth: int | None
    icc_profile: bytes | None
    exif: dict | None
    is_16bit: bool = False
    source_mode: str = ""
    exif_bytes: bytes | None = None

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.rgb.shape[:2]
        return (w, h)


def load(path: str | Path, apply_orientation: bool = True) -> LoadedImage:
    """Decode an image at full resolution preserving as much as possible."""
    p = Path(path)
    info = analyze(p)

    try:
        with Image.open(p) as img:
            source_mode = img.mode

            icc = img.info.get("icc_profile")
            bits = info.bit_depth
            is_16bit = bits == 16

            try:
                exif = img.getexif()
                exif_dict = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()} if exif else {}
            except Exception:
                exif_dict = {}
            try:
                exif_bytes = img.info.get("exif") or (img.getexif().tobytes() if img.getexif() else None)
            except Exception:
                exif_bytes = None

            # Defer the actual pixel conversion into float RGB.
            if apply_orientation:
                img = _apply_exif_orientation(img)

            # For 16-bit modes, convert through the raw band data so we keep values.
            if mode_to_16bit(source_mode):
                is_16bit = True
                bits = 16
                try:
                    rgb16 = _to_rgb16_float(img)
                except Exception as exc:
                    raise CorruptImageError(
                        f"Could not decode 16-bit image '{p.name}': {exc}"
                    ) from exc
                rgb = rgb16
            else:
                rgb = _to_rgb_float(img)

            # Recompute effective size after orientation.
            h, w = rgb.shape[:2]
            info.effective_size = (w, h)

            if rgb.size == 0:
                raise CorruptImageError(f"Image '{p.name}' decoded to zero pixels.")

            return LoadedImage(
                rgb=rgb,
                info=info,
                bit_depth=bits,
                icc_profile=icc,
                exif=exif_dict,
                is_16bit=is_16bit,
                source_mode=source_mode,
                exif_bytes=exif_bytes,
            )
    except ImageLoadError:
        raise
    except Exception as exc:
        raise CorruptImageError(f"Corrupt or undecodable image '{p.name}': {exc}") from exc


def mode_to_16bit(mode: str) -> bool:
    return mode in ("I;16", "I;16B", "I;16N") or mode.startswith("I;16")


def _to_rgb16_float(image: Image.Image) -> np.ndarray:
    """Convert an original 16-bit image to float32 RGB [0,1] without band loss.

    Preserves the 16-bit storage of grayscale (I;16 -> replicates to RGB) and
    RGB 5-5-5 / variants are rare and handled by 'converted' fallback.
    """
    mode = image.mode
    if mode in ("I;16", "I;16B", "I;16N"):
        gray = np.asarray(image, dtype=np.uint16).astype(np.float32) / 65535.0
        rgb = np.repeat(gray[..., None], 3, axis=2)
        return np.clip(rgb, 0.0, 1.0).astype(np.float32)
    # Other 16-bit variants -> use Pillow's own conversion (best effort).
    return np.clip(np.asarray(image.convert("RGB"), dtype=np.float32) / 65535.0, 0.0, 1.0)


def load_preview(path: str | Path, max_side: int = 1024) -> np.ndarray:
    """Cheap downscaled RGB uint8 preview, used by UI and model selectors.

    Never used for final output.
    """
    try:
        with Image.open(path) as img:
            img = _apply_exif_orientation(img)
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            return np.asarray(img.convert("RGB"), dtype=np.uint8)
    except Exception:
        return np.zeros((1, 1, 3), dtype=np.uint8)