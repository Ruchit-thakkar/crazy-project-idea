"""Settings page providing full control over directories, engine, and network."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
import yt_dlp

from app.utils.config import config_manager
from app.utils.ffmpeg_utils import find_ffmpeg, get_ffmpeg_version
from ui.widgets.icon_button import IconButton


class SettingsSection(QFrame):
    """Card container for a group of related settings."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsSection")
        self.setStyleSheet("""
            #settingsSection {
                background-color: #141414;
                border: 1px solid #27272A;
                border-radius: 12px;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(16)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        self.layout.addWidget(title_lbl)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #242424;")
        self.layout.addWidget(divider)

    def add_row(self, label_text: str, desc: str, widget: QWidget):
        row = QHBoxLayout()
        row.setSpacing(20)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #FFFFFF;")
        info_layout.addWidget(lbl)

        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: #9A9A9A;")
            desc_lbl.setWordWrap(True)
            info_layout.addWidget(desc_lbl)

        row.addLayout(info_layout, stretch=1)
        row.addWidget(widget)
        self.layout.addLayout(row)


class SettingsPage(QWidget):
    """Settings view for configuring MediaDrop."""

    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)

        # Header
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #FFFFFF;")
        title_layout.addWidget(title)

        subtitle = QLabel("Configure downloads, conversion quality, and performance")
        subtitle.setStyleSheet("font-size: 13px; color: #9A9A9A;")
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout)

        # 1. General Section
        sec_general = SettingsSection("General")

        # Download Directory
        dir_widget = QWidget()
        dir_layout = QHBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(8)

        self.input_download_dir = QLineEdit()
        self.input_download_dir.setMinimumWidth(280)
        self.input_download_dir.setText(config_manager.get("download_dir"))
        self.input_download_dir.textChanged.connect(lambda v: config_manager.set("download_dir", v))
        dir_layout.addWidget(self.input_download_dir)

        self.btn_browse = IconButton("folder.svg", "Browse", icon_size=14)
        self.btn_browse.clicked.connect(self._browse_download_dir)
        dir_layout.addWidget(self.btn_browse)
        sec_general.add_row("Download Directory", "Where completed media files and thumbnails are saved", dir_widget)

        # Auto-open completed
        self.chk_auto_open = QCheckBox()
        self.chk_auto_open.setChecked(config_manager.get("auto_open_completed", False))
        self.chk_auto_open.toggled.connect(lambda v: config_manager.set("auto_open_completed", v))
        sec_general.add_row("Automatically open completed files", "Open the file with your default player once finished", self.chk_auto_open)

        # Clipboard detection
        self.chk_clipboard = QCheckBox()
        self.chk_clipboard.setChecked(config_manager.get("clipboard_detection", True))
        self.chk_clipboard.toggled.connect(lambda v: config_manager.set("clipboard_detection", v))
        sec_general.add_row("Clipboard URL detection", "Show a banner when a supported media link is copied", self.chk_clipboard)

        layout.addWidget(sec_general)

        # 2. Downloads Section
        sec_downloads = SettingsSection("Downloads")

        # Max simultaneous downloads
        self.spin_max_concurrent = QSpinBox()
        self.spin_max_concurrent.setRange(1, 10)
        self.spin_max_concurrent.setValue(config_manager.get("max_concurrent_downloads", 3))
        self.spin_max_concurrent.valueChanged.connect(lambda v: config_manager.set("max_concurrent_downloads", v))
        sec_downloads.add_row("Maximum simultaneous downloads", "Limit active network downloads to maintain speed", self.spin_max_concurrent)

        # Network timeout
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(5, 120)
        self.spin_timeout.setSuffix(" sec")
        self.spin_timeout.setValue(config_manager.get("network_timeout", 30))
        self.spin_timeout.valueChanged.connect(lambda v: config_manager.set("network_timeout", v))
        sec_downloads.add_row("Network timeout", "Connection timeout when querying platform extractors", self.spin_timeout)

        # Retry count
        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 10)
        self.spin_retries.setValue(config_manager.get("retry_count", 3))
        self.spin_retries.valueChanged.connect(lambda v: config_manager.set("retry_count", v))
        sec_downloads.add_row("Retry attempts", "Number of automatic retries on momentary network failure", self.spin_retries)

        layout.addWidget(sec_downloads)

        # 3. Conversion & FFmpeg Section
        sec_conv = SettingsSection("Conversion & FFmpeg")

        # Default MP3 bitrate
        self.combo_audio_bitrate = QComboBox()
        self.combo_audio_bitrate.addItems(["320k", "256k", "192k", "128k"])
        self.combo_audio_bitrate.setCurrentText(config_manager.get("default_audio_bitrate", "320k"))
        self.combo_audio_bitrate.currentTextChanged.connect(lambda v: config_manager.set("default_audio_bitrate", v))
        sec_conv.add_row("Default MP3 bitrate", "Preferred audio quality when converting to MP3", self.combo_audio_bitrate)

        # Default Thumbnail format
        self.combo_thumb_fmt = QComboBox()
        self.combo_thumb_fmt.addItems(["JPG", "PNG", "WEBP"])
        self.combo_thumb_fmt.setCurrentText(config_manager.get("default_thumbnail_format", "JPG"))
        self.combo_thumb_fmt.currentTextChanged.connect(lambda v: config_manager.set("default_thumbnail_format", v))
        sec_conv.add_row("Default thumbnail format", "Saved image format for downloaded thumbnails", self.combo_thumb_fmt)

        # FFmpeg custom path
        ff_widget = QWidget()
        ff_layout = QHBoxLayout(ff_widget)
        ff_layout.setContentsMargins(0, 0, 0, 0)
        ff_layout.setSpacing(8)

        self.input_ffmpeg = QLineEdit()
        self.input_ffmpeg.setMinimumWidth(280)
        self.input_ffmpeg.setPlaceholderText("Auto-detected from PATH")
        self.input_ffmpeg.setText(config_manager.get("ffmpeg_path", ""))
        self.input_ffmpeg.textChanged.connect(self._on_ffmpeg_path_changed)
        ff_layout.addWidget(self.input_ffmpeg)

        self.btn_browse_ff = IconButton("folder.svg", "Browse", icon_size=14)
        self.btn_browse_ff.clicked.connect(self._browse_ffmpeg)
        ff_layout.addWidget(self.btn_browse_ff)
        sec_conv.add_row("FFmpeg Executable Path", "Leave blank to use automatically detected system FFmpeg", ff_widget)

        layout.addWidget(sec_conv)

        # 4. Advanced Section
        sec_adv = SettingsSection("Advanced & System")

        # yt-dlp version
        ytdlp_ver = getattr(yt_dlp, "version", None)
        ytdlp_ver_str = getattr(ytdlp_ver, "__version__", "Installed") if ytdlp_ver else "Installed"
        ytdlp_lbl = QLabel(ytdlp_ver_str)
        ytdlp_lbl.setStyleSheet("font-size: 13px; color: #818CF8; font-weight: 600;")
        sec_adv.add_row("yt-dlp Engine Version", "Underlying extractor engine", ytdlp_lbl)

        # FFmpeg detected version
        _, ff_ver = get_ffmpeg_version(config_manager.get("ffmpeg_path"))
        self.lbl_ff_ver = QLabel(ff_ver)
        self.lbl_ff_ver.setStyleSheet("font-size: 13px; color: #10B981; font-weight: 600;")
        sec_adv.add_row("FFmpeg Version", "Media merging and audio conversion binary", self.lbl_ff_ver)

        # Debug logging
        self.chk_debug = QCheckBox()
        self.chk_debug.setChecked(config_manager.get("debug_logging", False))
        self.chk_debug.toggled.connect(lambda v: config_manager.set("debug_logging", v))
        sec_adv.add_row("Debug Logging", "Write detailed extractor and subprocess logs to logs/mediadrop.log", self.chk_debug)

        # Reset button
        btn_reset = QPushButton("Reset All Settings to Default")
        btn_reset.setProperty("role", "danger")
        btn_reset.setFixedWidth(220)
        btn_reset.clicked.connect(self._reset_defaults)
        sec_adv.add_row("Reset Settings", "Restore factory configuration", btn_reset)

        layout.addWidget(sec_adv)
        layout.addStretch(1)

        scroll.setWidget(content_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

    def _browse_download_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            self.input_download_dir.text(),
        )
        if chosen:
            self.input_download_dir.setText(chosen)

    def _browse_ffmpeg(self):
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            "",
            "Executable (*.exe);;All Files (*.*)",
        )
        if chosen:
            self.input_ffmpeg.setText(chosen)

    def _on_ffmpeg_path_changed(self, text: str):
        config_manager.set("ffmpeg_path", text.strip())
        _, ff_ver = get_ffmpeg_version(text.strip() or None)
        self.lbl_ff_ver.setText(ff_ver)
        self.settings_updated.emit()

    def _reset_defaults(self):
        config_manager.reset()
        self.input_download_dir.setText(config_manager.get("download_dir"))
        self.chk_auto_open.setChecked(config_manager.get("auto_open_completed"))
        self.chk_clipboard.setChecked(config_manager.get("clipboard_detection"))
        self.spin_max_concurrent.setValue(config_manager.get("max_concurrent_downloads"))
        self.spin_timeout.setValue(config_manager.get("network_timeout"))
        self.spin_retries.setValue(config_manager.get("retry_count"))
        self.combo_audio_bitrate.setCurrentText(config_manager.get("default_audio_bitrate"))
        self.combo_thumb_fmt.setCurrentText(config_manager.get("default_thumbnail_format"))
        self.input_ffmpeg.setText("")
        self.settings_updated.emit()
