"""Gacha Stats - campaigns, 50/50, heatmap, banner filter (PySide6)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.gacha_stats import (
    BANNER_LABELS,
    ELITE_HARD_PITY,
    WORST_PULLS_V6,
    build_stats_report,
)
from src.data.gacha_db import GachaDB
from src.ui.components.charts import ActivityHeatmap, ChartFrame
from src.ui.styles import (
    card_frame,
    configure_stretch_table,
    create_button,
    section_frame,
    toolbar_frame,
)

BANNER_FILTER_ORDER = (
    ("All", None),
    ("Premium Doll", "Targeted Procurement"),
    ("Premium Weapon", "Military Upgrade"),
    ("Custom Dolls", "Custom Procurement - Dolls"),
    ("Custom Weapons", "Custom Procurement - Weapons"),
    ("Standard", "Standard Procurement"),
)

# Banner identity - GFL2 class colors (+ physical for Standard)
_BANNER_ACCENT = {
    "Premium Doll": THEME["class_vanguard"],
    "Premium Weapon": THEME["class_sentinel"],
    "Custom Dolls": THEME["class_support"],
    "Custom Weapons": THEME["class_bulwark"],
    "Standard": THEME["element_physical"],
    "Targeted Procurement": THEME["class_vanguard"],
    "Military Upgrade": THEME["class_sentinel"],
    "Custom Procurement - Dolls": THEME["class_support"],
    "Custom Procurement - Weapons": THEME["class_bulwark"],
    "Standard Procurement": THEME["element_physical"],
}

# 50/50 outcomes - Support / Omni / Electric (DESIGN class + type)
_OUTCOME_STYLE = {
    "win": ("W", "#E8F0EA", THEME["class_support"]),
    "loss": ("L", "#F5E8E6", THEME["element_omni"]),
    "guaranteed": ("G", "#1a1a1a", THEME["element_electric"]),
}

_PITY_ORDER = (
    ("Premium Doll", "pity_doll", "Targeted Procurement"),
    ("Premium Weapon", "pity_weapon", "Military Upgrade"),
    ("Custom Dolls", "pity_custom_doll", "Custom Procurement - Dolls"),
    ("Custom Weapons", "pity_custom_weapon", "Custom Procurement - Weapons"),
    ("Standard", "pity_standard", "Standard Procurement"),
)

# (key, header label, width, alignment)
_TABLE_COLUMNS = (
    ("name", "Name", 140, Qt.AlignmentFlag.AlignLeft),
    ("copies", "Copies", 60, Qt.AlignmentFlag.AlignCenter),
    ("potential", "Rank", 50, Qt.AlignmentFlag.AlignCenter),
    ("pulls", "Pulls", 60, Qt.AlignmentFlag.AlignCenter),
    ("first_pity", "1st pity", 70, Qt.AlignmentFlag.AlignCenter),
    ("losses", "L", 40, Qt.AlignmentFlag.AlignCenter),
    ("wins", "W", 40, Qt.AlignmentFlag.AlignCenter),
    ("guaranteed", "Guar.", 50, Qt.AlignmentFlag.AlignCenter),
    ("status", "Status", 90, Qt.AlignmentFlag.AlignCenter),
)


def _hex_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(hex_a: str, hex_b: str, t: float) -> str:
    """Blend two #rrggbb colors; t=0 -> a, t=1 -> b."""
    ar, ag, ab = _hex_rgb(hex_a)
    br, bg, bb = _hex_rgb(hex_b)
    r = int(round(ar + (br - ar) * t))
    g = int(round(ag + (bg - ag) * t))
    b = int(round(ab + (bb - ab) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def _soft_surface(accent: str, amount: float = 0.22) -> str:
    """Tint bg_raised toward an accent for subtle chip / cell fills."""
    return _blend(THEME["bg_raised"], accent, amount)


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)


class _MetricChip(QWidget):
    """Plain centered metric label; value text/color updates in place."""

    def __init__(self, fonts, label: str, accent: Optional[str] = None):
        super().__init__()
        self._accent = accent
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(0)

        title = QLabel(label.upper())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(fonts.body)
        title.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        lay.addWidget(title)

        self._value = QLabel("0")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setFont(fonts.heading)
        lay.addWidget(self._value)
        self.set_value("0")

    def set_value(self, text: str, accent: Optional[str] = None) -> None:
        color = accent or self._accent or THEME["text_strong"]
        self._value.setText(text)
        self._value.setStyleSheet(f"color: {color}; background: transparent;")


class _RatioBar(QWidget):
    """Thin horizontal fill bar used inside pity cards."""

    def __init__(self, ratio: float, color: str):
        super().__init__()
        self._ratio = max(0.0, min(1.0, ratio))
        self._color = color
        self.setFixedHeight(5)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(THEME["bg_canvas"]))
        if self._ratio > 0:
            w = max(4, int(self.width() * max(0.04, self._ratio)))
            painter.fillRect(0, 0, w, self.height(), QColor(self._color))
        painter.end()


