from __future__ import annotations

import logging
from typing import ClassVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_MODIFIER_KEYS = frozenset({
    "ctrl", "shift", "alt", "meta", "super",
    "control", "shift_l", "shift_r", "ctrl_l", "ctrl_r",
    "alt_l", "alt_r", "meta_l", "meta_r", "super_l", "super_r",
})


def _is_valid_key_combo(keys: list[str]) -> bool:
    keys_lower = [k.lower() for k in keys]
    non_modifiers = [k for k in keys_lower if k not in _MODIFIER_KEYS]
    if not non_modifiers:
        return False
    return True


def _normalize_combo(keys: list[str]) -> str:
    parts = []
    seen = set()
    for k in keys:
        lower = k.lower().replace("control", "ctrl").replace("super", "meta")
        if lower not in seen:
            seen.add(lower)
            parts.append(lower.capitalize())
    return "+".join(parts)


class HotkeyRecorder(QWidget):
    hotkey_changed = Signal(str)

    def __init__(self, initial: str = "Ctrl+Shift+Space", parent: QWidget | None = None):
        super().__init__(parent)
        self._current = initial
        self._listening = False
        self._pressed: list[str] = []
        self._recorded: list[str] = []

        self._build_ui()
        self._update_display()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Hotkey")
        self._label.setStyleSheet("background: transparent;")
        layout.addWidget(self._label)

        self._display = QLabel()
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px 12px;
                color: #d4d4d4;
            }
            QLabel:hover {
                border-color: #0078d4;
            }
        """)
        self._display.setCursor(Qt.PointingHandCursor)
        self._display.mousePressEvent = self._on_click
        layout.addWidget(self._display)
        self._update_display()

    def _on_click(self, event) -> None:
        self.start_listening()

    def start_listening(self) -> None:
        self._listening = True
        self._pressed.clear()
        self._recorded.clear()
        self._show_listening_style()
        self.setFocus()
        self.grabKeyboard()

    def _show_listening_style(self) -> None:
        self._display.setText("Press key combination...")
        self._display.setStyleSheet("""
            QLabel {
                background-color: #094771;
                border: 2px solid #0078d4;
                border-radius: 4px;
                padding: 8px 12px;
                color: #ffffff;
            }
        """)

    def _show_error_style(self) -> None:
        self._display.setText("Invalid combination — try again")
        self._display.setStyleSheet("""
            QLabel {
                background-color: #5a1d1d;
                border: 1px solid #c73e3e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #ff8a8a;
            }
        """)

    def keyPressEvent(self, event) -> None:
        if not self._listening:
            super().keyPressEvent(event)
            return

        if event.isAutoRepeat():
            return

        key = event.key()

        if key == Qt.Key_Escape:
            self._cancel_listening()
            return

        modifier_map = {
            Qt.Key_Control: "Ctrl",
            Qt.Key_Shift: "Shift",
            Qt.Key_Alt: "Alt",
            Qt.Key_Meta: "Meta",
        }
        mod = modifier_map.get(key)
        if mod:
            if mod not in self._pressed:
                self._pressed.append(mod)
                if mod not in self._recorded:
                    self._recorded.append(mod)
                self._update_pressed_display()
            return

        from PySide6.QtGui import QKeySequence
        key_name = QKeySequence(key).toString(QKeySequence.PortableText)
        if not key_name:
            return

        if key_name not in self._pressed:
            self._pressed.append(key_name)
            if key_name not in self._recorded:
                self._recorded.append(key_name)
            self._update_pressed_display()

    def keyReleaseEvent(self, event) -> None:
        if not self._listening:
            return

        if event.isAutoRepeat():
            return

        key = event.key()

        if key == Qt.Key_Escape:
            return

        modifier_map = {
            Qt.Key_Control: "Ctrl",
            Qt.Key_Shift: "Shift",
            Qt.Key_Alt: "Alt",
            Qt.Key_Meta: "Meta",
        }
        released = modifier_map.get(key)
        if released:
            if released in self._pressed:
                self._pressed.remove(released)
        else:
            from PySide6.QtGui import QKeySequence
            key_name = QKeySequence(key).toString(QKeySequence.PortableText)
            if key_name and key_name in self._pressed:
                self._pressed.remove(key_name)

        if not self._pressed:
            if any(k.lower() not in _MODIFIER_KEYS for k in self._recorded):
                self._finish_listening()
            else:
                self._show_listening_style()
                self._pressed.clear()
                self._recorded.clear()
        else:
            self._update_pressed_display()

    def _update_pressed_display(self) -> None:
        self._display.setText("+".join(self._pressed))

    def _cancel_listening(self) -> None:
        self._listening = False
        self.releaseKeyboard()
        self._update_display()

    def _finish_listening(self) -> None:
        self._listening = False
        self.releaseKeyboard()

        combo = _normalize_combo(self._recorded)
        if not _is_valid_key_combo(self._recorded):
            self._show_error_style()
            return

        self._current = combo
        self._update_display()
        self.hotkey_changed.emit(self._current)

    def _update_display(self) -> None:
        hint = QKeySequence(self._current)
        self._display.setText(hint.toString(QKeySequence.PortableText))
        self._display.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px 12px;
                color: #d4d4d4;
            }
            QLabel:hover {
                border-color: #0078d4;
            }
        """)

    @property
    def current(self) -> str:
        return self._current

    def set_hotkey(self, value: str) -> None:
        self._current = value
        self._update_display()


