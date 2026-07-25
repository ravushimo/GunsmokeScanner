"""Settings page: OCR languages, window options, keybinds, updates."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.constants import (
    APP_VERSION,
    OCR_LANG_CUSTOM_CHOICES,
    OCR_LANG_EN,
    OCR_LANG_PRESETS,
    THEME,
)
from src.ui.qt_util import call_soon
from src.ui.styles import create_button, section_frame


_KEYBIND_ROWS = (
    ("F4", "Apply layout template for current screen"),
    ("F5", "Stop scan (Gacha / Inventory)"),
    ("F7", "Scan last inventory row (Inventory only)"),
    ("F8", "Scan one selected item (Inventory only)"),
    ("F9", "Start scanning (all modes)"),
    ("F10", "Toggle region overlay on/off"),
)


class SettingsTab(QWidget):
    def __init__(
        self,
        parent,
        *,
        config_manager,
        fonts,
        ocr_processor,
        always_on_top: bool,
        overlay_on: bool,
        on_always_on_top: Callable[[bool], None],
        on_overlay: Callable[[bool], None],
        on_languages_applied: Optional[Callable[[list], None]] = None,
        on_check_updates: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.config_manager = config_manager
        self.fonts = fonts
        self.ocr_processor = ocr_processor
        self._on_always_on_top = on_always_on_top
        self._on_overlay = on_overlay
        self._on_languages_applied = on_languages_applied
        self._on_check_updates = on_check_updates
        self._custom_langs: list[str] = []
        self._preset_btns: dict[str, object] = {}
        self._applying_langs = False

        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("Settings")
        title.setFont(self.fonts.heading)
        title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        root.addWidget(title)

        root.addWidget(self._build_ocr_section())
        root.addWidget(self._build_window_section(always_on_top, overlay_on))
        root.addWidget(self._build_keybinds_section())
        root.addWidget(self._build_updates_section())
        root.addStretch(1)

        self._load_languages_from_config()

    def _section_title(self, parent: QWidget, text: str) -> QLabel:
        lbl = QLabel(text, parent)
        lbl.setFont(self.fonts.subheading)
        lbl.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        return lbl

    def _hint(self, parent: QWidget, text: str) -> QLabel:
        lbl = QLabel(text, parent)
        lbl.setFont(self.fonts.caption)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        return lbl

    def _build_ocr_section(self) -> QWidget:
        frame = section_frame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(8)
        lay.addWidget(self._section_title(frame, "OCR languages"))
        lay.addWidget(
            self._hint(
                frame,
                "English is always on. CN / KR / JP load extra EasyOCR models "
                "(one Asian script at a time works best). Applying may download models.",
            )
        )

        en = QLabel("English (en) - always enabled", frame)
        en.setFont(self.fonts.body)
        en.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        lay.addWidget(en)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for label, code, _name in OCR_LANG_PRESETS:
            btn = create_button(frame, label, None, variant="secondary", font=self.fonts.ui)
            btn.setCheckable(True)
            btn.setProperty("lang_code", code)
            btn.clicked.connect(lambda _=False, c=code: self._on_preset_toggled(c))
            self._preset_btns[code] = btn
            preset_row.addWidget(btn)
        preset_row.addStretch()
        lay.addLayout(preset_row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.custom_combo = QComboBox(frame)
        self.custom_combo.setFont(self.fonts.body)
        for code, name in OCR_LANG_CUSTOM_CHOICES:
            self.custom_combo.addItem(f"{name} ({code})", code)
        custom_row.addWidget(self.custom_combo, 1)
        custom_row.addWidget(
            create_button(
                frame, "Add", self._add_custom_lang, variant="secondary", font=self.fonts.ui
            )
        )
        lay.addLayout(custom_row)

        self.custom_list_lbl = QLabel("", frame)
        self.custom_list_lbl.setFont(self.fonts.caption)
        self.custom_list_lbl.setWordWrap(True)
        self.custom_list_lbl.setStyleSheet(
            f"color: {THEME['text_muted']}; background: transparent;"
        )
        lay.addWidget(self.custom_list_lbl)

        self.active_langs_lbl = QLabel("", frame)
        self.active_langs_lbl.setFont(self.fonts.body)
        self.active_langs_lbl.setStyleSheet(
            f"color: {THEME['text_primary']}; background: transparent;"
        )
        lay.addWidget(self.active_langs_lbl)

        apply_row = QHBoxLayout()
        self.apply_langs_btn = create_button(
            frame,
            "Apply languages",
            self._apply_languages,
            variant="primary",
            font=self.fonts.ui,
        )
        apply_row.addWidget(self.apply_langs_btn)
        apply_row.addWidget(
            create_button(
                frame,
                "Clear extras",
                self._clear_extras,
                variant="ghost",
                font=self.fonts.ui,
            )
        )
        apply_row.addStretch()
        lay.addLayout(apply_row)
        return frame

    def _build_window_section(self, always_on_top: bool, overlay_on: bool) -> QWidget:
        frame = section_frame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(8)
        lay.addWidget(self._section_title(frame, "Window"))

        self.top_check = QCheckBox("Keep app on top", frame)
        self.top_check.setFont(self.fonts.body)
        self.top_check.setChecked(always_on_top)
        self.top_check.toggled.connect(self._on_always_on_top)
        lay.addWidget(self.top_check)

        self.overlay_check = QCheckBox("Show region overlay", frame)
        self.overlay_check.setFont(self.fonts.body)
        self.overlay_check.setChecked(overlay_on)
        self.overlay_check.toggled.connect(self._on_overlay)
        lay.addWidget(self.overlay_check)
        lay.addWidget(self._hint(frame, "Overlay can also be toggled with F10."))
        return frame

    def _build_keybinds_section(self) -> QWidget:
        frame = section_frame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(4)
        lay.addWidget(self._section_title(frame, "Keybinds"))
        for key, desc in _KEYBIND_ROWS:
            row = QHBoxLayout()
            k = QLabel(key, frame)
            k.setFont(self.fonts.mono)
            k.setFixedWidth(36)
            k.setStyleSheet(f"color: {THEME['accent_orange']}; background: transparent;")
            d = QLabel(desc, frame)
            d.setFont(self.fonts.body)
            d.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
            row.addWidget(k)
            row.addWidget(d, 1)
            lay.addLayout(row)
        return frame

    def _build_updates_section(self) -> QWidget:
        frame = section_frame(self)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(8)
        lay.addWidget(self._section_title(frame, "Updates"))

        ver = QLabel(f"Current version: {APP_VERSION}", frame)
        ver.setFont(self.fonts.body)
        ver.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        lay.addWidget(ver)

        self.update_status = QLabel("", frame)
        self.update_status.setFont(self.fonts.caption)
        self.update_status.setWordWrap(True)
        self.update_status.setStyleSheet(
            f"color: {THEME['text_muted']}; background: transparent;"
        )
        lay.addWidget(self.update_status)

        self.check_updates_btn = create_button(
            frame,
            "Check for updates",
            self._check_updates,
            variant="secondary",
            font=self.fonts.ui,
        )
        lay.addWidget(self.check_updates_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def _load_languages_from_config(self) -> None:
        langs = self.config_manager.get_ocr_languages()
        preset_codes = {code for _l, code, _n in OCR_LANG_PRESETS}
        for code, btn in self._preset_btns.items():
            btn.blockSignals(True)
            btn.setChecked(code in langs)
            btn.blockSignals(False)
        self._custom_langs = [
            c for c in langs if c != OCR_LANG_EN and c not in preset_codes
        ]
        self._refresh_lang_labels()

    def _selected_languages(self) -> list[str]:
        langs = [OCR_LANG_EN]
        for code, btn in self._preset_btns.items():
            if btn.isChecked() and code not in langs:
                langs.append(code)
        for code in self._custom_langs:
            if code not in langs:
                langs.append(code)
        return langs

    def _refresh_lang_labels(self) -> None:
        if self._custom_langs:
            self.custom_list_lbl.setText(
                "Custom: " + ", ".join(self._custom_langs) + "  (Clear extras to remove)"
            )
        else:
            self.custom_list_lbl.setText("Custom: none")
        self.active_langs_lbl.setText(
            "Active: " + ", ".join(self._selected_languages())
        )

    def _on_preset_toggled(self, code: str) -> None:
        btn = self._preset_btns.get(code)
        if btn is None:
            return
        # EasyOCR uses one Asian recognition model - keep CN/KR/JP exclusive.
        if btn.isChecked():
            for other, other_btn in self._preset_btns.items():
                if other != code and other_btn.isChecked():
                    other_btn.blockSignals(True)
                    other_btn.setChecked(False)
                    other_btn.blockSignals(False)
        self._refresh_lang_labels()

    def _add_custom_lang(self) -> None:
        code = self.custom_combo.currentData()
        if not code:
            return
        if code in self._custom_langs or code == OCR_LANG_EN:
            return
        if code in self._preset_btns:
            self._preset_btns[code].setChecked(True)
            self._on_preset_toggled(code)
            return
        self._custom_langs.append(code)
        self._refresh_lang_labels()

    def _clear_extras(self) -> None:
        for btn in self._preset_btns.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self._custom_langs.clear()
        self._refresh_lang_labels()

    def _apply_languages(self) -> None:
        if self._applying_langs:
            return
        langs = self._selected_languages()
        asian = [c for _l, c, _n in OCR_LANG_PRESETS if c in langs]
        if len(asian) > 1:
            QMessageBox.warning(
                self,
                "Language conflict",
                "EasyOCR works best with English plus one Asian language "
                "(CN, KR, or JP). Only one will be used effectively.",
            )

        self._applying_langs = True
        self.apply_langs_btn.setEnabled(False)
        self.apply_langs_btn.setText("Loading models...")
        self.update_status.setText("")

        def work():
            err = None
            try:
                self.ocr_processor.set_languages(langs)
                self.config_manager.set_ocr_languages(langs)
            except Exception as e:
                err = str(e)

            def done():
                self._applying_langs = False
                self.apply_langs_btn.setEnabled(True)
                self.apply_langs_btn.setText("Apply languages")
                if err:
                    QMessageBox.critical(
                        self, "OCR languages", f"Failed to load languages:\n{err}"
                    )
                    self._load_languages_from_config()
                    return
                self._refresh_lang_labels()
                if self._on_languages_applied:
                    self._on_languages_applied(langs)
                QMessageBox.information(
                    self,
                    "OCR languages",
                    f"EasyOCR ready with: {', '.join(langs)}",
                )

            call_soon(done)

        threading.Thread(target=work, daemon=True).start()

    def _check_updates(self) -> None:
        if self._on_check_updates is None:
            return
        self.check_updates_btn.setEnabled(False)
        self.update_status.setText("Checking...")
        self._on_check_updates()

    def set_update_status(self, text: str) -> None:
        self.update_status.setText(text)
        self.check_updates_btn.setEnabled(True)

    def sync_overlay_checkbox(self, on: bool) -> None:
        self.overlay_check.blockSignals(True)
        self.overlay_check.setChecked(on)
        self.overlay_check.blockSignals(False)

    def sync_always_on_top_checkbox(self, on: bool) -> None:
        self.top_check.blockSignals(True)
        self.top_check.setChecked(on)
        self.top_check.blockSignals(False)
