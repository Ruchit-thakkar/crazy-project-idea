"""Checkerboard (transparency) rendering utilities."""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

_LIGHT = QColor(210, 210, 210)
_DARK = QColor(178, 178, 178)


def checker_pixmap(width: int, height: int, cell: int = 16) -> QPixmap:
    """A seamless checkerboard tile used as transparent backdrop."""
    img = QImage(cell * 2, cell * 2, QImage.Format.Format_RGB32)
    img.fill(_LIGHT)
    painter = QPainter(img)
    painter.fillRect(0, 0, cell, cell, _DARK)
    painter.fillRect(cell, cell, cell, cell, _DARK)
    painter.end()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(1.0)
    return pix


def checker_image(width: int, height: int, cell: int = 16) -> QImage:
    pix = checker_pixmap(width, height, cell)
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(_LIGHT)
    p = QPainter(img)
    for y in range(0, height, cell * 2):
        for x in range(0, width, cell * 2):
            p.drawPixmap(x, y, pix)
    p.end()
    return img


def numpy_rgba_to_qimage(rgb: np.ndarray, alpha: np.ndarray | None = None) -> QImage:
    """Builds a properly-swizzled QImage from float RGB (and optional alpha)."""
    h, w = rgb.shape[:2]
    from PySide6.QtGui import QImage as QI

    if alpha is None:
        rgb8 = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        q = QI(memoryview(rgb8.data), w, h, 3 * w, QI.Format.Format_RGB888)
        return q.copy()
    rgb8 = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    a8 = (np.clip(alpha, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    rgba = np.concatenate([rgb8, a8[..., None]], axis=2)
    q = QI(memoryview(rgba.data), w, h, 4 * w, QI.Format.Format_RGBA8888)
    return q.copy()