"""Local Growth Data inventory browser - PySide6 port."""

from __future__ import annotations

import csv
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME, class_color
from src.data.inventory_db import InventoryDB
from src.ui.styles import configure_stretch_table, create_button, section_frame, toolbar_frame

_CSV_FIELDS = (
    "core_type",
    "quantity",
    "perk1_name",
    "perk1_lvl",
    "perk2_name",
    "perk2_level",
    "perk3_name",
    "perk3_level",
)

_COLUMNS = (
    ("id", 40, Qt.AlignmentFlag.AlignCenter),
    ("Type", 100, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Perk1", 160, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Perk2", 160, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Perk3", 160, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    ("Qty", 50, Qt.AlignmentFlag.AlignCenter),
)


class InventoryListTab(QWidget):
    def __init__(self, parent, fonts, db: InventoryDB = None, on_change=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.fonts = fonts
        self.db = db or InventoryDB()
        self.on_change = on_change
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 12)
        outer.setSpacing(6)

        header = section_frame()
        outer.addWidget(header)
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 4)
        header_lay.setSpacing(2)

        title = QLabel("Scanned Growth Data")
        title.setFont(self.fonts.subheading)
        title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        header_lay.addWidget(title)

        self.summary = QLabel("")
        self.summary.setFont(self.fonts.caption)
        self.summary.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        header_lay.addWidget(self.summary)

        toolbar = toolbar_frame()
        outer.addWidget(toolbar)
        filters = QHBoxLayout(toolbar)
        filters.setContentsMargins(8, 6, 8, 6)
        filters.setSpacing(6)

        type_lbl = QLabel("Type:")
        type_lbl.setFont(self.fonts.body)
        type_lbl.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        filters.addWidget(type_lbl)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Bulwark", "Sentinel", "Vanguard", "Support"])
        self.type_combo.setFont(self.fonts.body)
        self.type_combo.currentTextChanged.connect(lambda _t: self.refresh())
        filters.addWidget(self.type_combo)

        filters.addWidget(
            create_button(
                toolbar, "Refresh", self.refresh, variant="secondary", font=self.fonts.ui
            )
        )
        filters.addWidget(
            create_button(
                toolbar,
                "Export CSV",
                self.export_csv,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        filters.addWidget(
            create_button(
                toolbar,
                "Clear all...",
                self.clear_all,
                variant="danger",
                font=self.fonts.ui,
            )
        )
        filters.addStretch(1)

        self.tree = QTableWidget(0, len(_COLUMNS))
        self.tree.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.tree.verticalHeader().setVisible(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(False)
        configure_stretch_table(
            self.tree,
            stretch=[2, 3, 4],
            min_widths=[c[1] for c in _COLUMNS],
        )
        outer.addWidget(self.tree, 1)

        edit_widget = QWidget()
        edit = QHBoxLayout(edit_widget)
        edit.setContentsMargins(0, 0, 0, 0)
        edit.setSpacing(6)
        outer.addWidget(edit_widget)

        qty_lbl = QLabel("Qty:")
        qty_lbl.setFont(self.fonts.body)
        qty_lbl.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        edit.addWidget(qty_lbl)

        self.qty_entry = QLineEdit()
        self.qty_entry.setFixedWidth(60)
        self.qty_entry.setFont(self.fonts.body)
        edit.addWidget(self.qty_entry)

        edit.addWidget(
            create_button(
                edit_widget,
                "Set quantity",
                self.set_quantity,
                variant="secondary",
                font=self.fonts.ui,
            )
        )
        edit.addWidget(
            create_button(
                edit_widget,
                "Delete row",
                self.delete_selected,
                variant="danger",
                font=self.fonts.ui,
            )
        )
        edit.addStretch(1)

    def refresh(self):
        self.tree.setRowCount(0)
        t = self.type_combo.currentText() or "All"
        cores = self.db.list_cores(core_type=None if t == "All" else t)
        self.tree.setRowCount(len(cores))
        for row, c in enumerate(cores):
            p1 = f"{c['perk1_name']} {c['perk1_level']}"
            p2 = f"{c['perk2_name']} {c['perk2_level']}"
            p3 = (
                f"{c['perk3_name']} {c['perk3_level']}"
                if c.get("perk3_name")
                else ""
            )
            values = (
                str(c["id"]),
                c["type"],
                p1,
                p2,
                p3,
                str(c["quantity"]),
            )
            color = QColor(class_color(c.get("type")))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(int(_COLUMNS[col][2]))
                item.setForeground(color)
                self.tree.setItem(row, col, item)
        self.summary.setText(
            f"{len(cores)} unique \u00b7 {self.db.total_quantity()} total copies "
            f"(filter: {t})"
        )

    def _selected_id(self):
        row = self.tree.currentRow()
        if row < 0:
            return None
        item = self.tree.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def set_quantity(self):
        core_id = self._selected_id()
        if core_id is None:
            QMessageBox.information(self, "Select", "Select a row first.")
            return
        try:
            qty = int(self.qty_entry.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Invalid", "Quantity must be an integer.")
            return
        self.db.update_quantity(core_id, qty)
        self.refresh()
        if self.on_change:
            self.on_change()

    def delete_selected(self):
        core_id = self._selected_id()
        if core_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete core id {core_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_core(core_id)
        self.refresh()
        if self.on_change:
            self.on_change()

    def export_csv(self):
        t = self.type_combo.currentText() or "All"
        cores = self.db.list_cores(core_type=None if t == "All" else t)
        if not cores:
            QMessageBox.information(self, "Export", "No cores to export for the current filter.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Growth Data CSV",
            f"growth_cores_{stamp}.csv",
            "CSV (*.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=_CSV_FIELDS,
                    delimiter=";",
                    lineterminator="\n",
                )
                writer.writeheader()
                for c in cores:
                    writer.writerow(
                        {
                            "core_type": c.get("type") or "",
                            "quantity": int(c.get("quantity") or 1),
                            "perk1_name": c.get("perk1_name") or "",
                            "perk1_lvl": c.get("perk1_level") if c.get("perk1_name") else "",
                            "perk2_name": c.get("perk2_name") or "",
                            "perk2_level": c.get("perk2_level") if c.get("perk2_name") else "",
                            "perk3_name": c.get("perk3_name") or "",
                            "perk3_level": c.get("perk3_level") if c.get("perk3_name") else "",
                        }
                    )
        except OSError as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(
            self,
            "Export",
            f"Wrote {len(cores)} row(s) to:\n{path}",
        )

    def clear_all(self):
        reply = QMessageBox.question(
            self,
            "Clear inventory",
            "Delete ALL scanned Growth Data from local DB?\n"
            "Also unlock all cores in-game before a full rescan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_all()
        self.refresh()
        if self.on_change:
            self.on_change()
