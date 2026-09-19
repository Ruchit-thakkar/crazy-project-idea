"""Downloads manager page showing active, queued, and completed downloads."""

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.controllers.main_controller import main_controller
from app.database.models import DownloadItem
from ui.widgets.download_card import DownloadCard
from ui.widgets.icon_button import IconButton


class DownloadsPage(QWidget):
    """Downloads view showing real-time progress cards and queue management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: Dict[str, DownloadCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title = QLabel("Downloads")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #FFFFFF;")
        title_layout.addWidget(title)

        self.subtitle = QLabel("Manage current downloads and queue")
        self.subtitle.setStyleSheet("font-size: 13px; color: #9A9A9A;")
        title_layout.addWidget(self.subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Batch actions
        self.btn_clear_completed = IconButton("trash.svg", "Clear Completed", icon_size=14)
        self.btn_clear_completed.clicked.connect(main_controller.clear_completed)
        header_layout.addWidget(self.btn_clear_completed)

        layout.addLayout(header_layout)

        # Scrollable container for cards
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 10, 0, 10)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setAlignment(Qt.AlignTop)

        # Empty state placeholder
        self.empty_label = QLabel("No active downloads.\nPaste a media URL on the Home page to start downloading.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 14px; color: #52525B; line-height: 1.5; padding: 60px 0;")
        self.cards_layout.addWidget(self.empty_label)

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

        # Connect controller signals
        main_controller.task_added.connect(self._on_task_added)
        main_controller.task_updated.connect(self._on_task_updated)
        main_controller.task_removed.connect(self._on_task_removed)

    def _on_task_added(self, item: DownloadItem):
        self.empty_label.hide()
        if item.id not in self.cards:
            card = DownloadCard(item, parent=self.cards_container)
            card.pause_requested.connect(main_controller.pause_download)
            card.resume_requested.connect(main_controller.resume_download)
            card.cancel_requested.connect(main_controller.cancel_download)
            card.retry_requested.connect(main_controller.retry_download)
            card.remove_requested.connect(main_controller.remove_task)

            # Insert at top of list
            self.cards_layout.insertWidget(0, card)
            self.cards[item.id] = card
            self._update_header_summary()

    def _on_task_updated(self, item: DownloadItem):
        if item.id in self.cards:
            self.cards[item.id].update_state(item)
            self._update_header_summary()

    def _on_task_removed(self, task_id: str):
        if task_id in self.cards:
            card = self.cards.pop(task_id)
            self.cards_layout.removeWidget(card)
            card.deleteLater()

        if not self.cards:
            self.empty_label.show()
        self._update_header_summary()

    def _update_header_summary(self):
        tasks = main_controller.get_all_tasks()
        downloading = sum(1 for t in tasks if t.status.lower() in ("downloading", "processing", "merging", "converting"))
        queued = sum(1 for t in tasks if t.status.lower() == "queued")

        if not tasks:
            self.subtitle.setText("Manage current downloads and queue")
        else:
            self.subtitle.setText(f"{downloading} active  •  {queued} queued  •  {len(tasks)} total")