def _pity_card(fonts, title: str, current: int, hard: int, accent: str) -> QFrame:
    ratio = min(1.0, current / hard) if hard else 0.0
    # Banner accent -> Electric -> Burn as pity climbs
    if ratio < 0.55:
        bar = accent
    elif ratio < 0.85:
        bar = _blend(accent, THEME["element_electric"], (ratio - 0.55) / 0.30)
    else:
        bar = _blend(THEME["element_electric"], THEME["element_burn"], (ratio - 0.85) / 0.15)

    border = _blend(THEME["border"], accent, 0.55)
    card = card_frame(accent=border)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(6, 5, 6, 5)
    lay.setSpacing(2)

    title_lbl = QLabel(title)
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_lbl.setFont(fonts.body_medium)
    title_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
    lay.addWidget(title_lbl)

    val_lbl = QLabel(f"{current} / {hard}")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    val_lbl.setFont(fonts.subheading)
    val_lbl.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
    lay.addWidget(val_lbl)

    lay.addWidget(_RatioBar(ratio, bar))
    return card


def _make_chip(fonts, outcome: str) -> QLabel:
    glyph, fg, bg = _OUTCOME_STYLE.get(outcome, ("?", THEME["text_muted"], THEME["bg_raised"]))
    chip = QLabel(glyph)
    chip.setFixedSize(20, 20)
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip.setFont(fonts.ui)
    chip.setStyleSheet(f"color: {fg}; background-color: {bg}; border: none;")
    return chip


class _SequenceRow(QWidget):
    """Single row of newest-first chips; truncates to fit available width."""

    def __init__(self, fonts, outcomes: Sequence[str]):
        super().__init__()
        self._fonts = fonts
        self._outcomes = list(outcomes)
        self._built_w = -1
        self.setFixedHeight(24)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 0, 8, 2)
        self._layout.setSpacing(1)
        self._render(force=True)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render()

    def _render(self, force: bool = False) -> None:
        w = self.width()
        if not force and w == self._built_w:
            return
        self._built_w = w
        _clear_layout(self._layout)
        if w < 20:
            return

        if not self._outcomes:
            self._layout.addStretch(1)
            empty = QLabel("-")
            empty.setFont(self._fonts.body)
            empty.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
            self._layout.addWidget(empty)
            self._layout.addStretch(1)
            return

        # Chips are ~20px wide + spacing; keep a safety margin so the newest
        # chip is never clipped.
        chip_span = 22
        ellipsis_w = 18
        avail = max(20, w - 16)
        shown = list(self._outcomes)
        truncated = False
        while shown:
            need = len(shown) * chip_span
            will_trunc = len(shown) < len(self._outcomes)
            if will_trunc:
                need += ellipsis_w
            if need <= avail:
                truncated = will_trunc
                break
            shown.pop(0)
        if not shown:
            shown = [self._outcomes[-1]]
            truncated = len(self._outcomes) > 1

        # Right-align so the newest chip is flush to the right (fully visible)
        self._layout.addStretch(1)
        if truncated:
            dots = QLabel("...")
            dots.setFont(self._fonts.body)
            dots.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
            self._layout.addWidget(dots)
        for o in shown:
            self._layout.addWidget(_make_chip(self._fonts, o))


