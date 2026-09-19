"""Curated dark theme and comprehensive QSS stylesheet for MediaDrop."""


class Theme:
    # Color Palette
    BG_MAIN = "#0A0A0A"
    BG_CARD = "#141414"
    BG_SURFACE = "#1B1B1B"
    BG_SURFACE_HOVER = "#232323"
    BG_SURFACE_ACTIVE = "#2C2C2C"

    BORDER = "#292929"
    BORDER_LIGHT = "#383838"
    BORDER_ACCENT = "#6366F1"

    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#9A9A9A"
    TEXT_MUTED = "#6B7280"

    ACCENT = "#6366F1"
    ACCENT_HOVER = "#4F46E5"
    ACCENT_ACTIVE = "#4338CA"
    ACCENT_LIGHT = "rgba(99, 102, 241, 0.15)"

    SUCCESS = "#10B981"
    SUCCESS_BG = "rgba(16, 185, 129, 0.12)"
    
    WARNING = "#F59E0B"
    WARNING_BG = "rgba(245, 158, 11, 0.12)"

    DANGER = "#EF4444"
    DANGER_BG = "rgba(239, 68, 68, 0.12)"
    DANGER_HOVER = "#DC2626"


GLOBAL_STYLESHEET = """
/* Base Settings */
* {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    color: #FFFFFF;
    outline: none;
}

QWidget {
    background-color: transparent;
}

QMainWindow, QDialog {
    background-color: #0A0A0A;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0A0A0A;
    width: 6px;
    margin: 0px 0px 0px 0px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #292929;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #4B5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0A0A0A;
    height: 6px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #292929;
    min-width: 24px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #4B5563;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: none;
    width: 0px;
}

/* Tooltips */
QToolTip {
    background-color: #1B1B1B;
    color: #FFFFFF;
    border: 1px solid #292929;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* Text Inputs */
QLineEdit {
    background-color: #141414;
    color: #FFFFFF;
    border: 1px solid #292929;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
    selection-background-color: #6366F1;
    selection-color: #FFFFFF;
}

QLineEdit:focus {
    border: 1px solid #6366F1;
    background-color: #1B1B1B;
}

QLineEdit:disabled {
    background-color: #141414;
    color: #6B7280;
    border-color: #202020;
}

/* Buttons */
QPushButton {
    background-color: #1B1B1B;
    color: #FFFFFF;
    border: 1px solid #292929;
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #262626;
    border-color: #383838;
}

QPushButton:pressed {
    background-color: #1F1F1F;
}

QPushButton:disabled {
    background-color: #141414;
    color: #4B5563;
    border-color: #202020;
}

/* Primary / Accent Button */
QPushButton[role="primary"] {
    background-color: #6366F1;
    border: 1px solid #6366F1;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton[role="primary"]:hover {
    background-color: #4F46E5;
    border-color: #4F46E5;
}

QPushButton[role="primary"]:pressed {
    background-color: #4338CA;
}

QPushButton[role="primary"]:disabled {
    background-color: #312E81;
    color: #818CF8;
    border-color: #312E81;
}

/* Danger Button */
QPushButton[role="danger"] {
    background-color: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #EF4444;
}

QPushButton[role="danger"]:hover {
    background-color: #EF4444;
    color: #FFFFFF;
    border-color: #EF4444;
}

/* Combo Box */
QComboBox {
    background-color: #141414;
    color: #FFFFFF;
    border: 1px solid #292929;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #383838;
}

QComboBox:focus {
    border: 1px solid #6366F1;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left-width: 0px;
}

QComboBox QAbstractItemView {
    background-color: #141414;
    color: #FFFFFF;
    border: 1px solid #292929;
    selection-background-color: #6366F1;
    selection-color: #FFFFFF;
    border-radius: 6px;
    padding: 4px;
}

/* Progress Bar */
QProgressBar {
    background-color: #1B1B1B;
    border: 1px solid #292929;
    border-radius: 5px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #6366F1;
    border-radius: 4px;
}

/* CheckBox */
QCheckBox {
    color: #FFFFFF;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3F3F46;
    background-color: #18181B;
}

QCheckBox::indicator:hover {
    border-color: #6366F1;
    background-color: #202025;
}

QCheckBox::indicator:checked {
    background-color: #6366F1;
    border-color: #6366F1;
    image: url("assets/icons/check.svg");
}

/* Radio Button */
QRadioButton {
    color: #FFFFFF;
    spacing: 8px;
    font-size: 13px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 1.5px solid #52525B;
    background-color: #18181B;
}

QRadioButton::indicator:hover {
    border-color: #6366F1;
}

QRadioButton::indicator:checked {
    border: 5px solid #6366F1;
    background-color: #FFFFFF;
}

/* SpinBox */
QSpinBox {
    background-color: #141414;
    color: #FFFFFF;
    border: 1px solid #292929;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: #6366F1;
    selection-color: #FFFFFF;
}

QSpinBox:focus {
    border: 1px solid #6366F1;
    background-color: #1B1B1B;
}

QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 20px;
    background-color: #1B1B1B;
    border: none;
}

QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 7px;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 7px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #262626;
}

/* Labels */
QLabel {
    color: #FFFFFF;
}

QLabel[role="secondary"] {
    color: #9A9A9A;
}

QLabel[role="muted"] {
    color: #6B7280;
}
"""
