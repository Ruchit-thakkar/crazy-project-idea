"""Trimap generation from soft alpha masks."""
from __future__ import annotations

import numpy as np
from scipy import ndimage


class Trimap:
    fg: np.ndarray        # boolean, definitely foreground
    bg: np.ndarray        # boolean, definitely background
    unknown: np.ndarray   # boolean, needs matting

    def __init__(self, fg: np.ndarray, bg: np.ndarray, unknown: np.ndarray):
        self.fg = fg
        self.bg = bg
        self.unknown = unknown

    def stats(self) -> dict:
        return {
            "fg": int(self.fg.sum()),
            "bg": int(self.bg.sum()),
            "unknown": int(self.unknown.sum()),
        }


def make_trimap(alpha: np.ndarray, erode_r: int = 2, dilate_r: int = 10) -> Trimap:
    """Build a trimap by eroding the foreground and dilating the background."""
    hard = alpha > 0.5

    if erode_r > 0:
        fg = ndimage.binary_erosion(hard, iterations=erode_r)
    else:
        fg = hard
    if dilate_r > 0:
        bg = ~ndimage.binary_dilation(hard, iterations=dilate_r)
    else:
        bg = ~hard

    unknown = ~(fg | bg)
    return Trimap(fg=fg, bg=bg, unknown=unknown)


def counts(trimap: Trimap) -> tuple[int, int, int]:
    return trimap.fg.sum(), trimap.bg.sum(), trimap.unknown.sum()