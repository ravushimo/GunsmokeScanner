"""Gacha History - filterable Access Records timeline (PySide6)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.gacha_stats import ELITE_HARD_PITY, build_history
from src.data.gacha_db import GachaDB
from src.ui.components.date_picker import DatePickerField
from src.ui.styles import configure_stretch_table, create_button, section_frame, stat_strip


BANNER_ORDER = (
    "Premium Doll",
    "Premium Weapon",
    "Custom Dolls",
    "Custom Weapons",
    "Standard",
)

# (label, width, alignment)
_COLUMNS = (
    ("#", 50, Qt.AlignmentFlag.AlignCenter),
    ("Pity", 50, Qt.AlignmentFlag.AlignCenter),
    ("Time", 150, Qt.AlignmentFlag.AlignLeft),
    ("Source", 150, Qt.AlignmentFlag.AlignLeft),
    ("Type", 70, Qt.AlignmentFlag.AlignCenter),
    ("Name", 200, Qt.AlignmentFlag.AlignLeft),
    ("Rarity", 70, Qt.AlignmentFlag.AlignCenter),
)


class GachaHistoryTab(QWidget):
    # Cap rows drawn in the table - pity still uses full timeline
    DISPLAY_LIMIT = 800

    def __init__(self, parent, fonts, db: GachaDB = None, on_change=None):
        super().__init__(parent)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_change = on_change
        self._cached_timeline = None
        self._cache_key = None
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self._build_ui()
        self.refresh()

    def _filter_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self.fonts.ui)
        lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        return lbl

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(6)

        filter_section = section_frame()
        root.addWidget(filter_section)
        filter_lay = QVBoxLayout(filter_section)
        filter_lay.setContentsMargins(0, 0, 0, 4)
        filter_lay.setSpacing(4)

        # Two stacked rows so controls stay visible at default (~720-860) width
        row_filters = QHBoxLayout()
        row_filters.setSpacing(6)
        filter_lay.addLayout(row_filters)

        row_filters.addWidget(self._filter_label("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(["All"])
        self.source_combo.setFont(self.fonts.body)
        self.source_combo.setFixedWidth(148)
        self.source_combo.currentTextChanged.connect(lambda _t: self.refresh())
        row_filters.addWidget(self.source_combo)
        row_filters.addSpacing(10)

        row_filters.addWidget(self._filter_label("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Doll", "Weapons"])
        self.type_combo.setFont(self.fonts.body)
        self.type_combo.setFixedWidth(90)
        self.type_combo.currentTextChanged.connect(lambda _t: self.refresh())
        row_filters.addWidget(self.type_combo)
        row_filters.addSpacing(10)

        row_filters.addWidget(self._filter_label("Rarity:"))
        self.rarity_combo = QComboBox()
        self.rarity_combo.addItems(["All", "Elite", "Standard", "Retired"])
        self.rarity_combo.setFont(self.fonts.body)
        self.rarity_combo.setFixedWidth(96)
        self.rarity_combo.currentTextChanged.connect(lambda _t: self.refresh())
        row_filters.addWidget(self.rarity_combo)
        row_filters.addStretch(1)

        row_actions = QHBoxLayout()
        row_actions.setSpacing(6)
        filter_lay.addLayout(row_actions)

        self.from_picker = DatePickerField(
            filter_section, self.fonts, width=100, placeholder="From date", on_change=self.refresh
        )
        row_actions.addWidget(self.from_picker)

        self.to_picker = DatePickerField(
            filter_section, self.fonts, width=100, placeholder="To date", on_change=self.refresh
        )
        row_actions.addWidget(self.to_picker)

        refresh_btn = create_button(filter_section, "Refresh", self.refresh, variant="secondary", font=self.fonts.ui)
        refresh_btn.setFixedHeight(28)
        row_actions.addWidget(refresh_btn)

        fix_btn = create_button(filter_section, "Fix names", self.fix_names, variant="secondary", font=self.fonts.ui)
        fix_btn.setFixedHeight(28)
        row_actions.addWidget(fix_btn)

        clear_btn = create_button(filter_section, "Clear History", self.clear_db, variant="danger", font=self.fonts.ui)
        clear_btn.setFixedHeight(28)
        row_actions.addWidget(clear_btn)
        row_actions.addStretch(1)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        configure_stretch_table(
            self.table,
            stretch=5,
            min_widths=[c[1] for c in _COLUMNS],
        )
        root.addWidget(self.table, 1)

        stats_strip = stat_strip()
        root.addWidget(stats_strip)
        stats_lay = QVBoxLayout(stats_strip)
        stats_lay.setContentsMargins(0, 8, 0, 8)
        stats_lay.setSpacing(2)

        self.stats_quality = QLabel("")
        self.stats_quality.setFont(self.fonts.body)
        self.stats_quality.setWordWrap(True)
        self.stats_quality.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        stats_lay.addWidget(self.stats_quality)

        self.stats_banners = QLabel("")
        self.stats_banners.setFont(self.fonts.body)
        self.stats_banners.setWordWrap(True)
        self.stats_banners.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        stats_lay.addWidget(self.stats_banners)

        self.stats_pity = QLabel("")
        self.stats_pity.setFont(self.fonts.body_medium)
        self.stats_pity.setWordWrap(True)
        self.stats_pity.setStyleSheet(f"color: {THEME['element_burn']}; background: transparent;")
        stats_lay.addWidget(self.stats_pity)

    def _format_stats(self, summary: dict, shown: int) -> None:
        hard = summary.get("hard_pity", ELITE_HARD_PITY)
        self.stats_quality.setText(
            f"Showing {shown}  \u00b7  DB total {self.db.count_pulls()}  \u00b7  "
            f"Elite dolls {summary.get('elite_dolls', 0)}  \u00b7  "
            f"Elite weapons {summary.get('elite_weapons', 0)}  \u00b7  "
            f"Standard {summary.get('standard', 0)}  \u00b7  "
            f"Retired {summary.get('retired', 0)}"
        )

        banners = summary.get("banners") or {}
        parts = []
        for name in BANNER_ORDER:
            if name in banners:
                parts.append(f"{name} {banners[name]}")
        for name, count in sorted(banners.items()):
            if name not in BANNER_ORDER:
                parts.append(f"{name} {count}")
        self.stats_banners.setText("Banners: " + ("  \u00b7  ".join(parts) if parts else "-"))

        avg = summary.get("avg_elite_doll_gap")
        avg_txt = f"  \u00b7  Avg pulls / Elite doll {avg}" if avg is not None else ""
        by_src = summary.get("pity_by_source") or {}
        # Prefer selected-source current pity when only one banner is in scope
        if len(by_src) == 1:
            src, cur = next(iter(by_src.items()))
            label = {
                "Targeted Procurement": "Premium Doll",
                "Military Upgrade": "Premium Weapon",
                "Custom Procurement - Dolls": "Custom Dolls",
                "Custom Procurement - Weapons": "Custom Weapons",
                "Standard Procurement": "Standard",
            }.get(src, src)
            pity_txt = f"Current pity - {label} {cur}/{hard}"
        else:
            doll_p = summary.get("pity_doll", 0)
            weap_p = summary.get("pity_weapon", 0)
            cd = summary.get("pity_custom_doll", 0)
            cw = summary.get("pity_custom_weapon", 0)
            st = summary.get("pity_standard", 0)
            pity_txt = (
                f"Current pity - Premium Doll {doll_p}/{hard}  \u00b7  "
                f"Premium Weapon {weap_p}/{hard}  \u00b7  "
                f"Custom Dolls {cd}/{hard}  \u00b7  "
                f"Custom Weapons {cw}/{hard}  \u00b7  "
                f"Standard {st}/{hard}"
            )
        self.stats_pity.setText(pity_txt + avg_txt)

    def fix_names(self) -> None:
        from src.core.gacha_names import propose_name_fixes

        proposals = propose_name_fixes(self.db.distinct_item_name_types())
        if not proposals:
            QMessageBox.information(
                self, "Fix names", "No OCR name mismatches found against the known catalog."
            )
            return
        self._open_fix_names_dialog(proposals)

    def _open_fix_names_dialog(self, proposals: List[Dict[str, str]]) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Fix item names")
        dlg.resize(560, 420)
        dlg.setStyleSheet(f"background-color: {THEME['bg_canvas']};")

        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(6)

        info = QLabel("Select corrections to apply (matched by Type so dolls/weapons stay separate):")
        info.setFont(self.fonts.body)
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        root.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {THEME['bg_canvas']}; border: none; }}")
        content = QWidget()
        content.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(2)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # key = (raw, item_type) so Lewis Doll and Lewis Gun Weapon can both appear
        checks: Dict[Tuple[str, str], Tuple[QCheckBox, str, str]] = {}
        for p in proposals:
            itype = p.get("item_type") or ""
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 2, 0, 2)
            cb = QCheckBox()
            cb.setChecked(True)
            row_lay.addWidget(cb)
            type_tag = f"[{itype}] " if itype else ""
            lbl = QLabel(f'{type_tag}{p["raw"]}  ->  {p["fixed"]}')
            lbl.setFont(self.fonts.body)
            lbl.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
            row_lay.addWidget(lbl, 1)
            content_lay.addWidget(row)
            checks[(p["raw"], itype)] = (cb, p["fixed"], itype)
        content_lay.addStretch(1)

        btn_row = QHBoxLayout()
        root.addLayout(btn_row)

        def select_all(value: bool) -> None:
            for cb, _fixed, _itype in checks.values():
                cb.setChecked(value)

        select_all_btn = create_button(dlg, "Select all", lambda: select_all(True), variant="ghost", font=self.fonts.ui)
        btn_row.addWidget(select_all_btn)
        select_none_btn = create_button(dlg, "Select none", lambda: select_all(False), variant="ghost", font=self.fonts.ui)
        btn_row.addWidget(select_none_btn)
        btn_row.addStretch(1)

        def apply() -> None:
            pairs = [
                (raw, fixed, itype)
                for (raw, _t), (cb, fixed, itype) in checks.items()
                if cb.isChecked()
            ]
            if not pairs:
                dlg.accept()
                return
            n = self.db.apply_name_fixes(pairs)
            dlg.accept()
            QMessageBox.information(
                self, "Fix names", f"Updated {n} pull row(s) across {len(pairs)} name(s)."
            )
            self.invalidate_cache()
            self.refresh()
            if self.on_change:
                self.on_change()

        cancel_btn = create_button(dlg, "Cancel", dlg.reject, variant="secondary", font=self.fonts.ui)
        btn_row.addWidget(cancel_btn)
        apply_btn = create_button(dlg, "Apply selected", apply, variant="primary", font=self.fonts.ui)
        btn_row.addWidget(apply_btn)

        dlg.exec()

    def _row_color(self, rarity_v: str, pity_high: bool) -> str:
        if pity_high:
            return THEME["element_omni"]
        return {
            "elite": THEME["element_electric"],
            "standard": THEME["class_vanguard"],
            "retired": THEME["element_physical"],
        }.get(rarity_v, THEME["text_primary"])

    def refresh(self) -> None:
        source = self.source_combo.currentText() or "All"
        item_type = self.type_combo.currentText() or "All"
        rarity = self.rarity_combo.currentText() or "All"
        date_from = self.from_picker.get() or None
        date_to = self.to_picker.get() or None
        if date_to and len(date_to) == 10:
            date_to = date_to + " 23:59:59"

        # Reload timeline only when DB size changes or date filter changes
        count = self.db.count_pulls()
        cache_key = (count, date_from, date_to)
        if self._cached_timeline is None or self._cache_key != cache_key:
            self._cached_timeline = self.db.list_all_oldest_first(
                date_from=date_from,
                date_to=date_to,
            )
            self._cache_key = cache_key

        sources = ["All"] + sorted(
            {p.get("purchase_source") or "" for p in self._cached_timeline if p.get("purchase_source")}
        )
        current = self.source_combo.currentText()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItems(sources)
        if current in sources:
            self.source_combo.setCurrentText(current)
            source = current
        else:
            self.source_combo.setCurrentText("All")
            source = "All"
        self.source_combo.blockSignals(False)

        display, summary = build_history(
            self._cached_timeline,
            purchase_source=None if source == "All" else source,
            item_type=None if item_type == "All" else item_type,
            rarity=None if rarity == "All" else rarity,
        )

        total_shown = len(display)
        truncated = total_shown > self.DISPLAY_LIMIT
        rows = display[: self.DISPLAY_LIMIT]

        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            rarity_v = p.get("rarity") or "retired"
            pity = p.get("pity")
            pity_str = "" if pity is None else str(pity)
            pity_high = pity is not None and pity >= ELITE_HARD_PITY - 10
            color = self._row_color(rarity_v, pity_high)
            values = (
                str(p.get("pull_index", "")),
                pity_str,
                p["purchase_time"],
                p.get("banner") or p["purchase_source"],
                p["item_type"],
                p["item_name"],
                rarity_v,
            )
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(int(_COLUMNS[c][2] | Qt.AlignmentFlag.AlignVCenter))
                item.setForeground(QBrush(QColor(color)))
                self.table.setItem(r, c, item)

        self._format_stats(summary, total_shown)
        if truncated:
            self.stats_quality.setText(
                self.stats_quality.text()
                + f"  \u00b7  Table shows newest {self.DISPLAY_LIMIT} of {total_shown}"
            )

    def invalidate_cache(self) -> None:
        self._cached_timeline = None
        self._cache_key = None

    def clear_db(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "This will permanently delete ALL saved gacha pulls from the local database.\n\n"
            "This data cannot be recovered. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_all()
        self.invalidate_cache()
        self.refresh()
        if self.on_change:
            self.on_change()
