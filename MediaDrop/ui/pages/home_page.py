"""Home page with large URL input, platform detection, and format selection."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.controllers.main_controller import main_controller
from app.database.models import DownloadItem, MediaMetadata
from app.extractors.yt_dlp_extractor import detect_platform
from app.utils.resource_utils import get_asset_path
from ui.dialogs.error_dialog import ErrorDialog
from ui.widgets.format_selector import FormatSelector
from ui.widgets.icon_button import IconButton
from ui.widgets.media_card import MediaCard


class HomePage(QWidget):
    """Home view for URL input, analysis, metadata display, and format selection."""

    download_started = Signal(str)  # task_id (switches to downloads page if desired)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.current_metadata: Optional[MediaMetadata] = None

        # Main scrollable area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content_widget = QWidget()
        self.layout = QVBoxLayout(content_widget)
        self.layout.setContentsMargins(40, 36, 40, 40)
        self.layout.setSpacing(24)

        # 1. Hero Section
        hero_layout = QVBoxLayout()
        hero_layout.setSpacing(6)
        hero_layout.setAlignment(Qt.AlignCenter)

        hero_title = QLabel("Download Media From Anywhere")
        hero_title.setAlignment(Qt.AlignCenter)
        hero_title.setStyleSheet("font-size: 26px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px;")
        hero_layout.addWidget(hero_title)

        hero_subtitle = QLabel("Paste any public media URL to detect formats, audio, and high-res thumbnails")
        hero_subtitle.setAlignment(Qt.AlignCenter)
        hero_subtitle.setStyleSheet("font-size: 13px; color: #9A9A9A; font-weight: 400;")
        hero_layout.addWidget(hero_subtitle)
        self.layout.addLayout(hero_layout)

        # 2. URL Input Card
        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_card.setStyleSheet("""
            #inputCard {
                background-color: #141414;
                border: 1.5px solid #27272A;
                border-radius: 12px;
            }
            #inputCard:hover {
                border-color: #383838;
            }
        """)
        input_card_layout = QVBoxLayout(input_card)
        input_card_layout.setContentsMargins(18, 16, 18, 16)
        input_card_layout.setSpacing(12)

        input_header = QHBoxLayout()
        input_label = QLabel("Paste a media URL")
        input_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #71717A; text-transform: uppercase;")
        input_header.addWidget(input_label)
        input_header.addStretch()

        self.detected_platform_lbl = QLabel("")
        self.detected_platform_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #818CF8;")
        input_header.addWidget(self.detected_platform_lbl)
        input_card_layout.addLayout(input_header)

        # Input Row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=... or Instagram, TikTok, Facebook, X, Pinterest")
        self.url_input.setFixedHeight(48)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1B1B1B;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 14px;
                color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 1px solid #6366F1;
                background-color: #202025;
            }
        """)
        self.url_input.textChanged.connect(self._on_url_text_changed)
        self.url_input.returnPressed.connect(self.analyze_current_url)
        input_row.addWidget(self.url_input, stretch=1)

        # Paste Button
        self.btn_paste = IconButton("copy.svg", "Paste", tooltip="Paste from Clipboard", icon_size=14)
        self.btn_paste.setFixedHeight(48)
        self.btn_paste.setFixedWidth(85)
        self.btn_paste.clicked.connect(self._paste_clipboard)
        input_row.addWidget(self.btn_paste)

        # Clear Button
        self.btn_clear = IconButton("close.svg", tooltip="Clear URL", icon_size=14)
        self.btn_clear.setFixedHeight(48)
        self.btn_clear.setFixedWidth(48)
        self.btn_clear.clicked.connect(self._clear_url)
        input_row.addWidget(self.btn_clear)

        # Analyze Button
        self.btn_analyze = QPushButton("Analyze URL")
        self.btn_analyze.setProperty("role", "primary")
        self.btn_analyze.setFixedHeight(48)
        self.btn_analyze.setFixedWidth(140)
        self.btn_analyze.setCursor(Qt.PointingHandCursor)
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton:disabled {
                background-color: #312E81;
                color: #A5B4FC;
            }
        """)
        self.btn_analyze.clicked.connect(self.analyze_current_url)
        input_row.addWidget(self.btn_analyze)

        input_card_layout.addLayout(input_row)

        # Supported Platforms Bar (Section 4 & 15)
        platform_bar = QHBoxLayout()
        platform_bar.setSpacing(12)
        platform_bar.setAlignment(Qt.AlignCenter)

        platforms = [
            ("YouTube", "#FF0000"),
            ("Instagram", "#E1306C"),
            ("TikTok", "#00F2FE"),
            ("Facebook", "#1877F2"),
            ("X", "#FFFFFF"),
            ("Pinterest", "#BD081C"),
        ]
        for name, color in platforms:
            p_lbl = QLabel(f"● {name}")
            p_lbl.setStyleSheet(f"font-size: 12px; color: #71717A; font-weight: 500;")
            platform_bar.addWidget(p_lbl)

        input_card_layout.addLayout(platform_bar)
        self.layout.addWidget(input_card)

        # 3. Loading Indicator
        self.loading_frame = QFrame()
        self.loading_frame.setStyleSheet("""
            QFrame {
                background-color: #141414;
                border: 1px solid #27272A;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        loading_layout = QVBoxLayout(self.loading_frame)
        loading_layout.setSpacing(10)
        loading_layout.setAlignment(Qt.AlignCenter)

        self.loading_lbl = QLabel("Analyzing media URL and detecting available qualities...")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        self.loading_lbl.setStyleSheet("font-size: 13px; color: #818CF8; font-weight: 600;")
        loading_layout.addWidget(self.loading_lbl)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # Indeterminate animation
        self.loading_bar.setFixedHeight(6)
        self.loading_bar.setTextVisible(False)
        loading_layout.addWidget(self.loading_bar)

        self.loading_frame.hide()
        self.layout.addWidget(self.loading_frame)

        # 4. Media Metadata Display Card
        self.media_card = MediaCard()
        self.media_card.hide()
        self.layout.addWidget(self.media_card)

        # 5. Format Selection Section ("What do you want to download?")
        self.format_selector = FormatSelector()
        self.format_selector.download_clicked.connect(self._on_download_confirmed)
        self.format_selector.hide()
        self.layout.addWidget(self.format_selector)

        # Stretch to keep layout neat
        self.layout.addStretch(1)

        scroll.setWidget(content_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

        # Connect controller signals
        main_controller.analysis_started.connect(self._on_analysis_started)
        main_controller.analysis_finished.connect(self._on_analysis_finished)
        main_controller.analysis_error.connect(self._on_analysis_error)

    def set_url(self, url: str):
        self.url_input.setText(url)
        self._on_url_text_changed(url)

    def focus_url_input(self):
        self.url_input.setFocus()
        self.url_input.selectAll()

    def _on_url_text_changed(self, text: str):
        platform = detect_platform(text)
        if text.strip() and platform != "Unknown":
            self.detected_platform_lbl.setText(f"● {platform} Detected")
        else:
            self.detected_platform_lbl.setText("")

    def _paste_clipboard(self):
        cb = QGuiApplication.clipboard()
        txt = cb.text().strip()
        if txt:
            self.url_input.setText(txt)
            self._on_url_text_changed(txt)

    def _clear_url(self):
        self.url_input.clear()
        self.detected_platform_lbl.setText("")
        self.media_card.hide()
        self.format_selector.hide()

    def analyze_current_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        main_controller.start_analysis(url)

    def _on_analysis_started(self, url: str):
        self.btn_analyze.setEnabled(False)
        self.loading_frame.show()
        self.media_card.hide()
        self.format_selector.hide()

    def _on_analysis_finished(self, meta: MediaMetadata):
        self.btn_analyze.setEnabled(True)
        self.loading_frame.hide()
        self.current_metadata = meta

        # Populate UI
        self.media_card.set_metadata(meta)
        self.media_card.show()

        self.format_selector.populate(meta)
        self.format_selector.show()

    def _on_analysis_error(self, friendly: str, details: str):
        self.btn_analyze.setEnabled(True)
        self.loading_frame.hide()
        dlg = ErrorDialog("Analysis Notice", friendly, details, parent=self)
        dlg.exec()

    def _on_download_confirmed(
        self,
        format_type: str,
        quality_str: str,
        format_id: str,
        thumb_url: str,
        thumb_fmt: str,
    ):
        if not self.current_metadata:
            return

        item = DownloadItem(
            url=self.current_metadata.url,
            title=self.current_metadata.title,
            platform=self.current_metadata.platform,
            format_type=format_type,
            quality=quality_str,
            selected_format_id=format_id,
            thumbnail_url=thumb_url or self.current_metadata.thumbnail_url,
            status="Queued",
        )

        main_controller.enqueue_download(item)
        self.download_started.emit(item.id)

    # Drag and Drop handlers
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                # If a local text file was dropped, read first line
                first_url = urls[0]
                if first_url.isLocalFile():
                    p = first_url.toLocalFile()
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("http"):
                                    self.set_url(line)
                                    self.analyze_current_url()
                                    break
                    except Exception:
                        pass
                else:
                    self.set_url(first_url.toString())
                    self.analyze_current_url()
        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if text.startswith("http"):
                self.set_url(text)
                self.analyze_current_url()
        event.acceptProposedAction()