class ComputeSelector(QWidget):
    compute_changed = Signal(str, str)

    DEVICE_OPTIONS: ClassVar[list[str]] = ["Auto", "CPU", "GPU"]
    COMPUTE_MAP: ClassVar[dict[str, list[str]]] = {
        "CPU": ["int8", "float32"],
        "GPU": ["float16", "bfloat16", "int8_float16", "int8_bfloat16"],
        "Auto": ["int8", "float32", "float16", "bfloat16", "int8_float16", "int8_bfloat16"],
    }

    def __init__(self, device: str = "cpu", compute_type: str = "int8", parent: QWidget | None = None):
        super().__init__(parent)
        self._device = device
        self._compute_type = compute_type
        self._build_ui()

    def _build_ui(self) -> None:
        try:
            from PySide6.QtWidgets import QComboBox, QFormLayout
        except ImportError:
            return

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._device_combo = QComboBox()
        self._device_combo.addItems(self.DEVICE_OPTIONS)
        layout.addRow("Device:", self._device_combo)
        self._device_combo.currentTextChanged.connect(self._on_device_changed)

        self._compute_combo = QComboBox()
        layout.addRow("Compute Type:", self._compute_combo)

        dev_label = self._device.capitalize() if self._device != "cuda" else "GPU"
        if dev_label not in self.DEVICE_OPTIONS:
            dev_label = "Auto"
        self._device_combo.setCurrentText(dev_label)
        self._on_device_changed(dev_label)
        self._set_compute_value(self._compute_type)

    def _on_device_changed(self, device_label: str) -> None:
        self._compute_combo.clear()
        options = self.COMPUTE_MAP.get(device_label, self.COMPUTE_MAP["Auto"])
        self._compute_combo.addItems(options)

    def _set_compute_value(self, compute_type: str) -> None:
        idx = self._compute_combo.findText(compute_type)
        if idx >= 0:
            self._compute_combo.setCurrentIndex(idx)

    def device(self) -> str:
        label = self._device_combo.currentText()
        return {"Auto": "auto", "CPU": "cpu", "GPU": "cuda"}.get(label, "auto")

    def compute_type(self) -> str:
        return self._compute_combo.currentText()

    def set_device(self, device: str) -> None:
        label = {"auto": "Auto", "cpu": "CPU", "cuda": "GPU"}.get(device, "Auto")
        self._device_combo.setCurrentText(label)

    def set_compute_type(self, compute_type: str) -> None:
        self._set_compute_value(compute_type)


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QPushButton(f"  ▶  {title}")
        self._toggle_btn.setObjectName("collapsibleToggle")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content.setVisible(False)
        layout.addWidget(self._content)

    def content_layout(self) -> QVBoxLayout:
        if not self._content.layout():
            self._content.setLayout(QVBoxLayout())
        layout: QVBoxLayout = self._content.layout()
        return layout

    def set_expanded(self, expanded: bool) -> None:
        if expanded != self._expanded:
            self._toggle()

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle_btn.setText(f"  {'▼' if self._expanded else '▶'}  {self._title}")
