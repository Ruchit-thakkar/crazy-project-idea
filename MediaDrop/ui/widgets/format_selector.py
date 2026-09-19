"""Format selection widget ('What do you want to download?')."""

import webbrowser
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.models import (
    AudioQuality,
    ImageItem,
    MediaMetadata,
    ThumbnailQuality,
    VideoQuality,
)
from app.utils.file_utils import format_bytes, format_duration
from app.utils.resource_utils import get_asset_path
from ui.styles.theme import Theme
from ui.widgets.icon_button import IconButton


class QualityCard(QFrame):
    """Clickable selectable card representing a specific video or audio quality."""

    selected = Signal(object)  # emits self

    def __init__(self, item_data: object, is_video: bool = True, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.is_video = is_video
        self._is_checked = False

        self.setObjectName("qualityCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(72)
        self._update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Radio circle indicator
        self.radio = QRadioButton()
        self.radio.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.radio)

        # Content details
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        if is_video and isinstance(item_data, VideoQuality):
            # Resolution Badge
            res_lbl = QLabel(item_data.resolution)
            res_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
            top_row.addWidget(res_lbl)

            if item_data.fps and item_data.fps > 30:
                fps_badge = QLabel(f"{item_data.fps} FPS")
                fps_badge.setStyleSheet("""
                    background-color: #202025;
                    color: #818CF8;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 2px 6px;
                    border-radius: 4px;
                """)
                top_row.addWidget(fps_badge)

            if item_data.width and item_data.height:
                dim_lbl = QLabel(f"{item_data.width} × {item_data.height}")
                dim_lbl.setStyleSheet("font-size: 12px; color: #71717A;")
                top_row.addWidget(dim_lbl)

            top_row.addStretch()

            # Size label
            size_str = f"~{format_bytes(item_data.filesize_est)}" if item_data.filesize_est else "Dynamic size"
            self.size_lbl = QLabel(size_str)
            self.size_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #E4E4E7;")
            top_row.addWidget(self.size_lbl)
            info_layout.addLayout(top_row)

            # Bottom row details
            sub_row = QHBoxLayout()
            codec_info = f"{item_data.vcodec} • {item_data.acodec} • MP4"
            codec_lbl = QLabel(codec_info)
            codec_lbl.setStyleSheet("font-size: 11px; color: #9A9A9A;")
            sub_row.addWidget(codec_lbl)
            sub_row.addStretch()
            info_layout.addLayout(sub_row)

        elif not is_video and isinstance(item_data, AudioQuality):
            bitrate_lbl = QLabel(item_data.bitrate)
            bitrate_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
            top_row.addWidget(bitrate_lbl)

            fmt_badge = QLabel("MP3")
            fmt_badge.setStyleSheet("""
                background-color: #202025;
                color: #10B981;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 4px;
            """)
            top_row.addWidget(fmt_badge)
            top_row.addStretch()

            size_str = f"~{format_bytes(item_data.filesize_est)}" if item_data.filesize_est else ""
            self.size_lbl = QLabel(size_str)
            self.size_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #E4E4E7;")
            top_row.addWidget(self.size_lbl)
            info_layout.addLayout(top_row)

            sub_row = QHBoxLayout()
            dur_str = f"Duration: {format_duration(item_data.duration)}" if item_data.duration else "Full audio track"
            sub_lbl = QLabel(f"High Quality Audio • {dur_str}")
            sub_lbl.setStyleSheet("font-size: 11px; color: #9A9A9A;")
            sub_row.addWidget(sub_lbl)
            sub_row.addStretch()
            info_layout.addLayout(sub_row)

        layout.addLayout(info_layout, stretch=1)

    def mousePressEvent(self, event):
        self.setChecked(True)
        self.selected.emit(self)
        super().mousePressEvent(event)

    def setChecked(self, checked: bool):
        self._is_checked = checked
        self.radio.setChecked(checked)
        self._update_style()

    def isChecked(self) -> bool:
        return self._is_checked

    def _update_style(self):
        if self._is_checked:
            self.setStyleSheet("""
                #qualityCard {
                    background-color: #1A1A22;
                    border: 1.5px solid #6366F1;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                #qualityCard {
                    background-color: #18181B;
                    border: 1px solid #27272A;
                    border-radius: 10px;
                }
                #qualityCard:hover {
                    background-color: #202025;
                    border-color: #3F3F46;
                }
            """)


class FormatSelector(QFrame):
    """'What do you want to download?' widget with VIDEO, AUDIO, IMAGE, THUMBNAIL tabs."""

    # format_type ('video', 'audio', 'thumbnail', 'image'), quality_label, format_id, custom_thumb_url, thumb_fmt, custom_urls
    download_clicked = Signal(str, str, str, str, str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_metadata: Optional[MediaMetadata] = None
        self.selected_format_type = "video"  # "video", "audio", "image", "thumbnail"
        self.video_cards: List[QualityCard] = []
        self.audio_cards: List[QualityCard] = []
        self.thumb_cards: List[QRadioButton] = []
        self.image_checkboxes: List[QCheckBox] = []

        self.setObjectName("formatSelector")
        self.setStyleSheet("""
            #formatSelector {
                background-color: #141414;
                border: 1px solid #292929;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        # Section Title
        header_layout = QHBoxLayout()
        title = QLabel("What do you want to download?")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Category Tabs (VIDEO / AUDIO / IMAGE / THUMBNAIL)
        tab_container = QFrame()
        tab_container.setStyleSheet("""
            QFrame {
                background-color: #18181B;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 2px;
            }
        """)
        tab_layout = QHBoxLayout(tab_container)
        tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_layout.setSpacing(4)

        self.tab_video = self._create_tab_btn("VIDEO (MP4)", True)
        self.tab_audio = self._create_tab_btn("AUDIO (MP3)", False)
        self.tab_image = self._create_tab_btn("IMAGE / PHOTOS", False)
        self.tab_thumb = self._create_tab_btn("THUMBNAIL", False)

        self.tab_video.clicked.connect(lambda: self._switch_tab("video"))
        self.tab_audio.clicked.connect(lambda: self._switch_tab("audio"))
        self.tab_image.clicked.connect(lambda: self._switch_tab("image"))
        self.tab_thumb.clicked.connect(lambda: self._switch_tab("thumbnail"))

        tab_layout.addWidget(self.tab_video)
        tab_layout.addWidget(self.tab_audio)
        tab_layout.addWidget(self.tab_image)
        tab_layout.addWidget(self.tab_thumb)
        layout.addWidget(tab_container)

        # Stacked pages for each category
        self.stack = QStackedWidget()

        # 1. Video page (Index 0)
        self.video_page = QWidget()
        self.video_layout = QVBoxLayout(self.video_page)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setSpacing(8)
        self.stack.addWidget(self.video_page)

        # 2. Audio page (Index 1)
        self.audio_page = QWidget()
        self.audio_layout = QVBoxLayout(self.audio_page)
        self.audio_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_layout.setSpacing(8)
        self.stack.addWidget(self.audio_page)

        # 3. Image page (Index 2)
        self.image_page = self._build_image_page()
        self.stack.addWidget(self.image_page)

        # 4. Thumbnail page (Index 3)
        self.thumb_page = self._build_thumbnail_page()
        self.stack.addWidget(self.thumb_page)

        layout.addWidget(self.stack)

        # Action bar with Download button
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setProperty("role", "primary")
        self.download_btn.setFixedHeight(44)
        self.download_btn.setMinimumWidth(190)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 600;
                border-radius: 8px;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
        """)
        self.download_btn.clicked.connect(self._on_download_clicked)
        action_layout.addWidget(self.download_btn)
        layout.addLayout(action_layout)

    def _create_tab_btn(self, text: str, checked: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setAutoExclusive(True)
        btn.setFixedHeight(34)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A1A1AA;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QPushButton:checked {
                background-color: #27272A;
                color: #FFFFFF;
                border: 1px solid #3F3F46;
            }
        """)
        return btn

    def _switch_tab(self, tab_type: str):
        self.selected_format_type = tab_type
        if tab_type == "video":
            self.stack.setCurrentIndex(0)
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Download Video (MP4)")
            self.tab_video.setChecked(True)
        elif tab_type == "audio":
            self.stack.setCurrentIndex(1)
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Download Audio (MP3)")
            self.tab_audio.setChecked(True)
        elif tab_type == "image":
            self.stack.setCurrentIndex(2)
            self.tab_image.setChecked(True)
            self._update_image_download_btn()
        elif tab_type == "thumbnail":
            self.stack.setCurrentIndex(3)
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Download Thumbnail")
            self.tab_thumb.setChecked(True)

    def _build_image_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(14)

        # Header with found count & Select All
        top_row = QHBoxLayout()
        self.image_count_lbl = QLabel("Image:")
        self.image_count_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #9A9A9A;")
        top_row.addWidget(self.image_count_lbl)
        top_row.addStretch()

        self.btn_select_all_imgs = QPushButton("Deselect All")
        self.btn_select_all_imgs.setCursor(Qt.PointingHandCursor)
        self.btn_select_all_imgs.setStyleSheet("""
            QPushButton {
                background-color: #1B1B1B;
                color: #818CF8;
                border: 1px solid #2E2E32;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #262629;
            }
        """)
        self.btn_select_all_imgs.clicked.connect(self._toggle_select_all_images)
        self.btn_select_all_imgs.hide()
        top_row.addWidget(self.btn_select_all_imgs)
        layout.addLayout(top_row)

        # Container for image presentation (single card or gallery checklist)
        self.image_items_container = QVBoxLayout()
        self.image_items_container.setSpacing(8)
        layout.addLayout(self.image_items_container)

        # Format selector (JPG / PNG / WEBP)
        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Save format:")
        fmt_lbl.setStyleSheet("font-size: 13px; color: #9A9A9A;")
        fmt_row.addWidget(fmt_lbl)

        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(["JPG", "PNG", "WEBP"])
        self.image_format_combo.setFixedWidth(100)
        self.image_format_combo.currentTextChanged.connect(self._on_image_format_changed)
        fmt_row.addWidget(self.image_format_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # Quick utility buttons: Copy URL, Open URL
        util_row = QHBoxLayout()
        util_row.setSpacing(10)

        self.btn_copy_image_url = IconButton("copy.svg", "Copy Image Link", icon_size=14)
        self.btn_copy_image_url.clicked.connect(self._copy_image_url)
        util_row.addWidget(self.btn_copy_image_url)

        self.btn_open_image_url = IconButton("external.svg", "Open in Browser", icon_size=14)
        self.btn_open_image_url.clicked.connect(self._open_image_url)
        util_row.addWidget(self.btn_open_image_url)

        util_row.addStretch()
        layout.addLayout(util_row)

        return widget

    def _build_thumbnail_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(14)

        # Quality options container
        q_label = QLabel("Available quality:")
        q_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #9A9A9A;")
        layout.addWidget(q_label)

        self.thumb_qualities_container = QVBoxLayout()
        self.thumb_qualities_container.setSpacing(8)
        layout.addLayout(self.thumb_qualities_container)

        # Format selector (JPG / PNG / WEBP)
        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Convert format:")
        fmt_lbl.setStyleSheet("font-size: 13px; color: #9A9A9A;")
        fmt_row.addWidget(fmt_lbl)

        self.thumb_format_combo = QComboBox()
        self.thumb_format_combo.addItems(["JPG", "PNG", "WEBP"])
        self.thumb_format_combo.setFixedWidth(100)
        fmt_row.addWidget(self.thumb_format_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # Quick utility buttons: Copy URL, Open URL
        util_row = QHBoxLayout()
        util_row.setSpacing(10)

        self.btn_copy_thumb_url = IconButton("copy.svg", "Copy Thumbnail URL", icon_size=14)
        self.btn_copy_thumb_url.clicked.connect(self._copy_thumbnail_url)
        util_row.addWidget(self.btn_copy_thumb_url)

        self.btn_open_thumb_url = IconButton("external.svg", "Open Thumbnail in Browser", icon_size=14)
        self.btn_open_thumb_url.clicked.connect(self._open_thumbnail_url)
        util_row.addWidget(self.btn_open_thumb_url)

        util_row.addStretch()
        layout.addLayout(util_row)

        return widget

    def populate(self, meta: MediaMetadata):
        """Populate format options dynamically based on metadata."""
        self.current_metadata = meta

        # 1. Clear previous video cards
        for c in self.video_cards:
            c.deleteLater()
        self.video_cards.clear()

        if meta.video_qualities:
            for i, vq in enumerate(meta.video_qualities):
                card = QualityCard(vq, is_video=True, parent=self.video_page)
                card.selected.connect(self._on_video_card_selected)
                if i == 0:
                    card.setChecked(True)
                self.video_layout.addWidget(card)
                self.video_cards.append(card)
        else:
            no_vid = QLabel("No direct video stream detected for this media.")
            no_vid.setStyleSheet("color: #71717A; font-style: italic; padding: 10px 0;")
            self.video_layout.addWidget(no_vid)

        # 2. Clear previous audio cards
        for c in self.audio_cards:
            c.deleteLater()
        self.audio_cards.clear()

        if meta.audio_qualities:
            for i, aq in enumerate(meta.audio_qualities):
                card = QualityCard(aq, is_video=False, parent=self.audio_page)
                card.selected.connect(self._on_audio_card_selected)
                if i == 0:
                    card.setChecked(True)
                self.audio_layout.addWidget(card)
                self.audio_cards.append(card)

        # 3. Clear previous image widgets
        self.image_checkboxes.clear()
        while self.image_items_container.count() > 0:
            child = self.image_items_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Populate Image Tab
        if meta.image_items:
            count = len(meta.image_items)
            if count == 1:
                # Single Image View: Clean card, no checkboxes, no "Select All"
                self.image_count_lbl.setText("Detected Photo / Image:")
                self.btn_select_all_imgs.hide()

                single_img = meta.image_items[0]
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background-color: #1A1A22;
                        border: 1.5px solid #6366F1;
                        border-radius: 10px;
                        padding: 12px;
                    }
                """)
                c_layout = QVBoxLayout(card)
                c_layout.setSpacing(4)

                lbl_main = QLabel(f"● {single_img.resolution_str or 'Original HD Resolution'}")
                lbl_main.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF;")
                c_layout.addWidget(lbl_main)

                lbl_sub = QLabel("100% Original full resolution image from source")
                lbl_sub.setStyleSheet("font-size: 12px; color: #A1A1AA;")
                c_layout.addWidget(lbl_sub)

                self.image_items_container.addWidget(card)
            else:
                # Multiple Images (Gallery): Checkbox list with Select All
                self.image_count_lbl.setText(f"Detected Gallery ({count} photos):")
                self.btn_select_all_imgs.setText("Deselect All")
                self.btn_select_all_imgs.show()

                for i, img in enumerate(meta.image_items):
                    chk = QCheckBox(f"{img.title or f'Photo {i+1}'} — {img.resolution_str or 'High Resolution'}")
                    chk.setChecked(True)
                    chk.setProperty("img_url", img.url)
                    chk.setStyleSheet("font-size: 13px; color: #FFFFFF; padding: 4px 0;")
                    chk.toggled.connect(self._on_image_checkbox_changed)
                    self.image_items_container.addWidget(chk)
                    self.image_checkboxes.append(chk)
        else:
            self.image_count_lbl.setText("No image detected.")
            self.btn_select_all_imgs.hide()

        # 4. Clear previous thumbnail radio items
        for r in self.thumb_cards:
            r.deleteLater()
        self.thumb_cards.clear()

        if meta.thumbnail_qualities:
            for i, tq in enumerate(meta.thumbnail_qualities):
                rb = QRadioButton(f"{tq.label} ({tq.resolution_str})")
                rb.setProperty("thumb_url", tq.url)
                rb.setProperty("thumb_label", tq.label)
                rb.setStyleSheet("font-size: 13px; color: #FFFFFF;")
                if i == 0:
                    rb.setChecked(True)
                self.thumb_qualities_container.addWidget(rb)
                self.thumb_cards.append(rb)

        # Tab visibility & Default tab
        has_videos = bool(meta.video_qualities)
        has_images = bool(meta.image_items)

        # If it's pure image/photo content, focus on IMAGE tab!
        if (meta.media_type in ("Image", "Photo Gallery") or not has_videos) and has_images:
            self._switch_tab("image")
        else:
            self._switch_tab("video")

    def _on_image_format_changed(self, text: str):
        if self.selected_format_type == "image":
            self._update_image_download_btn()

    def _on_image_checkbox_changed(self):
        self._update_image_download_btn()

    def _update_image_download_btn(self):
        fmt = self.image_format_combo.currentText()
        if not self.current_metadata or not self.current_metadata.image_items:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("No Image Available")
            return

        if len(self.current_metadata.image_items) == 1:
            self.download_btn.setEnabled(True)
            self.download_btn.setText(f"Download Image ({fmt})")
            return

        # Multiple images
        checked_count = sum(1 for c in self.image_checkboxes if c.isChecked())
        if checked_count == 0:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("Select an Image to Download")
            self.btn_select_all_imgs.setText("Select All")
        else:
            self.download_btn.setEnabled(True)
            self.download_btn.setText(f"Download Selected Photos ({checked_count})")
            if checked_count == len(self.image_checkboxes):
                self.btn_select_all_imgs.setText("Deselect All")
            else:
                self.btn_select_all_imgs.setText("Select All")

    def _toggle_select_all_images(self):
        all_checked = all(c.isChecked() for c in self.image_checkboxes)
        new_state = not all_checked
        for c in self.image_checkboxes:
            c.setChecked(new_state)
        self._update_image_download_btn()

    def _on_video_card_selected(self, selected_card: QualityCard):
        for c in self.video_cards:
            if c != selected_card:
                c.setChecked(False)

    def _on_audio_card_selected(self, selected_card: QualityCard):
        for c in self.audio_cards:
            if c != selected_card:
                c.setChecked(False)

    def _get_selected_thumbnail_url(self) -> str:
        for r in self.thumb_cards:
            if r.isChecked():
                return r.property("thumb_url") or ""
        return self.current_metadata.thumbnail_url if self.current_metadata else ""

    def _get_selected_image_urls(self) -> List[str]:
        selected = []
        for chk in self.image_checkboxes:
            if chk.isChecked():
                url = chk.property("img_url")
                if url:
                    selected.append(url)
        if not selected and self.current_metadata and self.current_metadata.image_items:
            selected.append(self.current_metadata.image_items[0].url)
        return selected

    def _copy_thumbnail_url(self):
        url = self._get_selected_thumbnail_url()
        if url:
            cb = QGuiApplication.clipboard()
            cb.setText(url)

    def _open_thumbnail_url(self):
        url = self._get_selected_thumbnail_url()
        if url:
            webbrowser.open(url)

    def _copy_image_url(self):
        urls = self._get_selected_image_urls()
        if urls:
            cb = QGuiApplication.clipboard()
            cb.setText(urls[0])

    def _open_image_url(self):
        urls = self._get_selected_image_urls()
        if urls:
            webbrowser.open(urls[0])

    def _on_download_clicked(self):
        if not self.current_metadata:
            return

        fmt_type = self.selected_format_type
        quality_str = ""
        format_id = ""
        thumb_url = ""
        thumb_fmt = "JPG"
        custom_urls: List[str] = []

        if fmt_type == "video":
            for c in self.video_cards:
                if c.isChecked() and isinstance(c.item_data, VideoQuality):
                    quality_str = c.item_data.resolution
                    format_id = c.item_data.format_id
                    break
            if not quality_str and self.video_cards:
                quality_str = self.video_cards[0].item_data.resolution  # type: ignore
                format_id = self.video_cards[0].item_data.format_id  # type: ignore

        elif fmt_type == "audio":
            for c in self.audio_cards:
                if c.isChecked() and isinstance(c.item_data, AudioQuality):
                    quality_str = c.item_data.bitrate
                    break
            if not quality_str and self.audio_cards:
                quality_str = self.audio_cards[0].item_data.bitrate  # type: ignore

        elif fmt_type == "image":
            custom_urls = self._get_selected_image_urls()
            thumb_fmt = self.image_format_combo.currentText()
            quality_str = thumb_fmt
            thumb_url = custom_urls[0] if custom_urls else ""

        elif fmt_type == "thumbnail":
            thumb_url = self._get_selected_thumbnail_url()
            thumb_fmt = self.thumb_format_combo.currentText()
            quality_str = thumb_fmt

        self.download_clicked.emit(fmt_type, quality_str, format_id, thumb_url, thumb_fmt, custom_urls)
