"""Edge refinement and halo removal for soft alpha masks.

Implements, in pure NumPy (+ optional scipy), classical techniques:

  * guided (box) filter refinement using the high-res RGB as guidance
  * morphology-based edge cleanup that removes jagged/speckle artifacts
  * confidence contrast that recovers fine hair while keeping hard cores
  * haloless defringe that un-darkens/un-lightens edges caused by
    background color bleeding into the alpha transition band
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from app.utils.log import get_logger

log = get_logger("processing.refine")


def box_filter(src: np.ndarray, r: int) -> np.ndarray:
    """Fast separable mean filter."""
    if r <= 0:
        return np.asarray(src, dtype=np.float64)
    size = 2 * r + 1
    return ndimage.uniform_filter(src.astype(np.float64), size=size, mode="reflect")


class GuidedFilter:
    """Grayscale guided filter (Kaiming He) with box-filter acceleration."""

    def __init__(self, radius: int = 4, eps: float = 1e-4):
        self.r = radius
        self.eps = eps

    def _box(self, src: np.ndarray) -> np.ndarray:
        return box_filter(src, self.r)

    def filter(self, guide: np.ndarray, target: np.ndarray) -> np.ndarray:
        guide = guide.astype(np.float64)
        target = target.astype(np.float64)

        mean_I = self._box(guide)
        mean_p = self._box(target)
        corr_I = self._box(guide * guide)
        corr_Ip = self._box(guide * target)

        var_I = corr_I - mean_I * mean_I
        cov_Ip = corr_Ip - mean_I * mean_p

        a = cov_Ip / (var_I + self.eps)
        b = mean_p - a * mean_I

        mean_a = self._box(a)
        mean_b = self._box(b)
        return np.clip(mean_a * guide + mean_b, 0.0, 1.0)


def _grayscale(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def guided_refine(alpha: np.ndarray, guide_rgb: np.ndarray, radius: int = 4, eps: float = 1e-4, tiles: int = 4) -> np.ndarray:
    """Refine a soft alpha mask so its edges follow the image's own edges."""
    g = _grayscale(guide_rgb)
    gf = GuidedFilter(radius=radius, eps=eps)
    if alpha.shape[0] * alpha.shape[1] <= (4096 * 4096):
        return gf.filter(g, alpha).astype(np.float32)
    return _tiled(g, alpha, gf.filter, tiles)


def _tiled(guide: np.ndarray, target: np.ndarray, fn, tiles: int, overlap: int = 64) -> np.ndarray:
    h, w = guide.shape
    out = np.zeros_like(target, dtype=np.float64)
    weight = np.zeros_like(target, dtype=np.float64)
    rows = np.linspace(0, h, tiles + 1).astype(int)
    cols = np.linspace(0, w, tiles + 1).astype(int)
    for ri in range(tiles):
        for ci in range(tiles):
            y0, y1 = rows[ri], min(rows[ri + 1] + overlap, h)
            x0, x1 = cols[ci], min(cols[ci + 1] + overlap, w)
            piece = fn(guide[y0:y1, x0:x1], target[y0:y1, x0:x1])
            wgt = np.ones_like(piece)
            out[y0:y1, x0:x1] += piece
            weight[y0:y1, x0:x1] += wgt
    return np.clip(out / np.maximum(weight, 1e-8), 0.0, 1.0).astype(np.float32)


def feather_mask(alpha: np.ndarray, radius: int = 1) -> np.ndarray:
    """Small Gaussian-like smoothing of the alpha transition (edge softening)."""
    if radius <= 0:
        return alpha
    return guided_refine(alpha, np.stack([alpha] * 3, axis=-1), radius=radius, eps=0.01)


def remove_speckles(alpha: np.ndarray, min_size_px: int = 6, radius: int = 1):
    """Drop isolated foreground/background blobs below min_size_px."""
    from scipy import ndimage

    binmask = alpha >= 0.5
    labels, n = ndimage.label(binmask)
    if n == 0:
        return alpha
    sizes = ndimage.sum(binmask, labels, range(1, n + 1))
    small = np.where(sizes < min_size_px)[0] + 1
    if small.size == 0:
        return alpha
    remove = np.isin(labels, small.tolist())
    alpha = np.where(remove, np.minimum(alpha, 0.0), alpha)
    return alpha


def clean_edges(alpha: np.ndarray, r: int = 1) -> np.ndarray:
    """Morphological open/close on the hard threshold to kill jaggies & nicks."""
    from scipy import ndimage

    if r <= 1:
        return alpha
    hard = (alpha > 0.5)
    se = np.ones((2 * r + 1, 2 * r + 1), dtype=bool)
    closed = ndimage.binary_opening(ndimage.binary_closing(hard, structure=se), structure=se)
    return np.where(closed != hard, np.where(closed, np.maximum(alpha, 0.5), np.minimum(alpha, 0.5)), alpha)


def stretch_soft(alpha: np.ndarray, sharpen: float = 1.0, floor: float = 0.02) -> np.ndarray:
    """Softly push intermediate alpha values apart without hard thresholding."""
    if sharpen <= 1.0:
        return alpha
    centered = (alpha - 0.5) * sharpen + 0.5
    return np.clip(centered, 0.0, 1.0).astype(np.float32)


def defringe(rgb: np.ndarray, alpha: np.ndarray, radius: int = 3, strength: float = 0.75) -> tuple[np.ndarray, np.ndarray]:
    """Reduce background-color bleeding into the foreground edge.

    Samples the color just inside the core foreground (opaque) and compares
    it with the transparent edge pixel color; pulls the edge RGB toward the
    core color and re-derives alpha where possible.
    """
    if radius <= 0 or strength <= 0:
        return rgb, alpha

    hard = alpha > 0.5
    from scipy import ndimage

    core = ndimage.binary_erosion(hard, iterations=radius) if radius > 0 else hard
    core_color = np.zeros((3,), dtype=np.float64)
    if core.any():
        core_color = rgb[core].mean(axis=0)

    edge = hard & ~ndimage.binary_erosion(hard, iterations=1) if radius > 0 else ~hard
    band = (~hard) & (alpha > 0.05)
    if not band.any():
        return rgb, alpha

    ys, xs = np.nonzero(band)
    step = max(1, len(ys) // 2_000_000)
    ys = ys[::step]
    xs = xs[::step]

    new_rgb = rgb.copy()
    for y, x in zip(ys, xs):
        c = rgb[y, x]
        diff = c - core_color
        pull = diff * strength * alpha[y, x]
        new_rgb[y, x] = np.clip(c - pull, 0.0, 1.0)
    return new_rgb, alpha


def refine_pipeline(
    rgb: np.ndarray,
    alpha_in: np.ndarray,
    quality: str = "Ultra Quality",
) -> tuple[np.ndarray, np.ndarray]:
    """Combine all refinement steps for the given quality level.

    Returns (refined_rgb, refined_alpha). The RGB is only ever touched by
    the defringe step (optional) — never resized or blurred wholesale.
    """
    r = 2 if quality == "Ultra Quality" else 1
    alpha = np.asarray(alpha_in, dtype=np.float32)

    alpha = clean_edges(alpha, r=max(1, r))
    alpha = guided_refine(alpha, rgb, radius=max(2, r), eps=1e-5 if quality == "Ultra Quality" else 1e-4)
    alpha = remove_speckles(alpha)

    if quality == "Ultra Quality":
        alpha = stretch_soft(alpha, sharpen=1.15)

    return rgb, np.clip(alpha, 0.0, 1.0).astype(np.float32)