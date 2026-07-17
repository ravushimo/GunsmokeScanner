"""Gacha Stats — campaigns, 50/50, and charts."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from src.constants import THEME
from src.core.gacha_stats import ELITE_HARD_PITY, WORST_PULLS_V6, build_stats_report
from src.data.gacha_db import GachaDB
from src.ui.components.charts import ChartFrame
from src.ui.styles import create_button


class GachaStatsTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: GachaDB = None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        toolbar = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        toolbar.pack(fill=tk.X, padx=8, pady=(6, 4))

        row = ctk.CTkFrame(toolbar, fg_color="transparent")
        row.pack(fill=tk.X, padx=8, pady=6)

        ctk.CTkLabel(
            row,
            text="Campaigns: first-copy pity → last copy (V0→V6). "
            "Standard-pool Elites = 50/50 losses on premium banners.",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="w",
            justify=tk.LEFT,
            wraplength=640,
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

        self.summary_lbl = ctk.CTkLabel(
            self.scroll,
            text="",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
            justify=tk.LEFT,
        )
        self.summary_lbl.pack(fill=tk.X, padx=2, pady=(0, 1))

        self.fifty_lbl = ctk.CTkLabel(
            self.scroll,
            text="",
            font=self.fonts.body_medium,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            anchor="w",
            justify=tk.LEFT,
        )
        self.fifty_lbl.pack(fill=tk.X, padx=2, pady=(0, 4))

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
            corner_radius=6,
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

        self.tree.tag_configure("complete", foreground=THEME["success"])
        self.tree.tag_configure("progress", foreground=THEME["accent_amber"])

    def refresh(self):
        self.db.normalize_purchase_sources()
        timeline = self.db.list_all_oldest_first()
        report = build_stats_report(timeline)
        summary = report["summary"]
        fifty = report["fifty_fifty"]
        charts = report["charts"]
        hard = summary.get("hard_pity", ELITE_HARD_PITY)

        self.summary_lbl.configure(
            text=(
                f"Total pulls {summary.get('total', 0)}  ·  "
                f"Elite dolls {summary.get('elite_dolls', 0)}  ·  "
                f"Elite weapons {summary.get('elite_weapons', 0)}  ·  "
                f"Pity — Premium Doll {summary.get('pity_doll', 0)}/{hard}  ·  "
                f"Premium Weapon {summary.get('pity_weapon', 0)}/{hard}"
            )
        )

        parts = []
        for label, stats in (fifty.get("by_banner") or {}).items():
            wr = stats.get("win_rate")
            wr_txt = f"{wr}%" if wr is not None else "—"
            parts.append(
                f"{label}: {stats.get('wins', 0)}W / {stats.get('losses', 0)}L "
                f"({wr_txt} of 50/50) · {stats.get('guaranteed', 0)} guaranteed"
            )
        g_doll = "YES" if fifty.get("guarantee_premium_doll") else "no"
        g_weap = "YES" if fifty.get("guarantee_premium_weapon") else "no"
        parts.append(f"Next Elite guaranteed — Doll: {g_doll}  ·  Weapon: {g_weap}")
        self.fifty_lbl.configure(text="\n".join(parts))

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