def _fifty_card(fonts, title: str, stats: Dict[str, Any], *, guarantee: bool) -> QFrame:
    accent = _BANNER_ACCENT.get(title, THEME["border"])
    border = THEME["element_electric"] if guarantee else _blend(THEME["border"], accent, 0.55)

    card = card_frame(accent=border)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(8, 6, 8, 6)
    lay.setSpacing(2)

    head = QHBoxLayout()
    title_lbl = QLabel(title)
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_lbl.setFont(fonts.body_medium)
    title_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
    head.addWidget(title_lbl, 1)
    if guarantee:
        badge = QLabel("NEXT GUARANTEED")
        badge.setFont(fonts.body)
        badge.setFixedHeight(18)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: #1a1a1a; background-color: {THEME['element_electric']}; padding: 0 4px; border: none;"
        )
        head.addWidget(badge)
    lay.addLayout(head)

    nums = QHBoxLayout()
    nums.setSpacing(2)
    for key, label, color in (
        ("wins", "WIN", THEME["class_support"]),
        ("losses", "LOSS", THEME["element_omni"]),
        ("guaranteed", "GUAR", THEME["element_electric"]),
    ):
        cell = QFrame()
        cell.setStyleSheet(f"background-color: {_soft_surface(color, 0.28)}; border: none;")
        cell_lay = QVBoxLayout(cell)
        cell_lay.setContentsMargins(2, 4, 2, 4)
        cell_lay.setSpacing(0)
        val = QLabel(str(stats.get(key, 0)))
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setFont(fonts.heading)
        val.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        cell_lay.addWidget(val)
        cap = QLabel(label)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setFont(fonts.body)
        cap.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent; border: none;")
        cell_lay.addWidget(cap)
        nums.addWidget(cell, 1)
    lay.addLayout(nums)

    wr = stats.get("win_rate")
    wr_txt = f"{wr}% win rate" if wr is not None else "No decided 50/50 yet"
    wr_lbl = QLabel(wr_txt)
    wr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wr_lbl.setFont(fonts.body)
    wr_lbl.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
    lay.addWidget(wr_lbl)

    streaks_txt = (
        f"Longest W{stats.get('longest_win_streak', 0)} L{stats.get('longest_loss_streak', 0)}"
        f"  -  Now W{stats.get('current_win_streak', 0)} L{stats.get('current_loss_streak', 0)}"
    )
    streaks_lbl = QLabel(streaks_txt)
    streaks_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    streaks_lbl.setFont(fonts.body)
    streaks_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
    lay.addWidget(streaks_lbl)

    seq_lbl = QLabel("Sequence (newest shown)")
    seq_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    seq_lbl.setFont(fonts.body)
    seq_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
    lay.addWidget(seq_lbl)

    outcomes: Sequence[str] = list(stats.get("sequence") or [])
    lay.addWidget(_SequenceRow(fonts, outcomes))
    return card


