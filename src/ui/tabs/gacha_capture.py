"""Gacha Access Records capture controls - PySide6 port."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.gacha_scanner import GachaScanner
from src.data.gacha_db import GachaDB
from src.ui.qt_util import call_soon
from src.ui.styles import (
    configure_stretch_table,
    create_button,
    section_frame,
    stat_strip,
    toolbar_frame,
)

_COLUMNS = (
    ("Time", 160, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Source", 160, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Type", 80, Qt.AlignmentFlag.AlignCenter),
    ("Name", 220, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Rarity", 70, Qt.AlignmentFlag.AlignCenter),
)


class GachaCaptureTab(QWidget):
    def __init__(
        self,
        parent,
        config_manager,
        ocr_processor,
        overlay_manager,
        fonts,
        db: GachaDB = None,
        on_history_refresh=None,
        on_overlay_off=None,
    ):
        super().__init__(parent)
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_history_refresh = on_history_refresh
        self.on_overlay_off = on_overlay_off

        self.scanner = GachaScanner(config_manager, ocr_processor, self.db)
        self.session_pulls = []
        self.is_scanning = False

        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(8)

        ctrl_frame = toolbar_frame()
        ctrl_lay = QVBoxLayout(ctrl_frame)
        ctrl_lay.setContentsMargins(12, 10, 12, 10)
        ctrl_lay.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(
            create_button(
                None,
                "Scan Access Records (F9)",
                self.start_scan_thread,
                variant="primary",
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
                "Clear Session",
                self.clear_session,
                variant="danger",
                font=self.fonts.ui,
            )
        )
        btn_row.addWidget(
            create_button(
                None,
                "Clear History",
                self.clear_history,
                variant="danger",
                font=self.fonts.ui,
            )
        )
        btn_row.addStretch(1)
        ctrl_lay.addLayout(btn_row)
        root.addWidget(ctrl_frame)

        # Settings sit on canvas (not inside toolbar surface fill)
        settings = section_frame()
        settings_lay = QVBoxLayout(settings)
        settings_lay.setContentsMargins(0, 4, 0, 0)
        settings_lay.setSpacing(6)

        timing_row = QHBoxLayout()
        timing_row.addStretch(1)
        gacha = self.config_manager.get_gacha()
        self.click_delay_entry = self._timing_field(
            timing_row,
            "Click delay (ms)",
            str(int(gacha.get("click_delay_ms", 150))),
        )
        self.settle_delay_entry = self._timing_field(
            timing_row,
            "OCR settle (ms)",
            str(int(gacha.get("ocr_settle_ms", 100))),
        )
        timing_row.addStretch(1)
        settings_lay.addLayout(timing_row)

        help_label = QLabel(
            "Open Access Records (any filter/banner). Scanner resets to page 1, "
            "walks newest to oldest, and stops once it hits pulls already in history "
            "(mixed pages from 10-pulls are fine). F9 start - F5 stop."
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
        self.stats_label = QLabel("Session pulls: 0 | DB total: 0")
        self.stats_label.setFont(self.fonts.body_medium)
        self.stats_label.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_lay.addWidget(self.stats_label)
        root.addWidget(stats_frame)

        self.tree = QTableWidget(0, len(_COLUMNS))
        self.tree.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.tree.verticalHeader().setVisible(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(False)
        configure_stretch_table(
            self.tree, stretch=3, min_widths=[160, 160, 80, 220, 70]
        )
        root.addWidget(self.tree, stretch=1)

        self.status_label = QLabel("Ready. Open Access Records, then F9 to scan (F5 to stop).")
        self.status_label.setFont(self.fonts.caption)
        self.status_label.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(28)
        root.addWidget(self.status_label)

        self._refresh_stats()

    def _timing_field(self, parent_layout, label: str, initial: str) -> QLineEdit:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wrap_lay = QHBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(6)
        parent_layout.addWidget(wrap)

        lbl = QLabel(label)
        lbl.setFont(self.fonts.caption)
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        wrap_lay.addWidget(lbl)

        entry = QLineEdit()
        entry.setFixedWidth(70)
        entry.setFont(self.fonts.mono)
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setText(initial)
        entry.editingFinished.connect(self.apply_timing)
        wrap_lay.addWidget(entry)
        return entry

    def apply_timing(self):
        """Persist click/settle delays from the UI into gacha config."""
        gacha = self.config_manager.get_gacha()
        try:
            click_ms = int(self.click_delay_entry.text().strip())
            settle_ms = int(self.settle_delay_entry.text().strip())
        except ValueError:
            # Restore last saved values on bad input
            self.click_delay_entry.setText(str(int(gacha.get("click_delay_ms", 150))))
            self.settle_delay_entry.setText(str(int(gacha.get("ocr_settle_ms", 100))))
            return

        click_ms = max(0, min(click_ms, 10000))
        settle_ms = max(0, min(settle_ms, 10000))
        gacha["click_delay_ms"] = click_ms
        gacha["ocr_settle_ms"] = settle_ms
        self.config_manager.save_config()

        # Keep fields showing the clamped values
        self.click_delay_entry.setText(str(click_ms))
        self.settle_delay_entry.setText(str(settle_ms))

    def _refresh_stats(self):
        self.stats_label.setText(
            f"Session pulls: {len(self.session_pulls)} | "
            f"DB total: {self.db.count_pulls()}"
        )

    def start_scan_thread(self):
        if self.is_scanning:
            return

        self.apply_timing()
        self.is_scanning = True
        self.session_pulls = []
        self.refresh_table()
        # Overlays would sit on top of the game and break OCR / clicks
        if self.on_overlay_off is not None:
            self.on_overlay_off()
        elif self.overlay_manager.active:
            self.overlay_manager.hide()

        gacha = self.config_manager.get_gacha()
        self.status_label.setText(
            f"Starting scan... "
            f"(click {gacha.get('click_delay_ms')}ms / "
            f"settle {gacha.get('ocr_settle_ms')}ms)"
        )
        threading.Thread(target=self._scan_logic, daemon=True).start()

    def stop_scan(self):
        if self.is_scanning:
            self.scanner.request_stop()
            self.status_label.setText("Stopping...")

    def _set_status(self, msg: str):
        call_soon(lambda m=msg: self.status_label.setText(m))

    def _on_pull(self, pull: dict):
        call_soon(lambda p=pull: self._append_pull(p))

    def _row_values(self, pull: dict):
        return (
            pull["purchase_time"],
            pull["purchase_source"],
            pull["item_type"],
            pull["item_name"],
            (pull.get("rarity_color") or "").title(),
        )

    def _fill_row(self, row: int, pull: dict):
        for col, value in enumerate(self._row_values(pull)):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(int(_COLUMNS[col][2]))
            self.tree.setItem(row, col, item)

    def _append_pull(self, pull: dict):
        self.session_pulls.append(pull)
        row = self.tree.rowCount()
        self.tree.insertRow(row)
        self._fill_row(row, pull)
        self._refresh_stats()

    def _scan_logic(self):
        try:
            summary = self.scanner.scan_all_pages(
                status_cb=self._set_status,
                on_pull=self._on_pull,
            )
            call_soon(lambda s=summary: self._on_scan_complete(s))
        except Exception as e:
            print(f"Gacha scan error: {e}")
            err = str(e)
            call_soon(lambda msg=err: self.status_label.setText(f"Error: {msg}"))
            self.is_scanning = False

    def _on_scan_complete(self, summary: dict):
        self.is_scanning = False
        self._refresh_stats()
        if summary.get("caught_up"):
            msg = (
                f"Caught up. Pages {summary['pages']}, "
                f"new {summary['inserted']}, already known {summary['skipped']}."
            )
        elif summary.get("stopped"):
            msg = (
                f"Stopped. Pages {summary['pages']}, "
                f"new {summary['inserted']}, known {summary['skipped']}."
            )
        else:
            msg = (
                f"Done. Pages {summary['pages']}, "
                f"new {summary['inserted']}, known {summary['skipped']}."
            )
        self.status_label.setText(msg)
        if not summary.get("stopped"):
            try:
                from src.core.notify import play_scan_complete_sound

                play_scan_complete_sound()
            except Exception:
                pass
        if self.on_history_refresh:
            self.on_history_refresh()

    def refresh_table(self):
        self.tree.setRowCount(0)
        for pull in self.session_pulls:
            row = self.tree.rowCount()
            self.tree.insertRow(row)
            self._fill_row(row, pull)

    def clear_session(self):
        if self.is_scanning:
            QMessageBox.warning(self, "Scanning", "Stop the scan before clearing.")
            return
        reply = QMessageBox.question(
            self,
            "Clear Session",
            "Delete all session pull data from the table?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.session_pulls = []
        self.refresh_table()
        self._refresh_stats()
        self.status_label.setText("Session cleared.")

    def clear_history(self):
        """Wipe saved pulls from SQLite so a fresh scan can be tested."""
        if self.is_scanning:
            QMessageBox.warning(
                self, "Scanning", "Stop the scan before clearing history."
            )
            return
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Delete ALL saved gacha pulls from the local database?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_all()
        self.session_pulls = []
        self.refresh_table()
        self._refresh_stats()
        self.status_label.setText("History cleared. Ready for a new scan.")
        if self.on_history_refresh:
            self.on_history_refresh()
