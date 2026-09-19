"""BG REMOVE — AI-powered local background removal.

Usage:
    python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the app package is importable from the project root.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.ui.main_window import MainWindow
    from app.utils.log import setup_logging
    from PySide6.QtWidgets import QApplication

    # Qt finds its own plugin dirs when bundled; this also helps unpacked runs.
    import os

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    setup_logging(app_dir=str(ROOT / "logs"))
    app = QApplication(sys.argv)
    app.setApplicationName("BG Remove")
    app.setOrganizationName("BG Remove")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())