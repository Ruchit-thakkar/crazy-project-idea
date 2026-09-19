"""Detailed media information card widget."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database.models import MediaMetadata
from app.services.thumbnail_service import thumbnail_service
from app.utils.file_utils import format_count, format_duration
from app.utils.resource_utils import get_asset_path
from ui.styles.theme import Theme


class ThumbnailLoaderThread(QThread):
    """Fetches thumbnail image in the background to avoid freezing the UI."""
    loaded = Signal(str)  # image file path

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            cached_path = thumbnail_service.fetch_preview_image(self.url)
            if cached_path and cached_path.exists():
                self.loaded.emit(str(cached_path))
        except Exception:
            pass


class MediaCard(QFrame):
    """Media information card displaying thumbnail, title, and rich source metadata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mediaCard")
        self.setStyleSheet("""
            #mediaCard {
                background-color: #141414;
                border: 1px solid #292929;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        # Top section: Thumbnail + Main details
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # Thumbnail display
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(220, 124)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("""
            background-color: #1B1B1B;
            border: 1px solid #292929;
            border-radius: 8px;
            color: #71717A;
            font-size: 12px;
        """)
        self.thumb_label.setText("Loading thumbnail...")
        top_layout.addWidget(self.thumb_label)

        # Title & Channel & Platform badge
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)

        # Platform badge + Type badge
        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(8)

        self.platform_badge = QLabel("Platform")
        self.platform_badge.setStyleSheet("""
            background-color: #202025;
            color: #818CF8;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(99, 102, 241, 0.3);
        """)
        badge_layout.addWidget(self.platform_badge)

        self.type_badge = QLabel("Video")
        self.type_badge.setStyleSheet("""
            background-color: #1B1B1B;
            color: #A1A1AA;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #2E2E32;
        """)
        badge_layout.addWidget(self.type_badge)
        badge_layout.addStretch()
        header_layout.addLayout(badge_layout)

        # Title
        self.title_label = QLabel("Media Title")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #FFFFFF; line-height: 1.3;")
        header_layout.addWidget(self.title_label)

        # Channel
        self.channel_label = QLabel("Channel Name")
        self.channel_label.setStyleSheet("font-size: 13px; color: #9A9A9A; font-weight: 500;")
        header_layout.addWidget(self.channel_label)

        header_layout.addStretch()
        top_layout.addLayout(header_layout, stretch=1)
        layout.addLayout(top_layout)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #242424;")
        layout.addWidget(divider)

        # Metadata Grid (Section 6 exact labels)
        # schedule, Duration, Language, Visibility, Type, Caption, Channel, Platform
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(24)
        grid_layout.setVerticalSpacing(10)

        self.lbl_platform = self._create_field(grid_layout, "Platform", 0, 0)
        self.lbl_duration = self._create_field(grid_layout, "Duration", 0, 1)
        self.lbl_language = self._create_field(grid_layout, "Language", 0, 2)
        self.lbl_visibility = self._create_field(grid_layout, "Visibility", 0, 3)

        self.lbl_schedule = self._create_field(grid_layout, "schedule", 1, 0)
        self.lbl_type = self._create_field(grid_layout, "Type", 1, 1)
        self.lbl_views = self._create_field(grid_layout, "Views", 1, 2)
        self.lbl_likes = self._create_field(grid_layout, "Likes", 1, 3)

        layout.addLayout(grid_layout)

        # Caption / Description block
        caption_title = QLabel("Caption")
        caption_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #9A9A9A; margin-top: 4px;")
        layout.addWidget(caption_title)

        self.caption_box = QTextEdit()
        self.caption_box.setReadOnly(True)
        self.caption_box.setMaximumHeight(80)
        self.caption_box.setStyleSheet("""
            QTextEdit {
                background-color: #18181B;
                border: 1px solid #262629;
                border-radius: 8px;
                color: #D4D4D8;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.caption_box)

        self.thumb_thread: Optional[ThumbnailLoaderThread] = None

    def _create_field(self, grid: QGridLayout, label_text: str, row: int, col: int) -> QLabel:
        container = QVBoxLayout()
        container.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #71717A; text-transform: uppercase;")
        val = QLabel("Not available")
        val.setStyleSheet("font-size: 13px; font-weight: 500; color: #FFFFFF;")

        container.addWidget(lbl)
        container.addWidget(val)
        grid.addLayout(container, row, col)
        return val

    def set_metadata(self, meta: MediaMetadata):
        """Populate the card with extracted media metadata."""
        self.title_label.setText(meta.title if meta.title else "Not available")
        self.channel_label.setText(meta.channel if meta.channel else "Not available")
        self.platform_badge.setText(f"● {meta.platform}")
        self.type_badge.setText(meta.media_type)

        self.lbl_platform.setText(meta.platform)
        self.lbl_duration.setText(format_duration(meta.duration))
        self.lbl_language.setText(meta.language)
        self.lbl_visibility.setText(meta.visibility)
        self.lbl_schedule.setText(meta.upload_date)
        self.lbl_type.setText(meta.media_type)
        self.lbl_views.setText(format_count(meta.view_count))
        self.lbl_likes.setText(format_count(meta.like_count))

        self.caption_box.setPlainText(meta.caption)

        # Load thumbnail asynchronously
        if meta.thumbnail_url:
            self.thumb_label.setText("Loading...")
            if self.thumb_thread and self.thumb_thread.isRunning():
                self.thumb_thread.terminate()
                self.thumb_thread.wait()
            self.thumb_thread = ThumbnailLoaderThread(meta.thumbnail_url, parent=self)
            self.thumb_thread.loaded.connect(self._on_thumbnail_loaded)
            self.thumb_thread.start()
        else:
            self.thumb_label.setText("No Thumbnail")

    def _on_thumbnail_loaded(self, path_str: str):
        pixmap = QPixmap(path_str)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                220, 124,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")
