"""Download history view with search, platform filtering, and file operations."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.database import db
from app.database.models import HistoryRecord
from app.utils.file_utils import (
    format_bytes,
    open_file_in_os,
    open_folder_in_os,
)
from ui.widgets.icon_button import IconButton


class HistoryCard(QFrame):
    """Card displaying a single downloaded media history record."""

    redownload_requested = Signal(str)  # url
    delete_requested = Signal(int)      # record_id

    def __init__(self, record: HistoryRecord, parent=None):
        super().__init__(parent)
        self.record = record

        self.setObjectName("historyCard")
        self.setStyleSheet("""
            #historyCard {
                background-color: #141414;
                border: 1px solid #27272A;
                border-radius: 10px;
            }
            #historyCard:hover {
                background-color: #18181C;
                border-color: #383838;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # Left: Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title_lbl = QLabel(record.title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #FFFFFF;")
        info_layout.addWidget(title_lbl)

        meta_str = f"{record.platform} • {record.quality} {record.format_type.upper()} • {format_bytes(record.file_size)} • {record.downloaded_at}"
        meta_lbl = QLabel(meta_str)
        meta_lbl.setStyleSheet("font-size: 12px; color: #71717A;")
        info_layout.addWidget(meta_lbl)

        layout.addLayout(info_layout, stretch=1)

        # Right: Actions
        btn_open = IconButton("file.svg", tooltip="Open File", icon_size=14)
        btn_open.clicked.connect(lambda: open_file_in_os(record.file_path))

        btn_folder = IconButton("folder.svg", tooltip="Open Folder", icon_size=14)
        btn_folder.clicked.connect(lambda: open_folder_in_os(record.file_path))

        btn_copy = IconButton("copy.svg", tooltip="Copy URL", icon_size=14)
        btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(record.url))

        btn_redownload = IconButton("retry.svg", tooltip="Analyze / Redownload", icon_size=14)
        btn_redownload.clicked.connect(lambda: self.redownload_requested.emit(record.url))

        btn_delete = IconButton("trash.svg", tooltip="Delete Record", icon_size=14)
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(record.id or 0))

        for b in [btn_open, btn_folder, btn_copy, btn_redownload, btn_delete]:
            b.setFixedSize(28, 28)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #1B1B1B;
                    border: 1px solid #2E2E32;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #27272A;
                }
            """)
            layout.addWidget(b)


class HistoryPage(QWidget):
    """History page allowing users to search, filter, and access downloaded media."""

    redownload_url = Signal(str)  # url

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title = QLabel("Download History")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #FFFFFF;")
        title_layout.addWidget(title)

        subtitle = QLabel("View past downloads and open files")
        subtitle.setStyleSheet("font-size: 13px; color: #9A9A9A;")
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        self.btn_clear_all = IconButton("trash.svg", "Clear History", icon_size=14)
        self.btn_clear_all.clicked.connect(self._clear_all_history)
        header_layout.addWidget(self.btn_clear_all)
        layout.addLayout(header_layout)

        # Filter bar (Search + Platform combo)
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search history by title or URL...")
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self.reload_history)
        filter_bar.addWidget(self.search_input, stretch=1)

        self.platform_filter = QComboBox()
        self.platform_filter.setFixedHeight(38)
        self.platform_filter.addItems([
            "All Platforms",
            "YouTube",
            "Instagram",
            "TikTok",
            "Facebook",
            "X",
            "Pinterest",
        ])
        self.platform_filter.currentTextChanged.connect(self.reload_history)
        filter_bar.addWidget(self.platform_filter)
        layout.addLayout(filter_bar)

        # Scrollable container for records
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.records_container = QWidget()
        self.records_layout = QVBoxLayout(self.records_container)
        self.records_layout.setContentsMargins(0, 10, 0, 10)
        self.records_layout.setSpacing(10)
        self.records_layout.setAlignment(Qt.AlignTop)

        self.empty_label = QLabel("No download history found.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 14px; color: #52525B; padding: 60px 0;")
        self.records_layout.addWidget(self.empty_label)

        scroll.setWidget(self.records_container)
        layout.addWidget(scroll)

        self.reload_history()

    def reload_history(self):
        """Query SQLite database and populate records."""
        # Clear existing cards
        while self.records_layout.count() > 1:
            child = self.records_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        search_text = self.search_input.text()
        platform_text = self.platform_filter.currentText()
        records = db.get_history(search=search_text, platform=platform_text)

        if records:
            self.empty_label.hide()
            for r in records:
                card = HistoryCard(r, parent=self.records_container)
                card.redownload_requested.connect(self.redownload_url.emit)
                card.delete_requested.connect(self._delete_record)
                self.records_layout.insertWidget(self.records_layout.count() - 1, card)
        else:
            self.empty_label.show()

    def _delete_record(self, record_id: int):
        if record_id:
            db.delete_history(record_id)
            self.reload_history()

    def _clear_all_history(self):
        db.clear_all_history()
        self.reload_history()
