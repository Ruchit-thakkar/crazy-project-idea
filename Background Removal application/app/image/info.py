"""Automatic detection of image properties (format, size, mode, bit depth)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFile

from app.utils.exceptions import CorruptImageError, UnsupportedImageError
from app.utils.log import get_logger

log = get_logger("image.info")

ImageFile.LOAD_TRUNCATED_IMAGES = False

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".tif",
    ".tiff",
    ".bmp",
}

_MODE_LABELS = {
    "1": "1-bit Black & White",
    "L": "8-bit Grayscale",
    "LA": "8-bit Grayscale + Alpha",
    "P": "8-bit Palette",
    "RGB": "8-bit RGB",
    "RGBA": "8-bit RGBA",
    "CMYK": "8-bit CMYK",
    "YCbCr": "8-bit YCbCr",
    "I": "32-bit Integer",
    "I;16": "16-bit Integer",
    "I;16B": "16-bit Integer (big-endian)",
    "F": "32-bit Float",
    "LAB": "8-bit Lab",
    "HSV": "8-bit HSV",
}


def supported_extension(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


@dataclass
class ImageInfo:
    path: str
    format: str
    width: int  # as stored
    height: int
    effective_size: tuple[int, int]  # after EXIF orientation is applied
    color_mode: str
    bit_depth: int | None
    orientation: int
    has_alpha: bool
    icc_profile: bool
    dpi: tuple[float, float] | None
    exif_available: bool
    megapixels: float

    def describe(self) -> str:
        bits = f"{self.bit_depth}-bit" if self.bit_depth else "unknown bit depth"
        return (
            f"{self.format}, {self.effective_size[0]} x {self.effective_size[1]}, "
            f"{self.color_mode}, {bits}"
        )


def _tiff_bits(image: Image.Image) -> int | None:
    try:
        tags = image.tag_v2
        bits = tags.get(258)  # BitsPerSample
        if isinstance(bits, (tuple, list)) and bits:
            return int(bits[0])
        if bits is not None:
            return int(bits)
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    return None


def _bits_per_channel(image: Image.Image, fmt: str) -> int | None:
    if fmt == "PNG":
        info = image.info.get("bits")
        if isinstance(info, int):
            return info
        mode = image.mode
        if mode in ("1",):
            return 1
        if mode in ("L", "LA", "RGB", "RGBA"):
            return 8
        if mode.startswith("I;16"):
            return 16
        return 8
    if fmt in ("TIFF", "TIF"):
        return _tiff_bits(image)
    if fmt == "JPEG":
        return 8
    if fmt in ("WEBP", "BMP"):
        mode = image.mode
        return 16 if mode.startswith("I;16") else 8
    return None


def analyze(path: str | Path) -> ImageInfo:
    """Open an image and collect its properties without decoding all pixels.

    Raises UnsupportedImageError / CorruptImageError when the file is unusable.
    """
    p = Path(path)

    if not p.exists():
        raise CorruptImageError(f"File does not exist: {p}")
    if not supported_extension(p):
        raise UnsupportedImageError(
            f"Unsupported file type '{p.suffix or '?'}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    try:
        with Image.open(p) as img:
            fmt = img.format or p.suffix.lstrip(".").upper()
            width, height = img.size
            color_mode = _MODE_LABELS.get(img.mode, img.mode)

            orientation = 1
            try:
                if img.getexif():
                    orientation = int(img.getexif().get(274, 1)) or 1
            except (AttributeError, ValueError, TypeError):
                orientation = 1

            effective = img.size
            if orientation in (5, 6, 7, 8):
                effective = (height, width)

            has_alpha = "A" in img.mode or img.mode.startswith("P") and (
                "transparency" in img.info
            )
            if img.mode.startswith("P"):
                has_alpha = has_alpha or "transparency" in img.info

            dpi = None
            try:
                d = img.info.get("dpi")
                if isinstance(d, (tuple, list)) and len(d) == 2:
                    dpi = (float(d[0]), float(d[1]))
            except (TypeError, ValueError):
                dpi = None

            icc = img.info.get("icc_profile") is not None
            exif = img.getexif() is not None and len(img.getexif()) > 0

            bits = _bits_per_channel(img, fmt)

            return ImageInfo(
                path=str(p),
                format=fmt,
                width=width,
                height=height,
                effective_size=effective,
                color_mode=color_mode,
                bit_depth=bits,
                orientation=orientation,
                has_alpha=has_alpha,
                icc_profile=icc,
                dpi=dpi,
                exif_available=exif,
                megapixels=round((width * height) / 1_000_000, 2),
            )

    except UnsupportedImageError:
        raise
    except Exception as exc:  # Pillow raises many different exceptions
        if isinstance(exc, CorruptImageError):
            raise
        raise CorruptImageError(f"Corrupt or undecodable image '{p.name}': {exc}") from exc


def color_mode_detail(path: str | Path) -> str:
    try:
        return analyze(path).describe()
    except Exception:
        return "unknown"