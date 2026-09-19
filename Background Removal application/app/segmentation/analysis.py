"""Lightweight image-content heuristics used by the Auto preset.

All heuristics are cheap and run on a downscaled preview only. They never
touch the full-resolution pixels.
"""
from __future__ import annotations

import numpy as np

from app.image.loader import load_preview


def as_preview(path: str, max_side: int = 512) -> np.ndarray:
    return load_preview(path, max_side=max_side)


def skin_score(rgb: np.ndarray) -> float:
    """Fraction of skin-toned pixels — a weak human-presence hint."""
    rgb_f = rgb.astype(np.float32) / 255.0
    r, g, b = rgb_f[..., 0], rgb_f[..., 1], rgb_f[..., 2]
    mx = rgb_f.max(axis=2)
    mn = rgb_f.min(axis=2)
    skin = (
        (r > 0.35)
        & (g > 0.22)
        & (b > 0.12)
        & (r > g) & (g > b) & (b < 0.85)
        & ((mx - mn) > 0.05) & (r - g > 0.05)
    )
    return float(skin.mean())


def subject_center_bias(rgb: np.ndarray, mask: np.ndarray) -> float:
    """1.0 if the subject is centred, <1.0 if it hugs the frame edges.

    The model mask (0/1 threshold) is compared against a Gaussian centered
    map. Used to decide model preset (centered subjects -> portrait paths).
    """
    h, w = mask.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.0, w / 2.0
    gauss = np.exp(-(((ys - cy) / (h * 0.55)) ** 2 + ((xs - cx) / (w * 0.55)) ** 2))
    hard = (mask > 0.5).astype(np.float32)
    total = max(hard.sum(), 1)
    return float((hard * gauss).sum() / total)


def classify_preview(path: str, max_side: int = 512) -> dict:
    """Return a small dictionary of content hints for Auto mode."""
    rgb = as_preview(path, max_side)
    tiny = rgb[::4, ::4] if rgb.shape[0] > 4 else rgb
    hints: dict = {
        "brightness": float(rgb.mean()),
        "skin_fraction": skin_score(tiny),
        "probably_human": skin_score(tiny) > 0.02,
        "background_evenness": 0.0,
    }
    try:
        small = rgb.astype(np.float32) / 255.0
        g = (small[..., 0] * 0.299 + small[..., 1] * 0.587 + small[..., 2] * 0.114)
        std = float(g.std())
        hints["background_evenness"] = 1.0 - min(1.0, std / 0.35)
    except Exception:
        pass
    return hints


def choose_preset_from_hints(hints: dict, user_preset: str = "Auto") -> str:
    if user_preset != "Auto":
        return user_preset
    return "Human" if hints.get("probably_human", False) else "u2net"