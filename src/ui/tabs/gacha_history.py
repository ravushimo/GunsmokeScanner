import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from src.constants import THEME
from src.core.gacha_stats import ELITE_HARD_PITY, build_history
from src.data.gacha_db import GachaDB
from src.ui.components.date_picker import DatePickerField
from src.ui.styles import create_button

BANNER_ORDER = (
    "Premium Doll",
    "Premium Weapon",
    "Custom Dolls",
    "Custom Weapons",
    "Standard",
)


class GachaHistoryTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: GachaDB = None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        filter_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        filter_frame.pack(fill=tk.X, padx=12, pady=(8, 6))

        row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row.pack(fill=tk.X, padx=10, pady=8)

        ctk.CTkLabel(
            row,
            text="Source:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)

        self.source_var = tk.StringVar(value="All")
        self.source_menu = ctk.CTkOptionMenu(
            row,
            variable=self.source_var,
            values=["All"],
            width=200,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        )
        self.source_menu.pack(side=tk.LEFT, padx=(6, 16))

        ctk.CTkLabel(
            row,
            text="Type:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)

        self.type_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            row,
            variable=self.type_var,
            values=["All", "Doll", "Weapons"],
            width=120,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        ).pack(side=tk.LEFT, padx=(6, 16))

        ctk.CTkLabel(
            row,
            text="Rarity:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)

        self.rarity_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            row,
            variable=self.rarity_var,
            values=["All", "Elite", "Standard", "Retired"],
            width=120,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        ).pack(side=tk.LEFT, padx=(6, 16))

        ctk.CTkLabel(
            row,
            text="From:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)
        self.from_picker = DatePickerField(
            row, self.fonts, width=120, on_change=self.refresh
        )
        self.from_picker.pack(side=tk.LEFT, padx=(6, 12))

        ctk.CTkLabel(
            row,
            text="To:",
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)
        self.to_picker = DatePickerField(
            row, self.fonts, width=120, on_change=self.refresh
        )
        self.to_picker.pack(side=tk.LEFT, padx=(6, 12))

        create_button(
            row,
            "Refresh",
            self.refresh,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)

        create_button(
            row,
            "Clear History",
            self.clear_db,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.RIGHT, padx=4)

        table_container = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        columns = ("#", "Pity", "Time", "Source", "Type", "Name", "Rarity")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=16,
            style="Custom.Treeview",
        )
        for col, width, anchor in (
            ("#", 50, tk.CENTER),
            ("Pity", 50, tk.CENTER),
            ("Time", 150, tk.W),
            ("Source", 150, tk.W),
            ("Type", 70, tk.CENTER),
            ("Name", 200, tk.W),
            ("Rarity", 70, tk.CENTER),
        ):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=anchor)

        scrollbar = ctk.CTkScrollbar(table_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=4)

        self.tree.tag_configure("elite", foreground="#C48A1A")
        self.tree.tag_configure("standard", foreground="#8A55C6")
        self.tree.tag_configure("retired", foreground=THEME["text_muted"])
        self.tree.tag_configure("gold", foreground="#C48A1A")
        self.tree.tag_configure("purple", foreground="#8A55C6")
        self.tree.tag_configure("common", foreground=THEME["text_muted"])
        self.tree.tag_configure("pity_high", foreground=THEME["danger"])

        # Bottom stats panel
        stats_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 16))

        ctk.CTkLabel(
            stats_frame,
            text="Stats",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, padx=15, pady=(12, 4))

        self.stats_quality = ctk.CTkLabel(
            stats_frame,
            text="",
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.stats_quality.pack(fill=tk.X, padx=15, pady=2)

        self.stats_banners = ctk.CTkLabel(
            stats_frame,
            text="",
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.stats_banners.pack(fill=tk.X, padx=15, pady=2)

        self.stats_pity = ctk.CTkLabel(
            stats_frame,
            text="",
            font=self.fonts.body_medium,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.stats_pity.pack(fill=tk.X, padx=15, pady=(2, 12))

    def _format_stats(self, summary: dict, shown: int) -> None:
        hard = summary.get("hard_pity", ELITE_HARD_PITY)
        self.stats_quality.configure(
            text=(
                f"Showing {shown}  ·  DB total {self.db.count_pulls()}  ·  "
                f"Elite dolls {summary.get('elite_dolls', 0)}  ·  "
                f"Elite weapons {summary.get('elite_weapons', 0)}  ·  "
                f"Standard {summary.get('standard', 0)}  ·  "
                f"Retired {summary.get('retired', 0)}"
            )
        )

        banners = summary.get("banners") or {}
        parts = []
        for name in BANNER_ORDER:
            if name in banners:
                parts.append(f"{name} {banners[name]}")
        for name, count in sorted(banners.items()):
            if name not in BANNER_ORDER:
                parts.append(f"{name} {count}")
        self.stats_banners.configure(
            text="Banners: " + ("  ·  ".join(parts) if parts else "—")
        )

        avg = summary.get("avg_elite_doll_gap")
        avg_txt = f"  ·  Avg pulls / Elite doll {avg}" if avg is not None else ""
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
            pity_txt = f"Current pity — {label} {cur}/{hard}"
        else:
            doll_p = summary.get("pity_doll", 0)
            weap_p = summary.get("pity_weapon", 0)
            pity_txt = (
                f"Current pity — Premium Doll {doll_p}/{hard}  ·  "
                f"Premium Weapon {weap_p}/{hard}"
            )
        self.stats_pity.configure(text=pity_txt + avg_txt)

    def refresh(self):
        # Collapse OCR variants (Custm/Custon/…) into canonical banner names
        self.db.normalize_purchase_sources()

        sources = ["All"] + self.db.distinct_sources()
        current = self.source_var.get()
        self.source_menu.configure(values=sources)
        if current not in sources:
            self.source_var.set("All")

        source = self.source_var.get()
        item_type = self.type_var.get()
        rarity = self.rarity_var.get()
        date_from = self.from_picker.get() or None
        date_to = self.to_picker.get() or None
        if date_to and len(date_to) == 10:
            date_to = date_to + " 23:59:59"

        timeline = self.db.list_all_oldest_first(
            date_from=date_from,
            date_to=date_to,
        )

        display, summary = build_history(
            timeline,
            purchase_source=None if source == "All" else source,
            item_type=None if item_type == "All" else item_type,
            rarity=None if rarity == "All" else rarity,
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in display:
            rarity = p.get("rarity") or "retired"
            pity = p.get("pity")
            pity_str = "" if pity is None else str(pity)
            tags = [rarity]
            if pity is not None and pity >= ELITE_HARD_PITY - 10:
                tags.append("pity_high")

            self.tree.insert(
                "",
                tk.END,
                values=(
                    p.get("pull_index", ""),
                    pity_str,
                    p["purchase_time"],
                    p.get("banner") or p["purchase_source"],
                    p["item_type"],
                    p["item_name"],
                    rarity,
                ),
                tags=tuple(tags),
            )

        self._format_stats(summary, len(display))

    def clear_db(self):
        if not messagebox.askyesno(
            "Clear History",
            "Delete ALL saved gacha pulls from the local database?\n"
            "This cannot be undone.",
        ):
            return
        self.db.clear_all()
        self.refresh()

