"""MediaDrop — Universal Media Downloader Entry Point."""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app.utils.config import config_manager
from app.utils.logger import setup_logger
from app.utils.resource_utils import get_asset_path
from ui.windows.main_window import MainWindow


def main():
    # Setup logging
    debug_mode = config_manager.get("debug_logging", False)
    logger = setup_logger(debug=debug_mode)
    logger.info("Starting MediaDrop v1.0.0...")

    # Initialize Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("MediaDrop")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MediaDrop")

    # Set default app font
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # Set App Icon
    icon_path = get_asset_path("icons/logo.svg")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Launch Main Window
    window = MainWindow()
    window.show()

    logger.info("MediaDrop initialized and running.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
