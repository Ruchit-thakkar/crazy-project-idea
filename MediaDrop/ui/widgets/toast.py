"""Floating toast notification widget."""

from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from ui.styles.theme import Theme
from ui.widgets.icon_button import IconButton


class Toast(QFrame):
    """Modern floating alert banner for clipboard notifications and status toasts."""

    action_triggered = Signal()
    dismissed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toastFrame")
        self.setStyleSheet(f"""
            #toastFrame {{
                background-color: #18181B;
                border: 1px solid #383838;
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        layout.addWidget(self.icon_label)

        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.message_label, stretch=1)

        self.action_btn = QPushButton("Action")
        self.action_btn.setProperty("role", "primary")
        self.action_btn.setFixedHeight(28)
        self.action_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                font-size: 12px;
                border-radius: 6px;
            }
        """)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.close_btn = IconButton("close.svg", tooltip="Dismiss", icon_size=14)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #27272A;
            }
        """)
        self.close_btn.clicked.connect(self.hide_toast)
        layout.addWidget(self.close_btn)

        self.hide()
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide_toast)

    def show_message(
        self,
        message: str,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        duration_ms: int = 6000,
        is_error: bool = False,
    ) -> None:
        """Show toast message with optional action."""
        self.message_label.setText(message)
        self._action_callback = action_callback

        if action_text and action_callback:
            self.action_btn.setText(action_text)
            self.action_btn.show()
        else:
            self.action_btn.hide()

        if is_error:
            self.setStyleSheet(f"""
                #toastFrame {{
                    background-color: #1C1012;
                    border: 1px solid #7F1D1D;
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #toastFrame {{
                    background-color: #18181B;
                    border: 1px solid #383838;
                    border-radius: 10px;
                }}
            """)

        self.adjustSize()
        self._position_toast()
        self.show()
        self.raise_()

        if duration_ms > 0:
            self.auto_hide_timer.start(duration_ms)

    def _position_toast(self):
        parent = self.parentWidget()
        if parent:
            w = min(max(self.sizeHint().width(), 400), parent.width() - 40)
            h = self.sizeHint().height()
            x = (parent.width() - w) // 2
            y = 20  # 20px from top
            self.setGeometry(x, y, w, h)

    def _on_action_clicked(self):
        if hasattr(self, "_action_callback") and self._action_callback:
            self._action_callback()
        self.action_triggered.emit()
        self.hide_toast()

    def hide_toast(self):
        self.auto_hide_timer.stop()
        self.hide()
        self.dismissed.emit()
