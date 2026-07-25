"""Growth Data capture controls (Inventory mode) - PySide6 port."""

from __future__ import annotations

import re
import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.constants import CLASS_COLORS, THEME, class_color
from src.core.growth_scanner import GrowthScanner
from src.data.inventory_db import InventoryDB
from src.ui.qt_util import call_soon
from src.ui.styles import (
    configure_stretch_table,
    create_button,
    section_frame,
    stat_strip,
    toolbar_frame,
)

_LOG_TYPE_RE = re.compile(
    r"\[(" + "|".join(re.escape(t) for t in CLASS_COLORS) + r")\]"
)

_COLUMNS = (
    ("Type", 100, Qt.AlignmentFlag.AlignCenter),
    ("Perks", 420, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Qty", 50, Qt.AlignmentFlag.AlignCenter),
)

class InventoryCaptureTab(QWidget):
    def __init__(
        self,
        parent,
        config_manager,
        ocr_processor,
        overlay_manager,
        fonts,
        db: InventoryDB = None,
        on_inventory_refresh=None,
        on_overlay_off=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.db = db or InventoryDB()
        self.on_inventory_refresh = on_inventory_refresh
        self.on_overlay_off = on_overlay_off
        self.scanner = GrowthScanner(config_manager, ocr_processor, self.db)
        self.is_scanning = False
        self.session_cores = []
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(8)

        ctrl = toolbar_frame()
        ctrl_lay = QVBoxLayout(ctrl)
        ctrl_lay.setContentsMargins(12, 10, 12, 10)
        ctrl_lay.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(
            create_button(
                None,
                "Full scan (F9)",
                self.start_full_scan,
                variant="primary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Last row (F7)",
                self.start_last_row,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Current core (F8)",
                self.start_single,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Stop (F5)",
                self.stop_scan,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Clear log",
                self.clear_log,
                variant="ghost",
                font=self.fonts.ui,
            )
        )
        btn_row.addStretch(1)
        ctrl_lay.addLayout(btn_row)
        root.addWidget(ctrl)

        # Settings sit on canvas (not inside toolbar surface fill)
        settings = section_frame()
        settings_lay = QVBoxLayout(settings)
        settings_lay.setContentsMargins(0, 4, 0, 0)
        settings_lay.setSpacing(6)

        growth = self.config_manager.get_inventory_growth()
        tune_row = QHBoxLayout()
        tune_row.addStretch(1)
        self.scroll_rows_entry = self._tune_field(
            tune_row, "Scroll rows", str(growth.get("scroll_rows", 5))
        )
        self.scroll_extra_entry = self._tune_field(
            tune_row, "Extra px", str(growth.get("scroll_extra_px", 24))
        )
        self.skip_top_entry = self._tune_field(
            tune_row, "Skip top after scroll", str(growth.get("skip_rows_after_scroll", 1))
        )
        tune_row.addWidget(
            create_button(
                None,
                "Save scroll",
                self.save_scroll_settings,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        tune_row.addStretch(1)
        settings_lay.addLayout(tune_row)

        help_label = QLabel(
            "Before first run: unlock all Growth Data cores in-game.\n"
            "F9 walks 14x6, locks each scanned core, scrolls (~5 rows + extra px), "
            "skips top overlap row after scroll.\n"
            "F7 retries the bottom row - F8 scans the currently selected core only.\n"
            "If scroll leaves a partial top row, raise scroll_extra_px a little. "
            "Turn overlays off while scanning (F10)."
        )
        help_label.setFont(self.fonts.caption)
        help_label.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        help_label.setWordWrap(True)
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_lay.addWidget(help_label)
        root.addWidget(settings)

        stats_frame = stat_strip()
        stats_lay = QVBoxLayout(stats_frame)
        stats_lay.setContentsMargins(12, 8, 12, 8)
        self.stats_label = QLabel("Session: 0 | DB cores: 0 | Total qty: 0")
        self.stats_label.setFont(self.fonts.body_medium)
        self.stats_label.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_lay.addWidget(self.stats_label)
        root.addWidget(stats_frame)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(8)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(self.fonts.caption)
        self.log.setStyleSheet(
            f"QTextEdit {{ background-color: {THEME['bg_canvas']};"
            f" color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; }}"
        )
        content_lay.addWidget(self.log, stretch=2)

        self.tree = QTableWidget(0, len(_COLUMNS))
        self.tree.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.tree.verticalHeader().setVisible(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(False)
        configure_stretch_table(
            self.tree, stretch=1, min_widths=[100, 420, 50]
        )
        content_lay.addWidget(self.tree, stretch=3)
        root.addWidget(content, stretch=1)

        self.status_label = QLabel("Ready. F9 full scan, F7 last row, F8 current core, F5 stop, F10 overlay.")
        self.status_label.setFont(self.fonts.caption)
        self.status_label.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(28)
        root.addWidget(self.status_label)

        self._refresh_stats()

    def _tune_field(self, parent_layout, label: str, value: str) -> QLineEdit:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(2)
        parent_layout.addWidget(wrap)

        lbl = QLabel(label)
        lbl.setFont(self.fonts.caption)
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        wrap_lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        entry = QLineEdit()
        entry.setFixedWidth(70)
        entry.setFont(self.fonts.body)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setText(value)
        wrap_lay.addWidget(entry)
        return entry

    def save_scroll_settings(self, *, quiet: bool = False) -> bool:
        g = self.config_manager.get_inventory_growth()
        try:
            g["scroll_rows"] = float(self.scroll_rows_entry.text().strip())
            g["scroll_extra_px"] = int(self.scroll_extra_entry.text().strip())
            g["skip_rows_after_scroll"] = int(self.skip_top_entry.text().strip())
        except ValueError:
            if not quiet:
                QMessageBox.critical(
                    self, "Invalid", "Scroll rows / extra px / skip top must be numbers."
                )
            return False
        self.config_manager.save_config()
        if not quiet:
            self._append_log(
                f"Saved scroll: rows={g['scroll_rows']} extra={g['scroll_extra_px']}px "
                f"skip_top={g['skip_rows_after_scroll']}"
            )
        return True

    def clear_log(self):
        self.log.clear()

    def _append_log(self, msg: str):
        # Newest lines on top; color [Bulwark]/[Sentinel]/... with class hues
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        default_fmt = QTextCharFormat()
        default_fmt.setForeground(QColor(THEME["text_primary"]))
        m = _LOG_TYPE_RE.search(msg)
        if m:
            before, typ, after = msg[: m.start()], m.group(1), msg[m.end() :]
            cursor.insertText(before, default_fmt)
            type_fmt = QTextCharFormat()
            type_fmt.setForeground(QColor(class_color(typ)))
            cursor.insertText(f"[{typ}]", type_fmt)
            cursor.insertText(after, default_fmt)
        else:
            cursor.insertText(msg, default_fmt)
        cursor.insertText("\n", default_fmt)
        self.log.moveCursor(QTextCursor.MoveOperation.Start)

    def _status(self, msg: str):
        call_soon(lambda m=msg: self._append_log(m))

    def _on_core(self, core: dict):
        def _ui():
            perks = ", ".join(
                f"{p['name']} Lv.{p['level']}" for p in core.get("perks") or []
            )
            ctype = core.get("type")
            self.tree.insertRow(0)
            values = (ctype, perks, str(core.get("quantity", 1)))
            color = QColor(class_color(ctype))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(int(_COLUMNS[col][2]))
                item.setForeground(color)
                self.tree.setItem(0, col, item)
            self.session_cores.append(core)
            self._refresh_stats()
            if self.on_inventory_refresh:
                self.on_inventory_refresh()

        call_soon(_ui)

    def _refresh_stats(self):
        self.stats_label.setText(
            f"Session: {len(self.session_cores)} | "
            f"DB unique: {self.db.unique_count()} | "
            f"Total qty: {self.db.total_quantity()}"
        )

    def _busy(self) -> bool:
        if self.is_scanning:
            QMessageBox.information(self, "Busy", "A scan is already running.")
            return True
        return False

    def _hide_overlay(self):
        if self.on_overlay_off is not None:
            self.on_overlay_off()
        elif self.overlay_manager.active:
            self.overlay_manager.hide()

    def stop_scan(self):
        self.scanner.stop()
        self._status("Stop requested...")

    def start_full_scan(self):
        if self._busy():
            return
        self.save_scroll_settings(quiet=True)
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Full scan (F9) ===")

        def _run():
            try:
                result = self.scanner.scan_full(
                    status=self._status, on_core=self._on_core
                )
                self._status(
                    f"Done: scanned={result['scanned']} "
                    f"skipped={result['skipped_locked']} pages={result['pages']}"
                )
            finally:
                self.is_scanning = False
                call_soon(self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()

    def start_last_row(self):
        if self._busy():
            return
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Last row (F7) ===")

        def _run():
            try:
                self.scanner.scan_last_row(status=self._status, on_core=self._on_core)
            finally:
                self.is_scanning = False
                call_soon(self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()

    def start_single(self):
        if self._busy():
            return
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Single core (F8) ===")

        def _run():
            try:
                self.scanner.scan_single(status=self._status, on_core=self._on_core)
            finally:
                self.is_scanning = False
                call_soon(self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()

