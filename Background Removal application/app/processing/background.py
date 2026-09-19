"""Background replacement (never touches the foreground pixels)."""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.utils.exceptions import ProcessingError
from app.utils.log import get_logger

log = get_logger("processing.background")

TRANSPARENT = "Transparent"
WHITE = "White"
BLACK = "Black"
CUSTOM_COLOR = "Custom Color"
CUSTOM_IMAGE = "Custom Image"
BLURRED_BG = "Blurred Background"
CHECKERBOARD = "Checkerboard"

OPTIONS = (TRANSPARENT, WHITE, BLACK, CUSTOM_COLOR, CUSTOM_IMAGE, BLURRED_BG, CHECKERBOARD)


def _checkerboard(h: int, w: int, size: int = 32) -> np.ndarray:
    tile = np.ones((size, size, 3), dtype=np.float32) * 0.85
    tile[: size // 2, size // 2:] = 0.62
    tile[size // 2:, : size // 2] = 0.62
    rows = np.tile(tile, (int(np.ceil(h / size)), int(np.ceil(w / size)), 1))[:h, :w]
    return rows


def compose(
    rgb: np.ndarray,
    alpha: np.ndarray,
    mode: str = TRANSPARENT,
    color: tuple[float, float, float] = (1.0, 1.0, 1.0),
    background_image: np.ndarray | None = None,
    blur_radius: float = 16.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (composited RGB, output alpha).

    * Transparent -> alpha channel is kept as-is (PNG export)
    * White/Black/Custom Color -> flat background
    * Custom Image -> background image composed under the foreground
    * Blurred Background -> the original background blurred, then composited
    * Checkerboard -> transparency preview (alpha forced to 1 for display)
    """
    h, w = rgb.shape[:2]
    a = np.clip(alpha, 0.0, 1.0)[..., None]

    if mode == TRANSPARENT:
        return rgb.astype(np.float32), alpha.astype(np.float32)

    if mode == CHECKERBOARD:
        board = _checkerboard(h, w)
        out = rgb * a + board * (1.0 - a)
        return np.asarray(out, np.float32), np.ones_like(alpha, np.float32)

    if mode == BLURRED_BG:
        bg = _blur(rgb, blur_radius)
    elif mode == CUSTOM_IMAGE:
        if background_image is None:
            raise ProcessingError("Custom image background requires an image")
        bg = _fit_bg(background_image, w, h)
    elif mode == WHITE:
        bg = np.full((h, w, 3), 1.0, dtype=np.float32)
    elif mode == BLACK:
        bg = np.full((h, w, 3), 0.0, dtype=np.float32)
    elif mode == CUSTOM_COLOR:
        bg = np.full((h, w, 3), np.asarray(color, np.float32), dtype=np.float32)
    else:
        # Fallback: use the passed color
        bg = np.full((h, w, 3), np.asarray(color, np.float32), dtype=np.float32)

    out = rgb * a + bg * (1.0 - a)
    return np.asarray(out, np.float32), np.ones_like(alpha, np.float32)


def _blur(rgb: np.ndarray, radius: float) -> np.ndarray:
    from scipy import ndimage

    sig = max(0.5, float(radius))
    blurred = ndimage.gaussian_filter(rgb.astype(np.float32), sigma=sig, truncate=3.0)
    return np.clip(blurred, 0.0, 1.0).astype(np.float32)


def _fit_bg(bg_img: np.ndarray, w: int, h: int) -> np.ndarray:
    bh, bw = bg_img.shape[:2]
    if (bw, bh) == (w, h):
        return bg_img.astype(np.float32)
    # Cover-fit, center crop.
    scale = max(w / bw, h / bh)
    nw, nh = max(1, int(round(bw * scale))), max(1, int(round(bh * scale)))
    pil = Image.fromarray((np.clip(bg_img, 0, 1) * 255 + 0.5).astype(np.uint8)).resize(
        (nw, nh), Image.Resampling.LANCZOS
    )
    arr = np.asarray(pil, np.float32)[..., :3] / 255.0
    ox = (nw - w) // 2
    oy = (nh - h) // 2
    return np.clip(arr[oy:oy + h, ox:ox + w], 0.0, 1.0)