"""Before/after comparison view with a draggable divider."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.ui.checkerboard import checker_pixmap, numpy_rgba_to_qimage


class CompareView(QWidget):
    """Draws ORIGINAL on the left, RESULT (transparent) on the right.

    The divider can be dragged; wheel zooms, middle-drag pans.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orig: QPixmap | None = None
        self._res: QPixmap | None = None
        self._size = (0, 0)
        self._zoom = 1.0
        self._offset = [0, 0]
        self._split = 0.5
        self._dragging_split = False
        self._panning = False
        self._last = QPointF()
        self.setMouseTracking(True)

    def set_pair(self, orig_rgb: np.ndarray | None, res_rgb: np.ndarray | None, res_alpha: np.ndarray | None):
        if orig_rgb is not None:
            self._orig = QPixmap.fromImage(numpy_rgba_to_qimage(orig_rgb))
        else:
            self._orig = None
        if res_rgb is not None and res_alpha is not None:
            self._res = QPixmap.fromImage(numpy_rgba_to_qimage(res_rgb, res_alpha))
        else:
            self._res = None
        if orig_rgb is not None:
            self._size = (orig_rgb.shape[1], orig_rgb.shape[0])
        else:
            self._size = (0, 0)
        self.fit()
        self.update()

    def fit(self):
        w, h = self._size
        if w == 0:
            return
        self._zoom = min(self.width() / w, self.height() / h, 8.0)
        self._zoom = max(0.01, self._zoom)
        self._center()

    def _center(self):
        w, h = self._size
        self._offset = [
            (self.width() - w * self._zoom) / 2,
            (self.height() - h * self._zoom) / 2,
        ]

    def zoom_in(self):
        self._zoom = min(64.0, self._zoom * 1.25)
        self.update()

    def zoom_out(self):
        self._zoom = max(0.01, self._zoom / 1.25)
        self.update()

    def set_100_percent(self):
        self._zoom = 1.0
        self._center()
        self.update()

    def _split_px(self) -> float:
        return self.width() * self._split

    def paintEvent(self, event):
        p = QPainter(self)
        if self._orig is None or self._res is None:
            p.setPen(QColor(150, 155, 170))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No result yet")
            p.end()
            return

        tile = checker_pixmap(16, 16, cell=8)
        p.drawTiledPixmap(self.rect(), tile)

        w, h = self._size
        target = QRectF(self._offset[0], self._offset[1], w * self._zoom, h * self._zoom)
        split = self._split_px()

        # original (left)
        clip = QRectF(0, 0, split, self.height())
        p.save()
        p.setClipRect(clip)
        p.drawPixmap(target, self._orig)
        p.restore()

        # result (right)
        clip2 = QRectF(split, 0, max(1, self.width() - split), self.height())
        p.save()
        p.setClipRect(clip2)
        p.drawPixmap(target, self._res)
        p.restore()

        # divider
        p.setPen(QColor(80, 90, 110, 220))
        p.setBrush(QColor(255, 255, 255, 180))
        p.drawRect(int(split) - 1, 0, 3, self.height())

        # labels
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(10, 10, 120, 24), Qt.AlignmentFlag.AlignLeft, "ORIGINAL")
        p.drawText(QRectF(self.width() - 130, 10, 110, 24), Qt.AlignmentFlag.AlignRight, "RESULT")
        p.end()

    def mousePressEvent(self, event):
        if abs(event.position().x() - self._split_px()) < 12:
            self._dragging_split = True
            return
        if event.button() == Qt.MouseButton.LeftButton or event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._last = event.position()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last = event.position()

    def mouseMoveEvent(self, event):
        if self._dragging_split:
            self._split = np.clip(event.position().x() / max(1, self.width()), 0.0, 1.0)
            self.update()
            return
        if self._panning:
            d = event.position() - self._last
            self._last = event.position()
            self._offset[0] += d.x()
            self._offset[1] += d.y()
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging_split = False
        self._panning = False

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self._zoom = np.clip(self._zoom * factor, 0.01, 64.0)
        self.update()
        event.accept()