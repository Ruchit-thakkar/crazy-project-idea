"""Main application window container for MediaDrop."""

from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.main_controller import main_controller
from app.extractors.yt_dlp_extractor import detect_platform
from app.utils.config import config_manager
from app.utils.resource_utils import get_asset_path
from ui.dialogs.first_run_dialog import FirstRunDialog
from ui.pages.downloads_page import DownloadsPage
from ui.pages.history_page import HistoryPage
from ui.pages.home_page import HomePage
from ui.pages.settings_page import SettingsPage
from ui.styles.theme import GLOBAL_STYLESHEET
from ui.widgets.sidebar import Sidebar
from ui.widgets.toast import Toast


class MainWindow(QMainWindow):
    """Primary application window with sidebar, page stack, and clipboard monitoring."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaDrop — Universal Media Downloader")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 900)
        self.setAcceptDrops(True)

        # Set App Icon
        icon_path = get_asset_path("icons/logo.svg")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Central Layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar
        self.sidebar = Sidebar(self)
        self.sidebar.page_changed.connect(self._switch_page)
        self.sidebar.new_download_requested.connect(self._on_new_download_clicked)
        main_layout.addWidget(self.sidebar)

        # 2. Content Stack
        self.stack = QStackedWidget(self)

        self.home_page = HomePage(self)
        self.downloads_page = DownloadsPage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)

        self.stack.addWidget(self.home_page)       # Index 0
        self.stack.addWidget(self.downloads_page)  # Index 1
        self.stack.addWidget(self.history_page)    # Index 2
        self.stack.addWidget(self.settings_page)   # Index 3

        main_layout.addWidget(self.stack, stretch=1)

        # 3. Toast Notifications Overlay
        self.toast = Toast(self)

        # Connect inter-page signals
        self.home_page.download_started.connect(self._on_download_started)
        self.history_page.redownload_url.connect(self._on_redownload_url)
        self.settings_page.settings_updated.connect(self.sidebar.update_ffmpeg_status)

        # Controller signals
        main_controller.active_count_changed.connect(self.sidebar.set_download_count)
        main_controller.notification_requested.connect(self._show_notification_toast)

        # Clipboard watcher setup
        self._last_clipboard_text = ""
        self._clipboard = QGuiApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_clipboard_changed)

        # Apply global theme
        self.setStyleSheet(GLOBAL_STYLESHEET)

        # Check first-run onboarding
        QTimer.singleShot(150, self._check_first_run)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        self.sidebar.set_active_page(index)
        if index == 2:
            self.history_page.reload_history()

    def _on_new_download_clicked(self):
        self._switch_page(0)
        self.home_page.focus_url_input()

    def _on_download_started(self, task_id: str):
        # Notify and optionally switch or show toast
        self.toast.show_message(
            "Download queued! View in Downloads",
            action_text="View Queue",
            action_callback=lambda: self._switch_page(1),
            duration_ms=4000,
        )

    def _on_redownload_url(self, url: str):
        self._switch_page(0)
        self.home_page.set_url(url)
        self.home_page.analyze_current_url()

    def _show_notification_toast(self, title: str, message: str):
        self.toast.show_message(
            f"{title}: {message}",
            action_text="View",
            action_callback=lambda: self._switch_page(1),
            duration_ms=5000,
        )

    def _on_clipboard_changed(self):
        if not config_manager.get("clipboard_detection", True):
            return

        text = self._clipboard.text().strip()
        if not text or text == self._last_clipboard_text:
            return

        self._last_clipboard_text = text
        platform = detect_platform(text)

        # Only prompt if it looks like a valid HTTP URL and platform is recognized
        if text.startswith("http://") or text.startswith("https://"):
            if platform in ("YouTube", "Instagram", "TikTok", "Facebook", "X", "Pinterest"):
                self.toast.show_message(
                    f"Media URL detected: {platform} link found",
                    action_text="Analyze",
                    action_callback=lambda: self._analyze_from_clipboard(text),
                    duration_ms=7000,
                )

    def _analyze_from_clipboard(self, url: str):
        self._switch_page(0)
        self.home_page.set_url(url)
        self.home_page.analyze_current_url()

    def _check_first_run(self):
        if not config_manager.get("first_run_completed", False):
            dialog = FirstRunDialog(self)
            dialog.exec()

    # Window-level drag and drop
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        self._switch_page(0)
        self.home_page.dropEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast._position_toast()
