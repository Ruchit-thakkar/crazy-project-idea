"""User-friendly error dialog with technical details drawer."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.utils.resource_utils import get_asset_path
from ui.widgets.icon_button import IconButton


class ErrorDialog(QDialog):
    """Modern modal dialog displaying friendly error explanations and technical details."""

    def __init__(self, title: str, friendly_msg: str, technical_details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MediaDrop — Notice")
        self.setFixedWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #121214;
                border: 1px solid #27272A;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with Alert Icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        alert_path = get_asset_path("icons/alert.svg")
        if alert_path.exists():
            from PySide6.QtGui import QIcon
            icon_lbl.setPixmap(QIcon(str(alert_path)).pixmap(32, 32))
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 700; color: #FFFFFF;")
        header_layout.addWidget(title_lbl, stretch=1)
        layout.addLayout(header_layout)

        # Friendly explanation
        msg_lbl = QLabel(friendly_msg)
        msg_lbl.setStyleSheet("font-size: 13px; color: #D4D4D8; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        # Details toggle button
        self.btn_toggle_details = QPushButton("View Details ▼")
        self.btn_toggle_details.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_details.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #818CF8;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover {
                color: #A5B4FC;
            }
        """)
        self.btn_toggle_details.clicked.connect(self._toggle_details)
        layout.addWidget(self.btn_toggle_details)

        # Technical details text area
        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)
        self.details_box.setPlainText(technical_details)
        self.details_box.setFixedHeight(120)
        self.details_box.setStyleSheet("""
            QTextEdit {
                background-color: #0A0A0C;
                color: #A1A1AA;
                border: 1px solid #202023;
                border-radius: 6px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        self.details_box.hide()
        layout.addWidget(self.details_box)

        # Action bar
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_copy = IconButton("copy.svg", "Copy Log", tooltip="Copy details to clipboard", icon_size=14)
        self.btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(technical_details))
        actions_layout.addWidget(self.btn_copy)
        actions_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setProperty("role", "primary")
        self.btn_close.setFixedHeight(34)
        self.btn_close.setFixedWidth(90)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #27272A;
                color: #FFFFFF;
                border: 1px solid #3F3F46;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3F3F46;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        actions_layout.addWidget(self.btn_close)
        layout.addLayout(actions_layout)

    def _toggle_details(self):
        if self.details_box.isVisible():
            self.details_box.hide()
            self.btn_toggle_details.setText("View Details ▼")
        else:
            self.details_box.show()
            self.btn_toggle_details.setText("Hide Details ▲")
        self.adjustSize()
