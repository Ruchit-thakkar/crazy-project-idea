"""Download card widget showing real-time progress, speed, ETA, and controls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.database.models import DownloadItem
from app.utils.file_utils import (
    format_bytes,
    open_file_in_os,
    open_folder_in_os,
)
from app.utils.resource_utils import get_asset_path
from ui.widgets.icon_button import IconButton


class DownloadCard(QFrame):
    """Download item card with progress bar, status, metrics, and actions."""

    pause_requested = Signal(str)   # task_id
    resume_requested = Signal(str)  # task_id
    cancel_requested = Signal(str)  # task_id
    retry_requested = Signal(str)   # task_id
    remove_requested = Signal(str)  # task_id

    def __init__(self, item: DownloadItem, parent=None):
        super().__init__(parent)
        self.task_id = item.id
        self.item = item

        self.setObjectName("downloadCard")
        self.setStyleSheet("""
            #downloadCard {
                background-color: #141414;
                border: 1px solid #27272A;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Top row: Title + Status Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.title_lbl = QLabel(item.title)
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #FFFFFF;")
        self.title_lbl.setWordWrap(True)
        top_row.addWidget(self.title_lbl, stretch=1)

        self.status_badge = QLabel(item.status)
        self.status_badge.setStyleSheet(self._get_badge_style(item.status))
        top_row.addWidget(self.status_badge)
        layout.addLayout(top_row)

        # Format & Platform info
        self.info_lbl = QLabel(f"{item.platform} • {item.quality} {item.format_type.upper()}")
        self.info_lbl.setStyleSheet("font-size: 12px; color: #9A9A9A;")
        layout.addWidget(self.info_lbl)

        # Progress Bar + Percentage
        prog_row = QHBoxLayout()
        prog_row.setSpacing(12)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(int(item.progress))
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(8)
        prog_row.addWidget(self.prog_bar, stretch=1)

        self.pct_lbl = QLabel(f"{item.progress:.0f}%")
        self.pct_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
        prog_row.addWidget(self.pct_lbl)
        layout.addLayout(prog_row)

        # Bottom row: Metrics (Size, Speed, ETA) + Action buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        # Metrics label
        self.metrics_lbl = QLabel(self._format_metrics(item))
        self.metrics_lbl.setStyleSheet("font-size: 12px; color: #A1A1AA;")
        bottom_row.addWidget(self.metrics_lbl)
        bottom_row.addStretch()

        # Action Buttons container
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(8)

        self.btn_pause = IconButton("pause.svg", tooltip="Pause", icon_size=14)
        self.btn_pause.clicked.connect(lambda: self.pause_requested.emit(self.task_id))

        self.btn_resume = IconButton("play.svg", tooltip="Resume", icon_size=14)
        self.btn_resume.clicked.connect(lambda: self.resume_requested.emit(self.task_id))

        self.btn_cancel = IconButton("cancel.svg", tooltip="Cancel", icon_size=14)
        self.btn_cancel.clicked.connect(lambda: self.cancel_requested.emit(self.task_id))

        self.btn_retry = IconButton("retry.svg", tooltip="Retry", icon_size=14)
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.task_id))

        self.btn_open_file = IconButton("file.svg", tooltip="Open File", icon_size=14)
        self.btn_open_file.clicked.connect(self._open_file)

        self.btn_open_folder = IconButton("folder.svg", tooltip="Open Folder", icon_size=14)
        self.btn_open_folder.clicked.connect(self._open_folder)

        self.btn_remove = IconButton("trash.svg", tooltip="Remove", icon_size=14)
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.task_id))

        for btn in [
            self.btn_pause, self.btn_resume, self.btn_cancel,
            self.btn_retry, self.btn_open_file, self.btn_open_folder,
            self.btn_remove
        ]:
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1B1B1B;
                    border: 1px solid #2E2E32;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #27272A;
                    border-color: #3F3F46;
                }
            """)
            self.actions_layout.addWidget(btn)

        bottom_row.addLayout(self.actions_layout)
        layout.addLayout(bottom_row)

        self.update_state(item)

    def update_state(self, item: DownloadItem):
        """Update display with real-time download item data."""
        self.item = item
        self.title_lbl.setText(item.title)
        self.status_badge.setText(item.status)
        self.status_badge.setStyleSheet(self._get_badge_style(item.status))

        self.prog_bar.setValue(int(item.progress))
        self.pct_lbl.setText(f"{item.progress:.0f}%")
        self.metrics_lbl.setText(self._format_metrics(item))

        # Show/hide relevant buttons depending on status
        st = item.status.lower()
        self.btn_pause.hide()
        self.btn_resume.hide()
        self.btn_cancel.hide()
        self.btn_retry.hide()
        self.btn_open_file.hide()
        self.btn_open_folder.hide()
        self.btn_remove.hide()

        if st in ("downloading", "queued", "analyzing", "processing", "merging", "converting"):
            self.btn_pause.show()
            self.btn_cancel.show()
        elif st == "paused":
            self.btn_resume.show()
            self.btn_cancel.show()
        elif st == "failed":
            self.btn_retry.show()
            self.btn_remove.show()
        elif st == "cancelled":
            self.btn_retry.show()
            self.btn_remove.show()
        elif st == "completed":
            self.btn_open_file.show()
            self.btn_open_folder.show()
            self.btn_remove.show()

    def _format_metrics(self, item: DownloadItem) -> str:
        st = item.status.lower()
        if st == "completed":
            return f"Finished • {format_bytes(item.file_size)}"
        elif st == "failed":
            return f"Error: {item.error_message or 'Download failed'}"
        elif st in ("merging", "converting", "processing"):
            return f"FFmpeg {item.status}..."
        elif st == "queued":
            return "Waiting in queue..."
        elif st == "paused":
            return "Paused"
        elif st == "cancelled":
            return "Cancelled by user"

        # Active downloading
        dl_str = format_bytes(item.downloaded_bytes)
        tot_str = format_bytes(item.total_bytes) if item.total_bytes > 0 else "Unknown"
        speed_str = item.speed
        eta_str = item.eta
        return f"{dl_str} / {tot_str}  •  {speed_str}  •  {eta_str}"

    def _open_file(self):
        if self.item.file_path:
            open_file_in_os(self.item.file_path)

    def _open_folder(self):
        if self.item.file_path:
            open_folder_in_os(self.item.file_path)

    def _get_badge_style(self, status: str) -> str:
        base = "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid "
        st = status.lower()
        if st == "completed":
            return base + "rgba(16, 185, 129, 0.4); background-color: rgba(16, 185, 129, 0.12); color: #10B981;"
        elif st == "failed":
            return base + "rgba(239, 68, 68, 0.4); background-color: rgba(239, 68, 68, 0.12); color: #EF4444;"
        elif st in ("merging", "converting", "processing"):
            return base + "rgba(245, 158, 11, 0.4); background-color: rgba(245, 158, 11, 0.12); color: #F59E0B;"
        elif st == "downloading":
            return base + "rgba(99, 102, 241, 0.4); background-color: rgba(99, 102, 241, 0.12); color: #818CF8;"
        else:
            return base + "#383838; background-color: #1F1F23; color: #9A9A9A;"
