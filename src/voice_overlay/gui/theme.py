from __future__ import annotations

APP_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
}
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QLabel {
    background: transparent;
    color: #cccccc;
}
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px 8px;
    color: #d4d4d4;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #0078d4;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #3c3c3c;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #d4d4d4;
    selection-background-color: #094771;
    selection-color: #ffffff;
    border: 1px solid #3c3c3c;
    outline: none;
}
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 6px 16px;
    color: #d4d4d4;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #383838;
    border-color: #0078d4;
}
QPushButton:pressed {
    background-color: #094771;
}
QPushButton:disabled {
    color: #555555;
    border-color: #2d2d2d;
}
QPushButton#primaryButton {
    background-color: #0078d4;
    border: 1px solid #0078d4;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background-color: #1e8ae6;
}
QPushButton#primaryButton:pressed {
    background-color: #005a9e;
}
QCheckBox {
    spacing: 8px;
    color: #d4d4d4;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    background-color: #2d2d2d;
}
QCheckBox::indicator:hover {
    border-color: #0078d4;
}
QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}
QGroupBox {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
    color: #cccccc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px 8px;
    color: #d4d4d4;
    min-height: 24px;
}
QLineEdit:focus {
    border-color: #0078d4;
}
QPushButton#collapsibleToggle {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 8px 12px;
    color: #cccccc;
    font-weight: 600;
    text-align: left;
}
QPushButton#collapsibleToggle:hover {
    background-color: #2d2d2d;
    border-color: #0078d4;
}
QPushButton#collapsibleToggle:pressed {
    background-color: #094771;
}
"""
