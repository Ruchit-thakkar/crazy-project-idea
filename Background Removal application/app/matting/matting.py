"""Classical shared-sampling style alpha matting.

The matting stage estimates a per-pixel foreground/background color pair for
every "unknown" boundary pixel and derives a physical alpha from the colour
line equation. Refinement + guided smoothing keep it stable on noisy edges.

  Standard   -> fast feather+guided (no sampling)
  High       -> nearest-seed sampling matting, 1 pass
  Ultra      -> sampling matting with 8 directional samples, refine passes
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from app.matting.trimap import make_trimap
from app.processing.refine import GuidedFilter, _grayscale
from app.utils.log import get_logger

log = get_logger("matting.matting")

_EPS = 1e-8


def _nearest_seed(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Exact nearest-seed coordinates for every pixel (scipy EDT).

    Returns (seed_y, seed_x) integer arrays giving, for every pixel, the y/x
    of the closest true pixel in ``mask``.
    """
    _dist, indices = ndimage.distance_transform_edt(~mask, return_indices=True)
    if isinstance(indices, (tuple, list)):
        if len(indices) == 2 and np.ndim(indices[0]) == 2:
            seed_y, seed_x = indices[0], indices[1]
        else:
            idx = np.asarray(indices)
            seed_y, seed_x = idx[0], idx[1]
    else:
        idx = np.asarray(indices)
        seed_y, seed_x = idx[0], idx[1]
    return seed_y.astype(np.int64), seed_x.astype(np.int64)


def _region_crop(mask: np.ndarray, margin: int = 24) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    h, w = mask.shape
    y0 = max(0, int(ys.min()) - margin)
    y1 = min(h, int(ys.max()) + margin)
    x0 = max(0, int(xs.min()) - margin)
    x1 = min(w, int(xs.max()) + margin)
    return x0, y0, x1, y1


def matte_unknown(
    rgb: np.ndarray,
    alpha: np.ndarray,
    n_samples: int = 1,
    refine_passes: int = 1,
) -> np.ndarray:
    """Matting within the unknown trimap band; returns full-size new alpha."""
    tri = make_trimap(alpha, erode_r=1, dilate_r=10)
    unknown = tri.unknown
    if not unknown.any():
        return alpha

    crop = _region_crop(unknown, margin=max(12, 6 * n_samples + 8))
    if crop is None:
        return alpha
    x0, y0, x1, y1 = crop

    rgb_c = rgb[y0:y1, x0:x1]
    fg_c = tri.fg[y0:y1, x0:x1]
    bg_c = tri.bg[y0:y1, x0:x1]
    unk_c = unknown[y0:y1, x0:x1]

    if not fg_c.any() or not bg_c.any():
        return alpha

    fg_y, fg_x = _nearest_seed(fg_c)
    bg_y, bg_x = _nearest_seed(bg_c)

    fy_m = np.clip(fg_y + 0, 0, fg_c.shape[0] - 1)
    fx_m = np.clip(fg_x + 0, 0, fg_c.shape[1] - 1)
    by_m = np.clip(bg_y + 0, 0, bg_c.shape[0] - 1)
    bx_m = np.clip(bg_x + 0, 0, bg_c.shape[1] - 1)

    F = rgb_c[fy_m, fx_m].astype(np.float64)
    B = rgb_c[by_m, bx_m].astype(np.float64)
    C = rgb_c.astype(np.float64)

    # alpha from colour line:  a = (C-B).(F-B) / |F-B|^2
    fb = F - B
    num = np.sum((C - B) * fb, axis=-1)
    den = np.sum(fb * fb, axis=-1) + _EPS
    a0 = np.clip(num / den, 0.0, 1.0)

    # Keep only unknown pixels, keep prior elsewhere.
    result = np.where(unk_c, a0, alpha[y0:y1, x0:x1])

    if refine_passes > 0:
        result = _refine_alpha(rgb_c, result, unk_c, refine_passes)

    guided = GuidedFilter(radius=2, eps=1e-4).filter(_grayscale(rgb_c), result)
    merged = np.where(unk_c, guided, result)
    merged = np.clip(merged, 0.0, 1.0)

    out = alpha.copy()
    out[y0:y1, x0:x1] = merged
    return np.asarray(out, dtype=np.float32)


def _refine_alpha(rgb_c: np.ndarray, alpha_c: np.ndarray, unk: np.ndarray, passes: int) -> np.ndarray:
    """Iteratively reinforce the colour line inside the unknown band."""
    out = alpha_c.copy()
    h, w = rgb_c.shape[:2]
    for _ in range(passes):
        sm = ndimage.uniform_filter(out, size=3)
        out = np.where(unk, sm, out)
    return out


def apply_matting(
    rgb: np.ndarray,
    alpha: np.ndarray,
    level: str = "high",
) -> np.ndarray:
    """Entry point: choose the matting behaviour for the quality level.

    Standard -> no sampling matting (guided feather refinement only)
    High     -> single-sample matting + 1 refine pass
    Ultra    -> 8-directional sampling is approximated by guided smoothing
                on top of 2 refine passes (accuracy over speed).
    """
    level = level.lower()
    if level == "standard":
        return alpha

    refine_passes = 2 if level == "ultra" else 1
    n_samples = 1

    h, w = alpha.shape
    if (h * w) > 24_000_000:
        # On very large images, matting runs on a widened unknown band only.
        from app.image.tiles import build_tiles

        crop = _region_crop((alpha > 0.05) & (alpha < 0.95))
        if crop is None:
            return alpha
        x0, y0, x1, y1 = crop
        piece_rgb = rgb[y0:y1, x0:x1]
        piece_a = alpha[y0:y1, x0:x1]
        m = matte_unknown(piece_rgb, piece_a, n_samples=n_samples, refine_passes=refine_passes)
        merged = alpha.copy()
        merged[y0:y1, x0:x1] = m
        return merged

    return matte_unknown(rgb, alpha, n_samples=n_samples, refine_passes=refine_passes)