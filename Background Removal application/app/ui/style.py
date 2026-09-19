"""Dark professional theme (QSS)."""
from __future__ import annotations

DARK_PALETTE = {
    "bg0": "#12141a",
    "bg1": "#171a22",
    "bg2": "#1f2330",
    "bg3": "#272c3a",
    "border": "#343a4d",
    "text": "#dfe3ee",
    "muted": "#8b93a7",
    "accent": "#4f7dff",
    "accent2": "#2f9e6e",
    "danger": "#e05c5c",
    "warn": "#e0a54c",
}

_QSS_TEMPLATE = """
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {text};
}}
QMainWindow, QDialog {{
    background-color: {bg0};
}}
QWidget#sidebar, QDockWidget {{
    background-color: {bg1};
}}
QLabel#appTitle {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #ffffff;
    background-color: {bg2};
    padding: 12px 16px;
    border-bottom: 1px solid {border};
}}
QLabel#section {{
    color: {muted};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    margin-top: 10px;
}}
QLabel {{
    background: transparent;
}}
QPushButton {{
    background-color: {bg3};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #303650; border-color: {accent}; }}
QPushButton:pressed {{ background-color: #262b3a; }}
QPushButton:disabled {{ color: {muted}; background-color: {bg2}; }}
QPushButton#primary {{
    background-color: {accent};
    border: none;
    color: white;
    font-size: 14px;
    padding: 12px 18px;
    border-radius: 8px;
}}
QPushButton#primary:hover {{ background-color: #6390ff; }}
QPushButton#danger {{ background-color: #3a1f26; border-color: {danger}; color: #ff9d9d; }}
QPushButton#success {{ background-color: {accent2}; border-color: {accent2}; color: white; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {bg2};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {bg2};
    border: 1px solid {border};
    selection-background-color: {accent};
    outline: none;
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {border};
    background-color: {bg2};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
QProgressBar {{
    background-color: {bg2};
    border: 1px solid {border};
    border-radius: 6px;
    text-align: center;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 5px;
}}
QTabWidget::pane {{ border: 1px solid {border}; }}
QTabBar::tab {{
    background: {bg1};
    padding: 8px 16px;
    border: 1px solid {border};
}}
QTabBar::tab:selected {{ background: {bg3}; }}
"""

QSS = _QSS_TEMPLATE.format(**DARK_PALETTE)