"""Gacha Access Records region calibration - PySide6 port."""

from __future__ import annotations

import threading

import pyautogui
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.constants import GACHA_EXTRA_REGIONS, GACHA_ROW_COLUMNS, THEME
from src.core.layouts import layout_from_gacha_config, save_layout
from src.core.scanner import safe_grab
from src.ui.qt_util import call_soon
from src.ui.region_helpers import (
    FIELD_INDEX,
    bind_entry_arrow_nudge,
    distribute_ys_from_first_two,
    fill_field_across_rows,
)
from src.ui.styles import create_button, section_frame

COL_LABELS = {
    "purchase_time": "Purchase Time",
    "purchase_source": "Purchase Source",
    "type": "Type",
    "name": "Name",
}

EXTRA_LABELS = {
    "page_number": "Page Number",
    "btn_prev": "Prev Button (<)",
    "btn_next": "Next Button (>)",
}


def _make_label(text: str, font, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def _add_coord_column(
    parent_row: QHBoxLayout,
    label_text: str,
    field_name: str,
    tab: "GachaSetupTab",
    fill_buttons: dict,
) -> QLineEdit:
    """One aligned column: label+entry on top, Fill others under the entry."""
    col = QVBoxLayout()
    col.setSpacing(4)
    col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    field_row = QHBoxLayout()
    field_row.setSpacing(6)
    field_row.setContentsMargins(0, 0, 0, 0)
    lbl = _make_label(label_text, tab.fonts.ui, THEME["text_muted"])
    lbl.setFixedWidth(52)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    field_row.addWidget(lbl)

    entry = QLineEdit()
    entry.setFixedWidth(90)
    entry.setFont(tab.fonts.mono)
    entry.editingFinished.connect(tab.apply_manual_values)
    bind_entry_arrow_nudge(entry, field_name, tab.nudge_field)
    field_row.addWidget(entry)
    col.addLayout(field_row)

    fill_btn = create_button(
        None,
        "Fill others",
        lambda checked=False, f=field_name: tab.fill_field_others(f),
        variant="ghost",
        font=tab.fonts.caption,
    )
    fill_btn.setFixedSize(90, 28)
    fill_wrap = QHBoxLayout()
    fill_wrap.setContentsMargins(58, 0, 0, 0)
    fill_wrap.addWidget(fill_btn)
    fill_wrap.addStretch(1)
    col.addLayout(fill_wrap)
    fill_buttons[field_name] = fill_btn

    wrap = QWidget()
    wrap.setLayout(col)
    parent_row.addWidget(wrap)
    return entry


class GachaSetupTab(QWidget):
    def __init__(
        self,
        parent,
        config_manager,
        overlay_manager,
        fonts,
        ocr_processor=None,
        on_activate=None,
        on_apply_layout=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.config_manager = config_manager
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.ocr_processor = ocr_processor
        self.on_activate = on_activate
        self.on_apply_layout = on_apply_layout

        self._kind = "row"
        self._row = 0
        self._col = "purchase_time"
        self._extra = "page_number"
        self._lock = "none"

        self.setup_ui()

    def activate(self):
        """Called when this tab becomes active - switch overlay profile."""
        self.overlay_manager.on_update_callback = self.on_overlay_update
        self.overlay_manager.set_profile("gacha")
        self.overlay_manager.set_move_lock(self._lock)
        self._sync_overlay_selection()
        if self.on_activate:
            self.on_activate()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        # 1) Title + instructions
        header = section_frame()
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(5)
        header_lay.addWidget(
            _make_label(
                "Gacha Access Records Regions",
                self.fonts.subheading,
                THEME["text_strong"],
            )
        )
        instructions = _make_label(
            (
                "1. Open Access Records - Show Overlay\n"
                "2. Drag to move - edges/corner to resize\n"
                "3. Arrows in X/Y/W/H fields nudge that value (Shift = 10). "
                "With Overlay on and focus outside fields, arrows move the selection.\n"
                "4. Lock Column/Row - OCR Peek - Save Config"
            ),
            self.fonts.body,
            THEME["text_primary"],
        )
        instructions.setWordWrap(True)
        header_lay.addWidget(instructions)
        outer.addWidget(header)

        # 2) Selection strip
        strip = section_frame()
        strip_lay = QHBoxLayout(strip)
        strip_lay.setContentsMargins(0, 0, 0, 0)
        strip_lay.addStretch(1)

        select_row = QHBoxLayout()
        select_row.setSpacing(24)
        select_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        kind_col = QVBoxLayout()
        kind_col.setSpacing(2)
        kind_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        kind_col.addWidget(_make_label("Target:", self.fonts.subheading, THEME["text_strong"]))
        self.kind_group = QButtonGroup(self)
        for text, value in (("Table Row", "row"), ("Pagination", "extra")):
            btn = QRadioButton(text)
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(value == self._kind)
            btn.toggled.connect(
                lambda checked, v=value: self._on_kind_toggled(v) if checked else None
            )
            self.kind_group.addButton(btn)
            kind_col.addWidget(btn)
        kind_widget = QWidget()
        kind_widget.setLayout(kind_col)
        select_row.addWidget(kind_widget, 0, Qt.AlignmentFlag.AlignTop)

        row_col = QVBoxLayout()
        row_col.setSpacing(2)
        row_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        row_col.addWidget(_make_label("Row:", self.fonts.subheading, THEME["text_strong"]))
        self.row_group = QButtonGroup(self)
        for i in range(6):
            btn = QRadioButton(f"Row {i + 1}")
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(i == self._row)
            btn.toggled.connect(
                lambda checked, v=i: self._on_row_toggled(v) if checked else None
            )
            self.row_group.addButton(btn)
            row_col.addWidget(btn)
        row_widget = QWidget()
        row_widget.setLayout(row_col)
        select_row.addWidget(row_widget, 0, Qt.AlignmentFlag.AlignTop)

        col_col = QVBoxLayout()
        col_col.setSpacing(2)
        col_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        col_col.addWidget(
            _make_label("Column / Control:", self.fonts.subheading, THEME["text_strong"])
        )
        self.col_group = QButtonGroup(self)
        self.col_buttons = {}
        for key in GACHA_ROW_COLUMNS:
            btn = QRadioButton(COL_LABELS[key])
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(key == self._col)
            btn.toggled.connect(
                lambda checked, v=key: self._on_col_toggled(v) if checked else None
            )
            self.col_group.addButton(btn)
            col_col.addWidget(btn)
            self.col_buttons[key] = btn

        self.extra_group = QButtonGroup(self)
        self.extra_buttons = {}
        for key in GACHA_EXTRA_REGIONS:
            btn = QRadioButton(EXTRA_LABELS[key])
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(key == self._extra)
            btn.toggled.connect(
                lambda checked, v=key: self._on_extra_toggled(v) if checked else None
            )
            self.extra_group.addButton(btn)
            col_col.addWidget(btn)
            btn.setVisible(False)
            self.extra_buttons[key] = btn
        col_widget = QWidget()
        col_widget.setLayout(col_col)
        select_row.addWidget(col_widget, 0, Qt.AlignmentFlag.AlignTop)

        lock_col = QVBoxLayout()
        lock_col.setSpacing(2)
        lock_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        lock_col.addWidget(
            _make_label("Move Lock:", self.fonts.subheading, THEME["text_strong"])
        )
        self.lock_group = QButtonGroup(self)
        for text, value in (
            ("Off", "none"),
            ("Whole Column", "column"),
            ("Whole Row", "row"),
        ):
            btn = QRadioButton(text)
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(value == self._lock)
            btn.toggled.connect(
                lambda checked, v=value: self._on_lock_toggled(v) if checked else None
            )
            self.lock_group.addButton(btn)
            lock_col.addWidget(btn)
        lock_widget = QWidget()
        lock_widget.setLayout(lock_col)
        select_row.addWidget(lock_widget, 0, Qt.AlignmentFlag.AlignTop)

        strip_lay.addLayout(select_row)
        strip_lay.addStretch(1)
        outer.addWidget(strip)

        # 3) Editor section
        editor = section_frame()
        editor_lay = QVBoxLayout(editor)
        editor_lay.setContentsMargins(0, 0, 0, 0)
        editor_lay.setSpacing(6)

        title_lbl = _make_label("Current region", self.fonts.subheading, THEME["text_strong"])
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_lay.addWidget(title_lbl)

        coords_row = QHBoxLayout()
        coords_row.addStretch(1)
        coords_inner = QHBoxLayout()
        coords_inner.setSpacing(12)
        self.region_entries = {}
        self.fill_buttons = {}
        for label_text, field_name in (
            ("X:", "x"),
            ("Y:", "y"),
            ("Width:", "w"),
            ("Height:", "h"),
        ):
            self.region_entries[field_name] = _add_coord_column(
                coords_inner, label_text, field_name, self, self.fill_buttons
            )
        coords_row.addLayout(coords_inner)
        coords_row.addStretch(1)
        editor_lay.addLayout(coords_row)

        self.peek_label = QLabel("OCR Peek: -")
        self.peek_label.setFont(self.fonts.mono)
        self.peek_label.setWordWrap(True)
        self.peek_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.peek_label.setMaximumHeight(64)
        self.peek_label.setStyleSheet(
            f"color: {THEME['text_primary']}; background: transparent;"
            f" border: 1px solid {THEME['border']}; border-radius: 4px; padding: 4px 8px;"
        )
        editor_lay.addWidget(self.peek_label)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(
            create_button(
                None,
                "Apply Changes",
                self.apply_manual_values,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        self.distribute_btn = create_button(
            None,
            "Distribute Y from Row 1-2",
            self.distribute_y,
            variant="featured",
            font=self.fonts.ui,
        )
        action_row.addWidget(self.distribute_btn)
        action_row.addWidget(
            create_button(
                None,
                "OCR Peek",
                self.ocr_peek,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        action_row.addStretch(1)
        editor_lay.addLayout(action_row)
        editor_lay.addStretch(1)

        outer.addWidget(editor, stretch=1)

        # 4) Bottom action row
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(
            create_button(
                None,
                "Save Config",
                self.save_config,
                variant="primary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Save as layout template",
                self.save_layout_template,
                variant="featured",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Apply layout (F4)",
                self.apply_layout_f4,
                variant="ghost",
                font=self.fonts.ui,
            )
        )
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        self._sync_kind_widgets()
        self.update_region_info()

    def _on_kind_toggled(self, value: str):
        self._kind = value
        self.on_selection_change()

    def _on_row_toggled(self, value: int):
        self._row = value
        self.on_selection_change()

    def _on_col_toggled(self, value: str):
        self._col = value
        self.on_selection_change()

    def _on_extra_toggled(self, value: str):
        self._extra = value
        self.on_selection_change()

    def _on_lock_toggled(self, value: str):
        self._lock = value
        self.on_lock_change()

    def on_lock_change(self):
        self.overlay_manager.set_move_lock(self._lock)

    def _sync_kind_widgets(self):
        is_row = self._kind == "row"
        for btn in self.col_buttons.values():
            btn.setVisible(is_row)
        for btn in self.extra_buttons.values():
            btn.setVisible(not is_row)

        for btn in self.fill_buttons.values():
            btn.setEnabled(is_row)
        if hasattr(self, "distribute_btn"):
            self.distribute_btn.setEnabled(is_row)

    def _current_target(self):
        if self._kind == "extra":
            return None, self._extra
        return self._row, self._col

    def _sync_overlay_selection(self):
        row_idx, col = self._current_target()
        self.overlay_manager.set_selected(row_idx, col)

    def _refresh_overlays(self):
        if self.overlay_manager.active:
            self.overlay_manager.sync_geometries()

    def on_selection_change(self):
        self._sync_kind_widgets()
        self.update_region_info()
        self._sync_overlay_selection()

    def _set_checked_silent(self, btn):
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)

    def on_overlay_update(self, row_idx, col_name, select=False):
        if select:
            if row_idx is None:
                self._kind = "extra"
                self._extra = col_name
                self._set_checked_silent(self.extra_buttons[col_name])
            else:
                self._kind = "row"
                self._row = row_idx
                self._col = col_name
                self._set_checked_silent(self.row_group.buttons()[row_idx])
                self._set_checked_silent(self.col_buttons[col_name])
            self._sync_kind_widgets()

        current_row, current_col = self._current_target()
        if current_row == row_idx and current_col == col_name:
            self.update_region_info()

    def get_current_bbox(self):
        gacha = self.config_manager.get_gacha()
        row_idx, col = self._current_target()
        if row_idx is None:
            return gacha[col]
        return gacha["rows"][row_idx][col]

    def set_current_bbox(self, bbox):
        gacha = self.config_manager.get_gacha()
        row_idx, col = self._current_target()
        if row_idx is None:
            gacha[col] = bbox
        else:
            gacha["rows"][row_idx][col] = bbox
        self.update_region_info()

    def update_region_info(self):
        bbox = self.get_current_bbox()
        for idx, key in enumerate(("x", "y", "w", "h")):
            self.region_entries[key].setText(str(bbox[idx]))

    def apply_manual_values(self):
        try:
            x = int(self.region_entries["x"].text())
            y = int(self.region_entries["y"].text())
            w = int(self.region_entries["w"].text())
            h = int(self.region_entries["h"].text())
            self.set_current_bbox([x, y, w, h])
            self._refresh_overlays()
        except ValueError:
            pass

    def nudge_field(self, field: str, delta: int):
        """Adjust one bbox field from arrow keys while an entry is focused."""
        self._sync_overlay_selection()
        if field in ("x", "y") and self.overlay_manager.active:
            dx = delta if field == "x" else 0
            dy = delta if field == "y" else 0
            if self.overlay_manager.nudge_selected(dx, dy):
                self.update_region_info()
                return

        try:
            value = int(self.region_entries[field].text())
        except ValueError:
            value = int(self.get_current_bbox()[FIELD_INDEX[field]])
        new_val = value + delta
        if field == "w":
            new_val = max(16, new_val)
        elif field == "h":
            new_val = max(12, new_val)
        bbox = list(self.get_current_bbox())
        bbox[FIELD_INDEX[field]] = new_val
        self.set_current_bbox(bbox)
        self._refresh_overlays()

    def fill_field_others(self, field: str):
        if self._kind != "row":
            return
        try:
            value = int(self.region_entries[field].text())
        except ValueError:
            return
        self.apply_manual_values()
        col = self._col
        rows = self.config_manager.get_gacha().get("rows", [])
        fill_field_across_rows(rows, col, field, value)
        self.update_region_info()
        self._refresh_overlays()

    def distribute_y(self):
        if self._kind != "row":
            return
        self.apply_manual_values()
        col = self._col
        rows = self.config_manager.get_gacha().get("rows", [])
        gap = distribute_ys_from_first_two(rows, col, sync_all_columns=False)
        if gap is None:
            QMessageBox.warning(
                self,
                "Distribute Y",
                "Align Row 1 and Row 2 first (different Y values required).",
            )
            return
        self.update_region_info()
        self._refresh_overlays()

    def ocr_peek(self):
        if self.ocr_processor is None:
            QMessageBox.warning(self, "OCR Peek", "OCR is not available.")
            return
        self.apply_manual_values()
        self.peek_label.setText("OCR Peek: reading...")
        was_active = self.overlay_manager.active
        if was_active:
            self.overlay_manager.hide()

        gacha_cfg = dict(self.config_manager.config)
        gacha_cfg["preprocessing"] = self.config_manager.get_gacha().get(
            "preprocessing", gacha_cfg.get("preprocessing")
        )

        def worker():
            try:
                img = safe_grab(self.get_current_bbox())
                text = self.ocr_processor.extract_text(img, config=gacha_cfg)
                display = text if text else "(empty)"
            except Exception as e:
                display = f"Error: {e}"
            call_soon(lambda: self._on_peek_done(display, was_active))

        threading.Thread(target=worker, daemon=True).start()

    def _on_peek_done(self, text: str, restore_overlays: bool):
        self.peek_label.setText(f"OCR Peek: {text}")
        if restore_overlays:
            self.overlay_manager.show()
            self._sync_overlay_selection()

    def save_config(self):
        self.overlay_manager.hide()
        if self.config_manager.save_config():
            QMessageBox.information(self, "Success", "Gacha configuration saved!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save configuration")

    def save_layout_template(self):
        """Export current gacha regions as a bundled layout for this screen size."""
        width, height = pyautogui.size()
        layout = layout_from_gacha_config(
            self.config_manager.get_gacha(), width, height
        )
        try:
            path = save_layout(layout)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not write layout:\n{e}")
            return
        QMessageBox.information(
            self,
            "Layout saved",
            f"Saved gacha template for {width}x{height}:\n{path}",
        )

    def apply_layout_f4(self):
        if self.on_apply_layout:
            self.on_apply_layout()
        else:
            QMessageBox.warning(
                self, "Layout", "Apply layout is not wired in this build."
            )
