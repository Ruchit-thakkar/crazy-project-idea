"""Zoomable / pannable image widget with checkerboard transparency + mask painting."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QPoint, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from app.ui.checkerboard import checker_pixmap, numpy_rgba_to_qimage


class ZoomableImageView(QWidget):
    on_edit = Signal()
    image_dropped = Signal(str)

    FITTED = "fitted"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: np.ndarray | None = None          # HxWx3 float
        self._alpha: np.ndarray | None = None          # HxW float
        self._show_checker = True
        self._zoom: float = 1.0
        self._offset = QPoint(0, 0)
        self._mode = self.FITTED
        self._dragging = False
        self._last_pos = QPoint()
        self._pix: QPixmap | None = None
        self._pix_orig: QPixmap | None = None
        self._img_size = (0, 0)
        self._bg_brush: QPixmap | None = None
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        # mask editing state
        self._edit_enabled = False
        self._brush_radius = 12.0
        self._brush_hardness = 0.85
        self._brush_opacity = 0.9
        self._brush_add = True
        self._previous_alpha_snap: np.ndarray | None = None

    # ---------------- image plumbing ----------------
    def set_content(self, rgb: np.ndarray | None, alpha: np.ndarray | None = None, checker: bool = True):
        self._image = rgb
        self._alpha = alpha
        self._show_checker = checker
        if rgb is None:
            self._pix = None
            self._pix_orig = None
            self._img_size = (0, 0)
        else:
            h, w = rgb.shape[:2]
            self._img_size = (w, h)
            self._rebuild_pixmaps()
        self._fit()

    def current_alpha(self) -> np.ndarray | None:
        return self._alpha

    def pop_previous_alpha(self) -> np.ndarray | None:
        snap = self._previous_alpha_snap
        self._previous_alpha_snap = None
        return snap

    def set_edit_enabled(self, enabled: bool):
        self._edit_enabled = enabled
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        if not enabled:
            self._previous_alpha_snap = None

    @property
    def edit_enabled(self) -> bool:
        return self._edit_enabled

    def set_brush(self, radius: float, hardness: float, opacity: float, additive: bool):
        self._brush_radius = max(1.0, radius)
        self._brush_hardness = np.clip(hardness, 0.05, 1.0)
        self._brush_opacity = np.clip(opacity, 0.05, 1.0)
        self._brush_add = additive

    def _rebuild_pixmaps(self):
        if self._image is None:
            return
        if self._alpha is not None:
            self._pix = QPixmap.fromImage(numpy_rgba_to_qimage(self._image, self._alpha))
            self._pix_orig = QPixmap.fromImage(numpy_rgba_to_qimage(self._image, self._alpha))
        else:
            self._pix = QPixmap.fromImage(numpy_rgba_to_qimage(self._image))
            self._pix_orig = QPixmap.fromImage(numpy_rgba_to_qimage(self._image))

    def refresh(self):
        """Re-render the pixmap from current alpha without resetting zoom."""
        self._rebuild_pixmaps()
        self.update()

    # ---------------- transform ----------------
    def _fit(self):
        self._mode = self.FITTED
        self.update_transform()
        self.update()

    def reset_zoom(self):
        self._mode = "exact"
        self._zoom = 1.0
        self._center_image()
        self.update()

    def zoom_in(self):
        self._mode = "exact"
        self._zoom = min(64.0, self._zoom * 1.25)
        self.update()

    def zoom_out(self):
        self._mode = "exact"
        self._zoom = max(0.01, self._zoom / 1.25)
        self.update()

    def fit_to_screen(self):
        self._fit()

    def set_100_percent(self):
        self.reset_zoom()

    def update_transform(self):
        w, h = self._img_size
        if w == 0:
            return
        vw, vh = self.width(), self.height()
        if self._mode == self.FITTED:
            scale = min(vw / w, vh / h, 8.0)
            self._zoom = max(0.01, scale)
            self._offset = QPoint(int((vw - w * self._zoom) / 2), int((vh - h * self._zoom) / 2))
        else:
            self._center_image()

    def _center_image(self):
        w, h = self._img_size
        self._offset = QPoint(
            int((self.width() - w * self._zoom) / 2),
            int((self.height() - h * self._zoom) / 2),
        )

    def _view_to_img(self, pos: QPoint) -> tuple[int, int]:
        ix = int((pos.x() - self._offset.x()) / self._zoom)
        iy = int((pos.y() - self._offset.y()) / self._zoom)
        return ix, iy

    # ---------------- painting ----------------
    def paintEvent(self, event):
        p = QPainter(self)
        if self._show_checker and self._pix is not None:
            tile = checker_pixmap(16, 16, cell=8)
            p.drawTiledPixmap(self.rect(), tile)
        if self._pix is not None:
            w, h = self._img_size
            target = QRectF(self._offset.x(), self._offset.y(), w * self._zoom, h * self._zoom)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._zoom < 2.0)
            p.drawPixmap(target, self._pix)
        else:
            p.setPen(QPen(QColor(150, 155, 170)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image loaded")
        p.end()

    # ---------------- interaction ----------------
    def wheelEvent(self, event):
        if self._image is None:
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        mu = event.position().x()
        mv = event.position().y()
        im_x = (mu - self._offset.x()) / self._zoom
        im_y = (mv - self._offset.y()) / self._zoom
        self._mode = "exact"
        self._zoom = np.clip(self._zoom * factor, 0.01, 64.0)
        self._offset = QPoint(
            int(mu - im_x * self._zoom),
            int(mv - im_y * self._zoom),
        )
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._edit_enabled and self._alpha is not None:
            self._previous_alpha_snap = self._alpha.copy()
            self._stamp(event.position())
            return
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self._dragging = True
            self._last_pos = event.globalPosition().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self._dragging = True
            self._last_pos = event.globalPosition().toPoint()
        elif self._image is not None:
            self._dragging = True
            self._last_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._edit_enabled and self._alpha is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._stamp(event.position())
            return
        if self._dragging:
            d = event.globalPosition().toPoint() - self._last_pos
            self._last_pos = event.globalPosition().toPoint()
            self._offset = QPoint(self._offset.x() + d.x(), self._offset.y() + d.y())
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_mode_changed(event):
            pass
        if self._previous_alpha_snap is not None and self._edit_enabled:
            diff = np.abs(self._previous_alpha_snap - self._alpha)
            if diff.max() > 0:
                self.on_edit.emit()
            self._previous_alpha_snap = None
        self._dragging = False

    def _drag_mode_changed(self, event) -> bool:
        return False

    def _stamp(self, pos):
        if self._alpha is None:
            return
        h, w = self._img_size
        ix, iy = self._view_to_img(QPoint(int(pos.x()), int(pos.y())))
        self._paint_alpha_at(ix, iy, h, w)
        self.refresh()

    def _paint_alpha_at(self, ix: int, iy: int, h: int, w: int):
        r = self._brush_radius
        y0 = max(0, int(iy - r))
        y1 = min(h, int(iy + r) + 1)
        x0 = max(0, int(ix - r))
        x1 = min(w, int(ix + r) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[0: y1 - y0, 0: x1 - x0]
        d = np.sqrt((yy - (iy - y0)) ** 2 + (xx - (ix - x0)) ** 2) / r
        if self._brush_hardness >= 0.98:
            kernel = (d <= 1.0).astype(np.float32)
        else:
            t = np.clip((1.0 - d) / self._brush_hardness, 0.0, 1.0)
            kernel = t * t * (3.0 - 2.0 * t)
        kernel *= self._brush_opacity
        region = self._alpha[y0:y1, x0:x1]
        if self._brush_add:
            region[:] = np.maximum(region, kernel)
        else:
            region[:] = np.minimum(region, 1.0 - kernel)
        self._alpha[y0:y1, x0:x1] = region

    # ---------------- drag & drop ----------------
    def dragEnterEvent(self, event):
        if any("image" in str(u).lower() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self.image_dropped.emit(p)
                break
        event.acceptProposedAction()

    @property
    def zoom_factor(self) -> float:
        return self._zoom