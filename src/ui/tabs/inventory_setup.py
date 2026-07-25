"""Growth Data region calibration (Inventory mode) - PySide6 port."""

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

from src.constants import INVENTORY_GROWTH_REGIONS, THEME
from src.core.growth_scanner import GrowthScanner, has_orange_lock
from src.core.layouts import layout_from_inventory_growth, save_layout
from src.core.scanner import safe_grab
from src.ui.qt_util import call_soon
from src.ui.region_helpers import bind_entry_arrow_nudge
from src.ui.styles import create_button, section_frame

REGION_LABELS = {
    "grid": "Item Grid",
    "type": "Type line",
    "perks": "Perks block",
    "lock_btn": "Detail lock button",
    "own_count": "Own count",
}


def _make_label(text: str, font, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def _add_coord_field(
    row: QHBoxLayout,
    label_text: str,
    field_name: str,
    tab: "InventorySetupTab",
    entries: dict[str, QLineEdit],
) -> QLineEdit:
    lbl = _make_label(label_text, tab.fonts.ui, THEME["text_muted"])
    lbl.setFixedWidth(60)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lbl)

    entry = QLineEdit()
    entry.setFixedWidth(90)
    entry.setFont(tab.fonts.mono)
    bind_entry_arrow_nudge(entry, field_name, tab.nudge_field)
    row.addWidget(entry)
    entries[field_name] = entry
    return entry