class GachaStatsTab(QWidget):
    def __init__(self, parent, fonts, db: GachaDB = None):
        super().__init__(parent)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 4)
        root.setSpacing(4)

        toolbar = toolbar_frame()
        root.addWidget(toolbar)
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)

        banner_lbl = QLabel("Banner:")
        banner_lbl.setFont(self.fonts.ui)
        banner_lbl.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        row.addWidget(banner_lbl)

        self.banner_combo = QComboBox()
        self.banner_combo.addItems([label for label, _ in BANNER_FILTER_ORDER])
        self.banner_combo.setFont(self.fonts.body)
        self.banner_combo.setFixedWidth(160)
        self.banner_combo.currentTextChanged.connect(lambda _t: self.refresh())
        row.addWidget(self.banner_combo)
        row.addSpacing(10)

        desc = QLabel("Filter applies to the whole Stats page.")
        desc.setFont(self.fonts.body)
        desc.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        row.addWidget(desc, 1)

        refresh_btn = create_button(toolbar, "Refresh", self.refresh, variant="secondary", font=self.fonts.ui)
        refresh_btn.setFixedSize(90, 28)
        row.addWidget(refresh_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)

        content = QWidget()
        content.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self.scroll.setWidget(content)
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(2, 4, 2, 4)
        content_lay.setSpacing(4)

        # --- Overview metrics (no cards) ---
        summary_widget = QWidget()
        self.summary_row = QHBoxLayout(summary_widget)
        self.summary_row.setContentsMargins(0, 4, 0, 6)
        self.summary_row.setSpacing(0)
        # Freeze / Vanguard / Burn - cool total, doll class, weapon heat
        self.chip_total = _MetricChip(self.fonts, "Total pulls", THEME["element_freeze"])
        self.chip_dolls = _MetricChip(self.fonts, "Elite dolls", THEME["class_vanguard"])
        self.chip_weapons = _MetricChip(self.fonts, "Elite weapons", THEME["element_burn"])
        for chip in (self.chip_total, self.chip_dolls, self.chip_weapons):
            self.summary_row.addWidget(chip, 1)
        content_lay.addWidget(summary_widget)

        # --- Current pity (flat section + title) ---
        pity_section = section_frame()
        content_lay.addWidget(pity_section)
        pity_outer = QVBoxLayout(pity_section)
        pity_outer.setContentsMargins(0, 4, 0, 4)
        pity_outer.setSpacing(6)
        pity_title = QLabel("Current pity")
        pity_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pity_title.setFont(self.fonts.subheading)
        pity_title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        pity_outer.addWidget(pity_title)
        self.pity_row = QHBoxLayout()
        self.pity_row.setSpacing(6)
        pity_outer.addLayout(self.pity_row)

        # --- 50/50 (flat section + title) ---
        fifty_section = section_frame()
        content_lay.addWidget(fifty_section)
        fifty_outer = QVBoxLayout(fifty_section)
        fifty_outer.setContentsMargins(0, 4, 0, 4)
        fifty_outer.setSpacing(6)
        fifty_title = QLabel("50/50 - Premium banners")
        fifty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fifty_title.setFont(self.fonts.subheading)
        fifty_title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        fifty_outer.addWidget(fifty_title)
        self.fifty_row = QHBoxLayout()
        self.fifty_row.setSpacing(6)
        fifty_outer.addLayout(self.fifty_row)

        self.heatmap = ActivityHeatmap(content, fonts=self.fonts, height=186)
        content_lay.addWidget(self.heatmap)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(4)
        self.chart_banner = ChartFrame(content, "Pulls by banner", kind="pie", height=180, fonts=self.fonts)
        self.chart_rarity = ChartFrame(content, "Pulls by rarity", kind="pie", height=180, fonts=self.fonts)
        charts_row.addWidget(self.chart_banner, 1)
        charts_row.addWidget(self.chart_rarity, 1)
        content_lay.addLayout(charts_row)

        charts_row2 = QHBoxLayout()
        charts_row2.setSpacing(4)
        self.chart_dolls = ChartFrame(
            content, "Pulls spent per premium doll", kind="campaign", height=240, fonts=self.fonts
        )
        self.chart_weapons = ChartFrame(
            content, "Pulls spent per premium weapon", kind="campaign", height=240, fonts=self.fonts
        )
        charts_row2.addWidget(self.chart_dolls, 1)
        charts_row2.addWidget(self.chart_weapons, 1)
        content_lay.addLayout(charts_row2)

        campaigns_lbl = QLabel("Premium campaigns")
        campaigns_lbl.setFont(self.fonts.subheading)
        campaigns_lbl.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        content_lay.addWidget(campaigns_lbl)

        self.table = QTableWidget(0, len(_TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in _TABLE_COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setMinimumHeight(280)
        configure_stretch_table(
            self.table,
            stretch=0,
            min_widths=[c[2] for c in _TABLE_COLUMNS],
        )
        content_lay.addWidget(self.table)

    def _selected_source(self) -> Optional[str]:
        label = self.banner_combo.currentText()
        for name, source in BANNER_FILTER_ORDER:
            if name == label:
                return source
        return None

    def _render_summary(self, summary: Dict[str, Any]) -> None:
        self.chip_total.set_value(str(summary.get("total", 0)))
        self.chip_dolls.set_value(str(summary.get("elite_dolls", 0)))
        self.chip_weapons.set_value(str(summary.get("elite_weapons", 0)))

    def _render_pity(self, summary: Dict[str, Any], src: Optional[str]) -> None:
        _clear_layout(self.pity_row)
        hard = summary.get("hard_pity", ELITE_HARD_PITY)
        by = summary.get("pity_by_source") or {}
        items: List[Tuple[str, int, str]] = []
        if src:
            label = BANNER_LABELS.get(src, src)
            accent = _BANNER_ACCENT.get(src) or _BANNER_ACCENT.get(label, THEME["element_physical"])
            items.append((label, int(by.get(src, 0)), accent))
        else:
            for title, key, source in _PITY_ORDER:
                cur = summary.get(key)
                if cur is None:
                    cur = by.get(source, 0)
                accent = _BANNER_ACCENT.get(title, THEME["element_physical"])
                items.append((title, int(cur or 0), accent))
        for title, cur, accent in items:
            self.pity_row.addWidget(_pity_card(self.fonts, title, cur, hard, accent), 1)

    def _render_fifty(self, fifty: Dict[str, Any], src: Optional[str]) -> None:
        _clear_layout(self.fifty_row)
        by_banner = fifty.get("by_banner") or {}

        if src == "Standard Procurement":
            msg = QLabel("Standard banner - pity only. No 50/50 win/loss tracking.")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setFont(self.fonts.body)
            msg.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
            self.fifty_row.addWidget(msg, 1)
            return

        cards: List[Tuple[str, Dict[str, Any], bool]] = []
        for label, stats in by_banner.items():
            if src:
                want = BANNER_LABELS.get(src, src)
                if label != want:
                    continue
            g = False
            if label == "Premium Doll":
                g = bool(fifty.get("guarantee_premium_doll"))
            elif label == "Premium Weapon":
                g = bool(fifty.get("guarantee_premium_weapon"))
            cards.append((label, stats, g))

        if not cards:
            msg = QLabel("No 50/50 outcomes in this filter.")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setFont(self.fonts.body)
            msg.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
            self.fifty_row.addWidget(msg, 1)
            return

        for label, stats, g in cards:
            self.fifty_row.addWidget(_fifty_card(self.fonts, label, stats, guarantee=g), 1)

    def _render_table(self, campaigns: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(len(campaigns))
        for row, c in enumerate(campaigns):
            status = "V6 done" if c.get("complete") else "In progress"
            if c.get("extras"):
                status += f" +{c['extras']}"
            color = THEME["class_support"] if c.get("complete") else THEME["element_electric"]
            values = (
                c.get("name", ""),
                c.get("copies", 0),
                c.get("potential", ""),
                c.get("pulls_spent", 0),
                c.get("first_pity", ""),
                c.get("fifty_losses", 0),
                c.get("fifty_wins", 0),
                c.get("fifty_guaranteed", 0),
                status,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                align = _TABLE_COLUMNS[col][3]
                item.setTextAlignment(int(align | Qt.AlignmentFlag.AlignVCenter))
                item.setForeground(QBrush(QColor(color)))
                self.table.setItem(row, col, item)

    def refresh(self) -> None:
        self.db.normalize_purchase_sources()
        timeline = self.db.list_all_oldest_first()
        report = build_stats_report(timeline, purchase_source=self._selected_source())
        summary = report["summary"]
        fifty = report["fifty_fifty"]
        charts = report["charts"]
        src = self._selected_source()

        self._render_summary(summary)
        self._render_pity(summary, src)
        self._render_fifty(fifty, src)

        self.heatmap.set_data(report.get("activity_by_day"))
        self.chart_banner.set_data(charts.get("by_banner"))
        self.chart_rarity.set_data(charts.get("by_rarity"))
        luck = charts.get("worst_pulls_v6") or WORST_PULLS_V6
        self.chart_dolls.set_data(charts.get("doll_campaigns"), luck_max=luck)
        self.chart_weapons.set_data(charts.get("weapon_campaigns"), luck_max=luck)

        self._render_table(report.get("campaigns") or [])
