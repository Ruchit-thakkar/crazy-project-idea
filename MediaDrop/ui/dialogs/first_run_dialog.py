"""First-run onboarding dialog for MediaDrop."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.utils.config import config_manager
from app.utils.ffmpeg_utils import find_ffmpeg, get_ffmpeg_version
from app.utils.resource_utils import get_asset_path
from ui.widgets.icon_button import IconButton


class FirstRunDialog(QDialog):
    """First-run welcome and initial setup dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to MediaDrop")
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QDialog {
                background-color: #121214;
                border: 1px solid #27272A;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)

        title = QLabel("Welcome to MediaDrop")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #FFFFFF;")
        header_layout.addWidget(title)

        subtitle = QLabel("One URL. Every Media.\nDownload public media from YouTube, Instagram, TikTok, and more.")
        subtitle.setStyleSheet("font-size: 13px; color: #9A9A9A; line-height: 1.4;")
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Download Directory section
        dir_box = QFrame()
        dir_box.setStyleSheet("""
            QFrame {
                background-color: #18181B;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        dir_layout = QVBoxLayout(dir_box)
        dir_layout.setContentsMargins(4, 4, 4, 4)
        dir_layout.setSpacing(8)

        dir_lbl = QLabel("Download Folder")
        dir_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #D4D4D8;")
        dir_layout.addWidget(dir_lbl)

        dir_input_row = QHBoxLayout()
        dir_input_row.setSpacing(8)

        self.dir_input = QLineEdit()
        default_dir = config_manager.get("download_dir") or str(Path.home() / "Downloads" / "MediaDrop")
        self.dir_input.setText(default_dir)
        dir_input_row.addWidget(self.dir_input, stretch=1)

        self.btn_browse = IconButton("folder.svg", "Browse", icon_size=14)
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_input_row.addWidget(self.btn_browse)
        dir_layout.addLayout(dir_input_row)
        layout.addWidget(dir_box)

        # FFmpeg status section
        ff_box = QFrame()
        ff_box.setStyleSheet("""
            QFrame {
                background-color: #18181B;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        ff_layout = QHBoxLayout(ff_box)
        ff_layout.setContentsMargins(8, 6, 8, 6)
        ff_layout.setSpacing(12)

        ff_title = QLabel("FFmpeg Engine")
        ff_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #D4D4D8;")
        ff_layout.addWidget(ff_title)
        ff_layout.addStretch()

        is_avail, ver = get_ffmpeg_version()
        self.ff_badge = QLabel(f"✓ Detected ({ver.split()[0]})" if is_avail else "⚠ Not detected")
        self.ff_badge.setStyleSheet(
            "color: #10B981; font-weight: 600; font-size: 12px;"
            if is_avail else
            "color: #EF4444; font-weight: 600; font-size: 12px;"
        )
        ff_layout.addWidget(self.ff_badge)
        layout.addWidget(ff_box)

        # Get Started button
        self.btn_start = QPushButton("Get Started")
        self.btn_start.setProperty("role", "primary")
        self.btn_start.setFixedHeight(44)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 600;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
        """)
        self.btn_start.clicked.connect(self._save_and_start)
        layout.addWidget(self.btn_start)

    def _browse_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select MediaDrop Download Folder",
            self.dir_input.text(),
        )
        if chosen:
            self.dir_input.setText(chosen)

    def _save_and_start(self):
        chosen_dir = self.dir_input.text().strip()
        if chosen_dir:
            config_manager.set("download_dir", chosen_dir)
            Path(chosen_dir).mkdir(parents=True, exist_ok=True)
        config_manager.set("first_run_completed", True)
        self.accept()
