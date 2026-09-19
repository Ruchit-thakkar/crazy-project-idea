"""Custom button widget with vector SVG icon support and hover styling."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

from app.utils.resource_utils import get_asset_path


def load_tinted_svg_icon(
    icon_name: str,
    color_hex: str = "#FFFFFF",
    size: QSize = QSize(20, 20)
) -> QIcon:
    """Render an SVG icon tinted with the given color."""
    icon_path = get_asset_path(f"icons/{icon_name}")
    if not icon_path.exists():
        return QIcon()

    renderer = QSvgRenderer(str(icon_path))
    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


class IconButton(QPushButton):
    """Sleek icon button with modern hover states and tooltips."""

    def __init__(
        self,
        icon_name: str,
        text: str = "",
        tooltip: str = "",
        icon_size: int = 18,
        parent=None,
    ):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

        icon_path = get_asset_path(f"icons/{icon_name}")
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
            self.setIconSize(QSize(icon_size, icon_size))
