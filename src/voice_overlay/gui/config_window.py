from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from voice_overlay.config import Config
from voice_overlay.gui.settings_widgets import CollapsibleSection, ComputeSelector, HotkeyRecorder

logger = logging.getLogger(__name__)

_VALID_MODELS = frozenset({
    "tiny", "base", "small", "medium", "large-v3", "distil-large-v3",
})
_VALID_LANGUAGES = [
    "en", "de", "fr", "es", "it", "pt", "nl", "ru", "ja", "ko", "zh",
]
_VALID_BLOCK_SIZES = [512, 1024, 2048, 4096]


class ConfigWindow(QMainWindow):
    saved = Signal(dict)

    def __init__(self, config: Config, tray_available: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config
        self._tray_available = tray_available

        self._error_label: QLabel | None = None
        self._minimize_button: QPushButton | None = None
        self._running_label: QLabel | None = None
        self._build_ui()
        self._populate_from_config()

    def _build_ui(self) -> None:
        self.setWindowTitle("VoiceOverlay Configuration")
        self.setFixedSize(540, 580)
        self._center_on_screen()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        main_layout.addWidget(scroll)

        scroll_content = QWidget()
        scroll.setWidget(scroll_content)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)

        scroll_layout.addWidget(self._build_audio_section())
        scroll_layout.addWidget(self._build_transcription_section())
        scroll_layout.addWidget(self._build_hotkey_section())
        scroll_layout.addWidget(self._build_output_section())
        scroll_layout.addWidget(self._build_behavior_section())
        scroll_layout.addWidget(self._build_advanced_section())
        scroll_layout.addStretch()

        main_layout.addWidget(self._build_footer())

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - 540) // 2
            y = (geometry.height() - 580) // 2
            self.move(x, y)

    def _build_audio_section(self) -> QGroupBox:
        group = QGroupBox("Audio")
        layout = QFormLayout(group)

        self._input_device_combo = QComboBox()
        self._input_device_combo.addItem("Auto (system default)", None)

        try:
            from voice_overlay.audio_capture import list_input_devices

            for dev in list_input_devices():
                self._input_device_combo.addItem(dev["name"], dev["index"])
        except Exception:
            logger.debug("Could not enumerate audio devices", exc_info=True)

        layout.addRow("Input Device:", self._input_device_combo)
        return group

    def _build_transcription_section(self) -> QGroupBox:
        group = QGroupBox("Transcription")
        layout = QFormLayout(group)

        row = QHBoxLayout()
        self._model_combo = QComboBox()
        for m in sorted(_VALID_MODELS):
            self._model_combo.addItem(m)
        row.addWidget(self._model_combo)

        self._language_combo = QComboBox()
        for lang in _VALID_LANGUAGES:
            self._language_combo.addItem(lang)
        row.addWidget(self._language_combo)

        layout.addRow("Model / Language:", row)
        return group

    def _build_hotkey_section(self) -> QGroupBox:
        group = QGroupBox("Hotkey")
        layout = QHBoxLayout(group)
        self._hotkey_recorder = HotkeyRecorder()
        layout.addWidget(self._hotkey_recorder)
        return group

    def _build_output_section(self) -> QGroupBox:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 20, 16, 12)
        self._auto_inject_check = QCheckBox("Auto-inject at cursor (off = copy to clipboard)")
        layout.addWidget(self._auto_inject_check, 0, Qt.AlignCenter)
        return group

    def _build_behavior_section(self) -> QGroupBox:
        group = QGroupBox("Behavior")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 20, 16, 12)
        self._launch_at_login_check = QCheckBox("Launch at login")
        layout.addWidget(self._launch_at_login_check, 0, Qt.AlignCenter)
        return group

    def _build_advanced_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Advanced")
        layout = section.content_layout()
        layout.setAlignment(Qt.AlignCenter)

        self._show_on_startup_check = QCheckBox("Show configuration on startup")
        layout.addWidget(self._show_on_startup_check, 0, Qt.AlignCenter)

        self._vad_filter_check = QCheckBox("Voice activity detection filter")
        layout.addWidget(self._vad_filter_check, 0, Qt.AlignCenter)

        compute_row = QHBoxLayout()
        self._compute_selector = ComputeSelector()
        compute_row.addStretch()
        compute_row.addWidget(QLabel("Compute:"))
        compute_row.addWidget(self._compute_selector)
        compute_row.addStretch()
        layout.addLayout(compute_row)

        block_row = QHBoxLayout()
        self._block_size_combo = QComboBox()
        for bs in _VALID_BLOCK_SIZES:
            self._block_size_combo.addItem(str(bs))
        block_row.addStretch()
        block_row.addWidget(QLabel("Audio Block Size:"))
        block_row.addWidget(self._block_size_combo)
        block_row.addStretch()
        layout.addLayout(block_row)

        beta_label = QLabel("Custom word replacements: Beta — coming in a future update")
        beta_label.setStyleSheet("color: #888888; background: transparent; font-style: italic;")
        beta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(beta_label)

        return section

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 0)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ff8a8a; background: transparent;")
        self._error_label.setWordWrap(True)
        footer_layout.addWidget(self._error_label, 1)

        self._running_label = QLabel("")
        self._running_label.setStyleSheet("color: #4ec94e; background: transparent; font-weight: 600;")
        self._running_label.setVisible(False)
        footer_layout.addWidget(self._running_label, 1)

        self._minimize_button = QPushButton("Minimize to Tray" if self._tray_available else "Hide to Background")
        self._minimize_button.clicked.connect(self._on_minimize)
        footer_layout.addWidget(self._minimize_button)

        self._save_button = QPushButton("Save && Start")
        self._save_button.setObjectName("primaryButton")
        self._save_button.clicked.connect(self._on_save)
        footer_layout.addWidget(self._save_button)

        if not self._tray_available:
            quit_btn = QPushButton("Quit")
            quit_btn.clicked.connect(self._on_quit)
            footer_layout.addWidget(quit_btn)

        return footer

    def _populate_from_config(self) -> None:
        input_idx = 0
        for i in range(self._input_device_combo.count()):
            if self._input_device_combo.itemData(i) is None and self._config.input_device is None:
                input_idx = i
                break
            if self._input_device_combo.itemData(i) == self._config.input_device:
                input_idx = i
                break
        self._input_device_combo.setCurrentIndex(input_idx)

        model_idx = self._model_combo.findText(self._config.model)
        if model_idx >= 0:
            self._model_combo.setCurrentIndex(model_idx)

        lang_idx = self._language_combo.findText(self._config.language)
        if lang_idx >= 0:
            self._language_combo.setCurrentIndex(lang_idx)

        self._hotkey_recorder.set_hotkey(
            "+".join(p.capitalize() for p in self._config.hotkey.split("+"))
        )
        self._auto_inject_check.setChecked(self._config.auto_inject)
        self._launch_at_login_check.setChecked(self._config.launch_at_login)
        self._show_on_startup_check.setChecked(self._config.show_config_window)
        self._vad_filter_check.setChecked(self._config.vad_filter)

        self._compute_selector.set_device(self._config.device)
        self._compute_selector.set_compute_type(self._config.compute_type)

        bs_idx = self._block_size_combo.findText(str(self._config.block_size))
        if bs_idx >= 0:
            self._block_size_combo.setCurrentIndex(bs_idx)

    def _on_minimize(self) -> None:
        self.hide()

    def _on_quit(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            self._error_label.setText(error)
            return
        self._error_label.setText("")

        settings = self._gather_settings()
        self.saved.emit(settings)

        if self._tray_available:
            self.hide()
        else:
            self._save_button.setEnabled(False)
            self._save_button.setText("Running...")
            self._running_label.setText("● Engine running in background")
            self._running_label.setVisible(True)
            self.setWindowTitle("VoiceOverlay — Running")

    def _validate(self) -> str | None:
        model = self._model_combo.currentText()
        if model not in _VALID_MODELS:
            return f"Unknown model: {model}"

        block_size = int(self._block_size_combo.currentText())
        if block_size not in _VALID_BLOCK_SIZES:
            return f"Invalid block size: {block_size}"

        hotkey = self._hotkey_recorder.current
        if not hotkey or hotkey == "Invalid combination — try again":
            return "Please set a valid hotkey"

        return None

    def _gather_settings(self) -> dict[str, Any]:
        input_data = self._input_device_combo.currentData()
        return {
            "input_device": input_data,
            "model": self._model_combo.currentText(),
            "language": self._language_combo.currentText(),
            "hotkey": self._hotkey_recorder.current.lower(),
            "auto_inject": self._auto_inject_check.isChecked(),
            "launch_at_login": self._launch_at_login_check.isChecked(),
            "show_config_window": self._show_on_startup_check.isChecked(),
            "vad_filter": self._vad_filter_check.isChecked(),
            "device": self._compute_selector.device(),
            "compute_type": self._compute_selector.compute_type(),
            "block_size": int(self._block_size_combo.currentText()),
            "model_changed": (
                self._model_combo.currentText() != self._config.model
                or self._compute_selector.device() != self._config.device
                or self._compute_selector.compute_type() != self._config.compute_type
            ),
        }

    def closeEvent(self, event) -> None:
        self.hide()
        event.ignore()