class InventorySetupTab(QWidget):
    def __init__(
        self,
        parent,
        config_manager,
        overlay_manager,
        fonts,
        ocr_processor=None,
        on_apply_layout=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.config_manager = config_manager
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.ocr_processor = ocr_processor
        self.on_apply_layout = on_apply_layout

        self._region_values = list(INVENTORY_GROWTH_REGIONS)
        self._region = self._region_values[0]

        self.setup_ui()

    def activate(self):
        """Called when this tab becomes active - switch overlay profile."""
        self.overlay_manager.on_update_callback = self.on_overlay_update
        self.overlay_manager.set_profile("inventory")
        self.overlay_manager.set_move_lock("none")
        self._sync_overlay_selection()
        self.update_region_info()

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
                "Growth Data Regions (3440x1440)",
                self.fonts.subheading,
                THEME["text_strong"],
            )
        )
        instructions = _make_label(
            (
                "1. Open Growth Data - Storeroom - Show Overlay\n"
                "2. Drag Grid / Type / Perks / Lock / Own regions\n"
                "   Identity (name/icon) is not stored - only type + perks.\n"
                "3. Set cell lock inset (orange padlock on tile, left side)\n"
                "4. OCR Peek / Lock Peek - Save Config - F4 apply template"
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

        region_col = QVBoxLayout()
        region_col.setSpacing(2)
        region_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        region_col.addWidget(_make_label("Region:", self.fonts.subheading, THEME["text_strong"]))
        self.region_group = QButtonGroup(self)
        self.region_buttons = {}
        for idx, key in enumerate(self._region_values):
            btn = QRadioButton(REGION_LABELS[key])
            btn.setFont(self.fonts.body)
            btn.setStyleSheet(f"color: {THEME['text_primary']};")
            btn.setChecked(key == self._region)
            self.region_group.addButton(btn, idx)
            region_col.addWidget(btn)
            self.region_buttons[key] = btn
        self.region_group.idClicked.connect(self._on_region_clicked)
        region_widget = QWidget()
        region_widget.setLayout(region_col)
        strip_lay.addWidget(region_widget, 0, Qt.AlignmentFlag.AlignTop)
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
        coords_inner.setSpacing(8)
        self.entries = {}
        for label_text, field_name in (
            ("X:", "x"),
            ("Y:", "y"),
            ("Width:", "w"),
            ("Height:", "h"),
        ):
            _add_coord_field(coords_inner, label_text, field_name, self, self.entries)
        coords_row.addLayout(coords_inner)
        coords_row.addStretch(1)
        editor_lay.addLayout(coords_row)

        inset_title = _make_label(
            "Cell lock inset (relative px inside each tile)",
            self.fonts.caption,
            THEME["text_muted"],
        )
        inset_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor_lay.addWidget(inset_title)

        inset_row = QHBoxLayout()
        inset_row.addStretch(1)
        inset_inner = QHBoxLayout()
        inset_inner.setSpacing(8)
        self.inset_entries = {}
        for label_text, field_name in (
            ("X:", "x"),
            ("Y:", "y"),
            ("Width:", "w"),
            ("Height:", "h"),
        ):
            lbl = _make_label(label_text, self.fonts.ui, THEME["text_muted"])
            lbl.setFixedWidth(60)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            inset_inner.addWidget(lbl)

            entry = QLineEdit()
            entry.setFixedWidth(90)
            entry.setFont(self.fonts.mono)
            inset_inner.addWidget(entry)
            self.inset_entries[field_name] = entry
        inset_row.addLayout(inset_inner)
        inset_row.addStretch(1)
        editor_lay.addLayout(inset_row)

        self.peek_label = QLabel("Peek: -")
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
                self.apply_coords,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        action_row.addWidget(
            create_button(
                None,
                "Lock Peek",
                self.lock_peek,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
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

        self.update_region_info()

    def apply_layout_f4(self):
        if self.on_apply_layout:
            self.on_apply_layout()
        else:
            QMessageBox.warning(
                self, "Layout", "Apply layout is not wired in this build."
            )

    def _growth(self) -> dict:
        return self.config_manager.get_inventory_growth()

    def _get_region(self) -> str:
        return self._region

    def _set_region(self, value: str, *, silent: bool = False):
        self._region = value
        btn = self.region_buttons.get(value)
        if btn is not None:
            if silent:
                btn.blockSignals(True)
                btn.setChecked(True)
                btn.blockSignals(False)
            else:
                btn.setChecked(True)

    def _on_region_clicked(self, idx: int):
        self._region = self._region_values[idx]
        self.on_selection_change()

    def on_selection_change(self):
        self.update_region_info()
        self._sync_overlay_selection()

    def _sync_overlay_selection(self):
        self.overlay_manager.set_selected(None, self._get_region())

    def on_overlay_update(self, row_idx, col_name, select=False):
        if select and col_name in INVENTORY_GROWTH_REGIONS:
            self._set_region(col_name, silent=True)
        self.update_region_info()

    def update_region_info(self):
        g = self._growth()
        key = self._get_region()
        bbox = g.get(key) or [0, 0, 0, 0]
        for field, val in zip(("x", "y", "w", "h"), bbox):
            self.entries[field].setText(str(int(val)))
        inset = g.get("cell_lock_inset") or [10, 48, 40, 40]
        for field, val in zip(("x", "y", "w", "h"), inset):
            self.inset_entries[field].setText(str(int(val)))

    def nudge_field(self, field: str, delta: int):
        e = self.entries.get(field)
        if not e:
            return
        try:
            val = int(e.text().strip())
        except ValueError:
            val = 0
        e.setText(str(val + delta))
        self.apply_coords()

    def apply_coords(self):
        g = self._growth()
        key = self._get_region()
        try:
            bbox = [int(self.entries[f].text()) for f in ("x", "y", "w", "h")]
            inset = [int(self.inset_entries[f].text()) for f in ("x", "y", "w", "h")]
        except ValueError:
            QMessageBox.critical(self, "Invalid", "Coordinates must be integers.")
            return
        g[key] = bbox
        g["cell_lock_inset"] = inset
        self.config_manager.save_config()
        if self.overlay_manager.active:
            self.overlay_manager.sync_geometries()
        self._log(f"Updated {key} = {bbox}; cell_lock_inset = {inset}")

    def save_config(self):
        self.apply_coords()
        QMessageBox.information(self, "Saved", "Inventory Growth config saved.")

    def save_layout_template(self):
        self.apply_coords()
        w, h = pyautogui.size()
        layout = layout_from_inventory_growth(self._growth(), w, h)
        path = save_layout(layout)
        QMessageBox.information(self, "Layout saved", f"Wrote {path}")

    def _log(self, text: str):
        self.peek_label.setText(text)

    def ocr_peek(self):
        if not self.ocr_processor:
            return

        def _run():
            key = self._get_region()
            g = self._growth()
            bbox = g.get(key)
            img = safe_grab(bbox) if bbox else None
            text = (
                self.ocr_processor.extract_text(img, config=self.config_manager.config)
                if img is not None
                else "(no image)"
            )
            if key in ("type", "perks"):
                from src.core.growth_names import parse_perks_from_text, parse_type_line

                if key == "type":
                    parsed = parse_type_line(text)
                    msg = f"OCR [type]:\n{text}\n\nparsed: {parsed!r}"
                else:
                    perks = parse_perks_from_text(text)
                    lines = [
                        f"  {p.get('name')} Lv.{p.get('level')}" for p in perks
                    ]
                    msg = f"OCR [perks]:\n{text}\n\nparsed ({len(perks)}):\n" + (
                        "\n".join(lines) if lines else "  (none)"
                    )
                call_soon(lambda: self._log(msg))
                return
            call_soon(lambda: self._log(f"OCR [{key}]:\n{text}"))

        threading.Thread(target=_run, daemon=True).start()

    def lock_peek(self):
        def _run():
            scanner = GrowthScanner(self.config_manager, self.ocr_processor)
            detail = scanner.is_detail_locked()
            # Sample R1C1 grid lock
            grid_locked = scanner.is_cell_locked(0, 0)
            g = self._growth()
            img = safe_grab(g.get("lock_btn"))
            px = has_orange_lock(img)
            msg = (
                f"Detail lock_btn orange={detail} (sample={px})\n"
                f"Grid R1C1 lock badge={grid_locked}\n"
                f"Select an unlocked vs locked core and re-check."
            )
            call_soon(lambda: self._log(msg))

        threading.Thread(target=_run, daemon=True).start()
