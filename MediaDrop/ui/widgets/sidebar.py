"""Sidebar navigation widget with branding, active badge, and FFmpeg status."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.utils.config import config_manager
from app.utils.ffmpeg_utils import find_ffmpeg
from app.utils.resource_utils import get_asset_path
from ui.styles.theme import Theme


class SidebarButton(QPushButton):
    """Sidebar navigation item with icon, label, and active selection pill."""

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)

        icon_path = get_asset_path(f"icons/{icon_name}")
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
            self.setIconSize(QSize(18, 18))

        self._badge_text = ""
        self._update_style()

    def _update_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9A9A9A;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 14px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #18181B;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #202025;
                color: #FFFFFF;
                font-weight: 600;
                border-left: 3px solid #6366F1;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
            }
        """)


class Sidebar(QFrame):
    """Main application sidebar."""

    page_changed = Signal(int)  # 0: Home, 1: Downloads, 2: History, 3: Settings
    new_download_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setObjectName("sidebarFrame")
        self.setStyleSheet("""
            #sidebarFrame {
                background-color: #0F0F10;
                border-right: 1px solid #1E1E22;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(12)

        # 1. Branding Header
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setFixedSize(36, 36)
        logo_path = get_asset_path("icons/logo.svg")
        if logo_path.exists():
            logo_pixmap = QPixmap(36, 36)
            logo_pixmap.fill(Qt.transparent)
            from PySide6.QtGui import QPainter
            painter = QPainter(logo_pixmap)
            renderer = QSvgRenderer(str(logo_path))
            renderer.render(painter)
            painter.end()
            logo_label.setPixmap(logo_pixmap)

        brand_text_layout = QVBoxLayout()
        brand_text_layout.setSpacing(2)

        title_label = QLabel("MediaDrop")
        title_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #FFFFFF;")

        tagline_label = QLabel("One URL. Every Media.")
        tagline_label.setStyleSheet("font-size: 11px; color: #71717A; font-weight: 500;")

        brand_text_layout.addWidget(title_label)
        brand_text_layout.addWidget(tagline_label)

        brand_layout.addWidget(logo_label)
        brand_layout.addLayout(brand_text_layout)
        brand_layout.addStretch()
        layout.addLayout(brand_layout)

        layout.addSpacing(10)

        # 2. "+ New Download" primary button
        self.new_download_btn = QPushButton("+ New Download")
        self.new_download_btn.setProperty("role", "primary")
        self.new_download_btn.setFixedHeight(40)
        self.new_download_btn.setCursor(Qt.PointingHandCursor)
        self.new_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton:pressed {
                background-color: #4338CA;
            }
        """)
        self.new_download_btn.clicked.connect(self.new_download_requested.emit)
        layout.addWidget(self.new_download_btn)

        layout.addSpacing(14)

        # 3. Navigation items
        nav_title = QLabel("NAVIGATION")
        nav_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #52525B; letter-spacing: 1px; padding-left: 8px;")
        layout.addWidget(nav_title)

        self.btn_home = SidebarButton("home.svg", "Home")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.page_changed.emit(0))
        layout.addWidget(self.btn_home)

        # Downloads with badge layout
        dl_container = QWidget()
        dl_layout = QHBoxLayout(dl_container)
        dl_layout.setContentsMargins(0, 0, 0, 0)
        dl_layout.setSpacing(0)

        self.btn_downloads = SidebarButton("download.svg", "Downloads")
        self.btn_downloads.clicked.connect(lambda: self.page_changed.emit(1))
        dl_layout.addWidget(self.btn_downloads, stretch=1)

        self.badge_label = QLabel("0")
        self.badge_label.setFixedSize(22, 18)
        self.badge_label.setAlignment(Qt.AlignCenter)
        self.badge_label.setStyleSheet("""
            background-color: #6366F1;
            color: #FFFFFF;
            border-radius: 9px;
            font-size: 11px;
            font-weight: 700;
        """)
        self.badge_label.hide()
        dl_layout.addWidget(self.badge_label)
        layout.addWidget(dl_container)

        self.btn_history = SidebarButton("history.svg", "History")
        self.btn_history.clicked.connect(lambda: self.page_changed.emit(2))
        layout.addWidget(self.btn_history)

        self.btn_settings = SidebarButton("settings.svg", "Settings")
        self.btn_settings.clicked.connect(lambda: self.page_changed.emit(3))
        layout.addWidget(self.btn_settings)

        # Spacer to push footer to bottom
        layout.addStretch(1)

        # 4. FFmpeg Status indicator
        self.ffmpeg_status_container = QFrame()
        self.ffmpeg_status_container.setStyleSheet("""
            QFrame {
                background-color: #141416;
                border: 1px solid #222226;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        ff_layout = QHBoxLayout(self.ffmpeg_status_container)
        ff_layout.setContentsMargins(10, 8, 10, 8)
        ff_layout.setSpacing(8)

        self.ff_icon = QLabel()
        self.ff_icon.setFixedSize(14, 14)
        ff_layout.addWidget(self.ff_icon)

        self.ff_label = QLabel("FFmpeg checking...")
        self.ff_label.setStyleSheet("font-size: 11px; color: #A1A1AA; font-weight: 500;")
        ff_layout.addWidget(self.ff_label, stretch=1)
        layout.addWidget(self.ffmpeg_status_container)

        # 5. Version Info
        ver_layout = QHBoxLayout()
        ver_label = QLabel("MediaDrop v1.0.0")
        ver_label.setStyleSheet("font-size: 11px; color: #52525B;")
        ver_layout.addWidget(ver_label)
        ver_layout.addStretch()
        layout.addLayout(ver_layout)

        self.update_ffmpeg_status()

    def update_ffmpeg_status(self):
        custom = config_manager.get("ffmpeg_path")
        found = find_ffmpeg(custom)
        if found:
            self.ff_label.setText("FFmpeg detected ✓")
            self.ff_label.setStyleSheet("font-size: 11px; color: #10B981; font-weight: 500;")
        else:
            self.ff_label.setText("FFmpeg missing ⚠")
            self.ff_label.setStyleSheet("font-size: 11px; color: #EF4444; font-weight: 500;")

    def set_active_page(self, index: int):
        buttons = [self.btn_home, self.btn_downloads, self.btn_history, self.btn_settings]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)

    def set_download_count(self, count: int):
        if count > 0:
            self.badge_label.setText(str(count))
            self.badge_label.show()
        else:
            self.badge_label.hide()
