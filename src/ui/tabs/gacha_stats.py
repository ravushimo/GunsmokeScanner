"""Gacha Stats — campaigns, 50/50, heatmap, banner filter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Sequence, Tuple

import customtkinter as ctk

from src.constants import THEME
from src.core.gacha_stats import (
    BANNER_LABELS,
    ELITE_HARD_PITY,
    WORST_PULLS_V6,
    build_stats_report,
)
from src.data.gacha_db import GachaDB
from src.ui.components.charts import ActivityHeatmap, ChartFrame
from src.ui.styles import create_button

BANNER_FILTER_ORDER = (
    ("All", None),
    ("Premium Doll", "Targeted Procurement"),
    ("Premium Weapon", "Military Upgrade"),
    ("Custom Dolls", "Custom Procurement - Dolls"),
    ("Custom Weapons", "Custom Procurement - Weapons"),
    ("Standard", "Standard Procurement"),
)

# Banner identity — GFL2 class colors (+ physical for Standard)
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

# 50/50 outcomes — Support / Omni / Electric (DESIGN class + type)
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


def _hex_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(hex_a: str, hex_b: str, t: float) -> str:
    """Blend two #rrggbb colors; t=0 → a, t=1 → b."""
    ar, ag, ab = _hex_rgb(hex_a)
    br, bg, bb = _hex_rgb(hex_b)
    r = int(round(ar + (br - ar) * t))
    g = int(round(ag + (bg - ag) * t))
    b = int(round(ab + (bb - ab) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def _soft_surface(accent: str, amount: float = 0.22) -> str:
    """Tint bg_raised toward an accent for subtle chip / cell fills."""
    return _blend(THEME["bg_raised"], accent, amount)


def _clear(frame: ctk.CTkFrame) -> None:
    for child in frame.winfo_children():
        child.destroy()


class GachaStatsTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: GachaDB = None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self._banner_var = tk.StringVar(value="All")
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        toolbar = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        toolbar.pack(fill=tk.X, padx=8, pady=(6, 4))

        row = ctk.CTkFrame(toolbar, fg_color="transparent")
        row.pack(fill=tk.X, padx=8, pady=6)

        ctk.CTkLabel(
            row,
            text="Banner:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)

        self.banner_menu = ctk.CTkOptionMenu(
            row,
            variable=self._banner_var,
            values=[label for label, _ in BANNER_FILTER_ORDER],
            width=160,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        )
        self.banner_menu.pack(side=tk.LEFT, padx=(6, 16))

        ctk.CTkLabel(
            row,
            text="Filter applies to the whole Stats page.",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        create_button(
            row,
            text="Refresh",
            variant="secondary",
            font=self.fonts.ui,
            command=self.refresh,
            width=90,
            height=28,
        ).pack(side=tk.RIGHT, padx=(10, 0))

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=0,
            border_width=0,
        )
        self.scroll.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # --- Overview metrics (no cards) ---
        self.summary_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.summary_row.pack(fill=tk.X, padx=2, pady=(4, 6))

        # --- Current pity (section block with centered header) ---
        self.pity_block = ctk.CTkFrame(
            self.scroll,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        self.pity_block.pack(fill=tk.X, padx=2, pady=(4, 4))
        ctk.CTkLabel(
            self.pity_block,
            text="Current pity",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=12, pady=(10, 4))
        self.pity_row = ctk.CTkFrame(self.pity_block, fg_color="transparent")
        self.pity_row.pack(fill=tk.X, padx=8, pady=(0, 8))

        # --- 50/50 (section block with centered header) ---
        self.fifty_block = ctk.CTkFrame(
            self.scroll,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        self.fifty_block.pack(fill=tk.X, padx=2, pady=(4, 4))
        ctk.CTkLabel(
            self.fifty_block,
            text="50/50 · Premium banners",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=12, pady=(10, 4))
        self.fifty_row = ctk.CTkFrame(self.fifty_block, fg_color="transparent")
        self.fifty_row.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.heatmap = ActivityHeatmap(self.scroll, fonts=self.fonts, height=186)
        self.heatmap.pack(fill=tk.X, padx=2, pady=(0, 4))

        charts_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        charts_row.pack(fill=tk.X, padx=0, pady=0)
        charts_row.grid_columnconfigure(0, weight=1)
        charts_row.grid_columnconfigure(1, weight=1)

        self.chart_banner = ChartFrame(
            charts_row, "Pulls by banner", kind="pie", height=180, fonts=self.fonts
        )
        self.chart_banner.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.chart_rarity = ChartFrame(
            charts_row, "Pulls by rarity", kind="pie", height=180, fonts=self.fonts
        )
        self.chart_rarity.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        charts_row2 = ctk.CTkFrame(self.scroll, fg_color="transparent")
        charts_row2.pack(fill=tk.X, padx=0, pady=0)
        charts_row2.grid_columnconfigure(0, weight=1)
        charts_row2.grid_columnconfigure(1, weight=1)

        self.chart_dolls = ChartFrame(
            charts_row2,
            "Pulls spent per premium doll",
            kind="campaign",
            height=240,
            fonts=self.fonts,
        )
        self.chart_dolls.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.chart_weapons = ChartFrame(
            charts_row2,
            "Pulls spent per premium weapon",
            kind="campaign",
            height=240,
            fonts=self.fonts,
        )
        self.chart_weapons.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        ctk.CTkLabel(
            self.scroll,
            text="Premium campaigns",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill=tk.X, padx=2, pady=(6, 2))

        table_wrap = ctk.CTkFrame(
            self.scroll,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        table_wrap.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 6))

        cols = (
            "name",
            "type",
            "banner",
            "copies",
            "potential",
            "pulls",
            "first_pity",
            "losses",
            "wins",
            "guaranteed",
            "status",
        )
        self.tree = ttk.Treeview(
            table_wrap,
            columns=cols,
            show="headings",
            style="Custom.Treeview",
            height=12,
        )
        headings = {
            "name": ("Name", 110),
            "type": ("Type", 70),
            "banner": ("Banner", 130),
            "copies": ("Copies", 60),
            "potential": ("Rank", 50),
            "pulls": ("Pulls", 60),
            "first_pity": ("1st pity", 70),
            "losses": ("L", 40),
            "wins": ("W", 40),
            "guaranteed": ("Guar.", 50),
            "status": ("Status", 90),
        }
        for key, (label, width) in headings.items():
            self.tree.heading(key, text=label)
            self.tree.column(
                key, width=width, anchor=tk.CENTER if key != "name" else tk.W
            )

        scroll_y = ctk.CTkScrollbar(table_wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)

        self.tree.tag_configure("complete", foreground=THEME["class_support"])
        self.tree.tag_configure("progress", foreground=THEME["element_electric"])

    def _selected_source(self):
        label = self._banner_var.get()
        for name, source in BANNER_FILTER_ORDER:
            if name == label:
                return source
        return None

    def _metric_chip(self, parent, label: str, value: str, *, accent: Optional[str] = None):
        """Plain centered metric — no card chrome; shares row width evenly."""
        # height=1: CTkFrame defaults to 200px — that was the empty band above/below
        chip = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        chip.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=12, pady=0)
        ctk.CTkLabel(
            chip,
            text=label.upper(),
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X)
        ctk.CTkLabel(
            chip,
            text=value,
            font=self.fonts.heading,
            text_color=accent or THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X)
        return chip

    def _pity_card(
        self,
        parent,
        title: str,
        current: int,
        hard: int,
        *,
        accent: str,
        column: int,
        columns: int,
    ):
        ratio = min(1.0, current / hard) if hard else 0.0
        # Banner accent → Electric → Burn as pity climbs
        if ratio < 0.55:
            bar = accent
        elif ratio < 0.85:
            bar = _blend(accent, THEME["element_electric"], (ratio - 0.55) / 0.30)
        else:
            bar = _blend(THEME["element_electric"], THEME["element_burn"], (ratio - 0.85) / 0.15)

        parent.grid_columnconfigure(column, weight=1, uniform="pity")
        card = ctk.CTkFrame(
            parent,
            fg_color=THEME["bg_raised"],
            corner_radius=0,
            border_width=1,
            border_color=_blend(THEME["border"], accent, 0.55),
        )
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0 if column == columns - 1 else 3), pady=0)

        ctk.CTkLabel(
            card,
            text=title,
            font=self.fonts.body_medium,
            text_color=accent,
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=6, pady=(5, 0))

        ctk.CTkLabel(
            card,
            text=f"{current} / {hard}",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=6, pady=(0, 3))

        track = ctk.CTkFrame(card, fg_color=THEME["bg_canvas"], height=5, corner_radius=0)
        track.pack(fill=tk.X, padx=8, pady=(0, 5))
        track.pack_propagate(False)
        if ratio > 0:
            fill = ctk.CTkFrame(track, fg_color=bar, height=5, corner_radius=0)
            fill.place(relx=0, rely=0, relwidth=max(0.04, ratio), relheight=1)

    def _seq_chip(self, parent, outcome: str):
        glyph, fg, bg = _OUTCOME_STYLE.get(
            outcome, ("?", THEME["text_muted"], THEME["bg_raised"])
        )
        chip = ctk.CTkLabel(
            parent,
            text=glyph,
            width=20,
            height=20,
            corner_radius=0,
            fg_color=bg,
            text_color=fg,
            font=self.fonts.ui,
        )
        chip.pack(side=tk.LEFT, padx=1, pady=0)
        return chip

    def _pack_sequence(self, parent: ctk.CTkFrame, outcomes: Sequence[str]) -> None:
        """Single row of newest chips, right-aligned so the latest is never clipped."""
        host = ctk.CTkFrame(parent, fg_color="transparent", height=24)
        host.pack(fill=tk.X, padx=8, pady=(0, 6))
        host.pack_propagate(False)

        all_outcomes = list(outcomes)
        # CTk chips are wider than nominal width=20 — keep a safety margin
        chip_span = 28
        ellipsis_w = 16

        def relayout(_event=None):
            if getattr(host, "_busy", False):
                return
            w = max(host.winfo_width(), 1)
            if w < 40:
                return
            prev = getattr(host, "_laid_w", 0)
            if abs(w - prev) < 2 and host.winfo_children():
                return
            host._busy = True
            try:
                host._laid_w = w
                for child in host.winfo_children():
                    child.destroy()

                if not all_outcomes:
                    ctk.CTkLabel(
                        host,
                        text="—",
                        font=self.fonts.body,
                        text_color=THEME["text_muted"],
                        fg_color="transparent",
                    ).place(relx=0.5, rely=0.5, anchor="center")
                    return

                # Drop oldest until newest row + optional "…" fits with margin
                avail = max(20, w - 6)
                shown = list(all_outcomes)
                truncated = False
                while shown:
                    need = len(shown) * chip_span
                    will_trunc = len(shown) < len(all_outcomes)
                    if will_trunc:
                        need += ellipsis_w
                    if need <= avail:
                        truncated = will_trunc
                        break
                    shown.pop(0)
                if not shown:
                    shown = [all_outcomes[-1]]
                    truncated = len(all_outcomes) > 1

                # Right-align so the newest chip is flush to the right (fully visible)
                row = ctk.CTkFrame(host, fg_color="transparent")
                row.place(relx=1.0, rely=0.5, anchor="e")
                if truncated:
                    ctk.CTkLabel(
                        row,
                        text="…",
                        font=self.fonts.body,
                        text_color=THEME["text_muted"],
                        fg_color="transparent",
                        width=14,
                    ).pack(side=tk.LEFT)
                for o in shown:
                    self._seq_chip(row, o)
            finally:
                host._busy = False

        host.bind("<Configure>", relayout)
        host.after_idle(relayout)

    def _fifty_card(
        self,
        parent,
        title: str,
        stats: Dict[str, Any],
        *,
        guarantee: bool,
        column: int,
        columns: int,
    ):
        accent = _BANNER_ACCENT.get(title, THEME["border"])
        parent.grid_columnconfigure(column, weight=1, uniform="fifty")
        card = ctk.CTkFrame(
            parent,
            fg_color=THEME["bg_raised"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["element_electric"] if guarantee else _blend(THEME["border"], accent, 0.55),
        )
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 3, 0 if column == columns - 1 else 3),
            pady=0,
        )

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill=tk.X, padx=8, pady=(6, 2))
        ctk.CTkLabel(
            head,
            text=title,
            font=self.fonts.body_medium,
            text_color=accent,
            fg_color="transparent",
            anchor="center",
        ).pack(side=tk.LEFT, expand=True)
        if guarantee:
            ctk.CTkLabel(
                head,
                text="NEXT GUARANTEED",
                font=self.fonts.body,
                text_color="#1a1a1a",
                fg_color=THEME["element_electric"],
                corner_radius=0,
                height=18,
            ).pack(side=tk.RIGHT)

        nums = ctk.CTkFrame(card, fg_color="transparent")
        nums.pack(fill=tk.X, padx=6, pady=(0, 2))
        for key, label, color in (
            ("wins", "WIN", THEME["class_support"]),
            ("losses", "LOSS", THEME["element_omni"]),
            ("guaranteed", "GUAR", THEME["element_electric"]),
        ):
            cell = ctk.CTkFrame(nums, fg_color=_soft_surface(color, 0.28), corner_radius=0)
            cell.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            ctk.CTkLabel(
                cell,
                text=str(stats.get(key, 0)),
                font=self.fonts.heading,
                text_color=color,
                fg_color="transparent",
                anchor="center",
            ).pack(fill=tk.X, pady=(4, 0))
            ctk.CTkLabel(
                cell,
                text=label,
                font=self.fonts.body,
                text_color=THEME["text_muted"],
                fg_color="transparent",
                anchor="center",
            ).pack(fill=tk.X, pady=(0, 4))

        wr = stats.get("win_rate")
        wr_txt = f"{wr}% win rate" if wr is not None else "No decided 50/50 yet"
        ctk.CTkLabel(
            card,
            text=wr_txt,
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=8, pady=(0, 1))

        streaks = (
            f"Longest W{stats.get('longest_win_streak', 0)} L{stats.get('longest_loss_streak', 0)}"
            f"  ·  Now W{stats.get('current_win_streak', 0)} L{stats.get('current_loss_streak', 0)}"
        )
        ctk.CTkLabel(
            card,
            text=streaks,
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=8, pady=(0, 2))

        ctk.CTkLabel(
            card,
            text="Sequence (newest shown)",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=8, pady=(0, 1))

        outcomes: Sequence[str] = list(stats.get("sequence") or [])
        self._pack_sequence(card, outcomes)

    def _render_summary(self, summary: Dict[str, Any]):
        _clear(self.summary_row)
        # Freeze / Vanguard / Burn — cool total, doll class, weapon heat
        self._metric_chip(
            self.summary_row,
            "Total pulls",
            str(summary.get("total", 0)),
            accent=THEME["element_freeze"],
        )
        self._metric_chip(
            self.summary_row,
            "Elite dolls",
            str(summary.get("elite_dolls", 0)),
            accent=THEME["class_vanguard"],
        )
        self._metric_chip(
            self.summary_row,
            "Elite weapons",
            str(summary.get("elite_weapons", 0)),
            accent=THEME["element_burn"],
        )

    def _render_pity(self, summary: Dict[str, Any], src: Optional[str]):
        _clear(self.pity_row)
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
        n = len(items)
        for i, (title, cur, accent) in enumerate(items):
            self._pity_card(
                self.pity_row, title, cur, hard, accent=accent, column=i, columns=n
            )

    def _render_fifty(self, fifty: Dict[str, Any], src: Optional[str]):
        _clear(self.fifty_row)
        by_banner = fifty.get("by_banner") or {}

        if src == "Standard Procurement":
            ctk.CTkLabel(
                self.fifty_row,
                text="Standard banner — pity only. No 50/50 win/loss tracking.",
                font=self.fonts.body,
                text_color=THEME["text_muted"],
                fg_color="transparent",
                anchor="center",
            ).pack(fill=tk.X, padx=10, pady=8)
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
            ctk.CTkLabel(
                self.fifty_row,
                text="No 50/50 outcomes in this filter.",
                font=self.fonts.body,
                text_color=THEME["text_muted"],
                fg_color="transparent",
                anchor="center",
            ).pack(fill=tk.X, padx=10, pady=8)
            return

        n = len(cards)
        for i, (label, stats, g) in enumerate(cards):
            self._fifty_card(
                self.fifty_row, label, stats, guarantee=g, column=i, columns=n
            )

    def refresh(self):
        self.db.normalize_purchase_sources()
        timeline = self.db.list_all_oldest_first()
        report = build_stats_report(
            timeline, purchase_source=self._selected_source()
        )
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

        for item in self.tree.get_children():
            self.tree.delete(item)

        for c in report.get("campaigns") or []:
            status = "V6 done" if c.get("complete") else "In progress"
            if c.get("extras"):
                status += f" +{c['extras']}"
            tag = "complete" if c.get("complete") else "progress"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    c.get("name", ""),
                    c.get("item_type", ""),
                    c.get("banner", ""),
                    c.get("copies", 0),
                    c.get("potential", ""),
                    c.get("pulls_spent", 0),
                    c.get("first_pity", ""),
                    c.get("fifty_losses", 0),
                    c.get("fifty_wins", 0),
                    c.get("fifty_guaranteed", 0),
                    status,
                ),
                tags=(tag,),
            )
