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

def _blend(hex_a: str, hex_b: str, t: float) -> str:
    def _rgb(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    ar, ag, ab = _rgb(hex_a)
    br, bg, bb = _rgb(hex_b)
    return (
        f"#{int(round(ar + (br - ar) * t)):02x}"
        f"{int(round(ag + (bg - ag) * t)):02x}"
        f"{int(round(ab + (bb - ab) * t)):02x}"
    )


class GachaHistoryTab(ctk.CTkFrame):
    # Cap rows drawn in the tree — pity still uses full timeline
    DISPLAY_LIMIT = 800

    def __init__(self, parent, fonts, db: GachaDB = None, on_change=None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_change = on_change
        self._cached_timeline = None
        self._cache_count = -1
        self.setup_ui()
        self.refresh()

    def _filter_group(self, parent, label: str) -> ctk.CTkFrame:
        group = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(
            group,
            text=label,
            font=self.fonts.ui,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)
        return group

    def setup_ui(self):
        filter_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=_blend(THEME["border"], THEME["element_freeze"], 0.35),
        )
        filter_frame.pack(fill=tk.X, padx=12, pady=(8, 6))

        # Two packed rows so controls stay visible at default (~720–860) width
        row_filters = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row_filters.pack(fill=tk.X, padx=10, pady=(8, 4))
        row_actions = ctk.CTkFrame(filter_frame, fg_color="transparent")
        row_actions.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Source
        g_source = self._filter_group(row_filters, "Source:")
        self.source_var = tk.StringVar(value="All")
        self.source_menu = ctk.CTkOptionMenu(
            g_source,
            variable=self.source_var,
            values=["All"],
            width=148,
            height=28,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        )
        self.source_menu.pack(side=tk.LEFT, padx=(6, 0))
        g_source.pack(side=tk.LEFT, padx=(0, 10))

        # Type
        g_type = self._filter_group(row_filters, "Type:")
        self.type_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            g_type,
            variable=self.type_var,
            values=["All", "Doll", "Weapons"],
            width=90,
            height=28,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        ).pack(side=tk.LEFT, padx=(6, 0))
        g_type.pack(side=tk.LEFT, padx=(0, 10))

        # Rarity
        g_rarity = self._filter_group(row_filters, "Rarity:")
        self.rarity_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            g_rarity,
            variable=self.rarity_var,
            values=["All", "Elite", "Standard", "Retired"],
            width=96,
            height=28,
            font=self.fonts.body,
            command=lambda _v: self.refresh(),
        ).pack(side=tk.LEFT, padx=(6, 0))
        g_rarity.pack(side=tk.LEFT, padx=(0, 4))

        # Dates (label is the placeholder) + compact action buttons
        self.from_picker = DatePickerField(
            row_actions,
            self.fonts,
            width=100,
            placeholder="From date",
            on_change=self.refresh,
        )
        self.from_picker.pack(side=tk.LEFT, padx=(0, 6))

        self.to_picker = DatePickerField(
            row_actions,
            self.fonts,
            width=100,
            placeholder="To date",
            on_change=self.refresh,
        )
        self.to_picker.pack(side=tk.LEFT, padx=(0, 8))

        # Fixed compact widths — CTk default is 140 and crowds out Clear History
        create_button(
            row_actions,
            "Refresh",
            self.refresh,
            variant="secondary",
            font=self.fonts.ui,
            width=72,
            height=28,
            fg_color=THEME["class_support"],
            hover_color=_blend(THEME["class_support"], "#ffffff", 0.12),
            text_color="#ffffff",
        ).pack(side=tk.LEFT, padx=(0, 4))
        create_button(
            row_actions,
            "Fix names",
            self.fix_names,
            variant="secondary",
            font=self.fonts.ui,
            width=84,
            height=28,
            fg_color=THEME["class_bulwark"],
            hover_color=_blend(THEME["class_bulwark"], "#ffffff", 0.12),
            text_color="#ffffff",
        ).pack(side=tk.LEFT, padx=(0, 4))
        create_button(
            row_actions,
            "Clear History",
            self.clear_db,
            variant="ghost",
            font=self.fonts.ui,
            width=104,
            height=28,
            border_color=_blend(THEME["border"], THEME["element_omni"], 0.55),
            text_color=THEME["element_omni"],
        ).pack(side=tk.LEFT)

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

        self.tree.tag_configure("elite", foreground=THEME["element_electric"])
        self.tree.tag_configure("standard", foreground=THEME["class_vanguard"])
        self.tree.tag_configure("retired", foreground=THEME["element_physical"])
        self.tree.tag_configure("gold", foreground=THEME["element_electric"])
        self.tree.tag_configure("purple", foreground=THEME["class_vanguard"])
        self.tree.tag_configure("common", foreground=THEME["element_physical"])
        self.tree.tag_configure("pity_high", foreground=THEME["element_omni"])

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
            text_color=THEME["element_freeze"],
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
            text_color=THEME["element_burn"],
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
            cd = summary.get("pity_custom_doll", 0)
            cw = summary.get("pity_custom_weapon", 0)
            st = summary.get("pity_standard", 0)
            pity_txt = (
                f"Current pity — Premium Doll {doll_p}/{hard}  ·  "
                f"Premium Weapon {weap_p}/{hard}  ·  "
                f"Custom Dolls {cd}/{hard}  ·  "
                f"Custom Weapons {cw}/{hard}  ·  "
                f"Standard {st}/{hard}"
            )
        self.stats_pity.configure(text=pity_txt + avg_txt)

    def fix_names(self):
        from src.core.gacha_names import propose_name_fixes

        proposals = propose_name_fixes(self.db.distinct_item_name_types())
        if not proposals:
            messagebox.showinfo(
                "Fix names",
                "No OCR name mismatches found against the known catalog.",
            )
            return
        self._open_fix_names_dialog(proposals)

    def _open_fix_names_dialog(self, proposals):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Fix item names")
        dlg.geometry("560x420")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        ctk.CTkLabel(
            dlg,
            text="Select corrections to apply (matched by Type so dolls/weapons stay separate):",
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(12, 6))

        scroll = ctk.CTkScrollableFrame(dlg, fg_color=THEME["bg_canvas"])
        scroll.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # key = (raw, item_type) so Lewis Doll and Lewis Gun Weapon can both appear
        vars_by_key = {}
        for p in proposals:
            itype = p.get("item_type") or ""
            var = tk.BooleanVar(value=True)
            vars_by_key[(p["raw"], itype)] = (var, p["fixed"], itype)
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill=tk.X, pady=2)
            ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=28,
            ).pack(side=tk.LEFT)
            type_tag = f"[{itype}] " if itype else ""
            ctk.CTkLabel(
                row,
                text=f'{type_tag}{p["raw"]}  →  {p["fixed"]}',
                font=self.fonts.body,
                text_color=THEME["text_strong"],
                fg_color="transparent",
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=12, pady=12)

        def select_all(value: bool):
            for var, _fixed, _itype in vars_by_key.values():
                var.set(value)

        create_button(
            btn_row,
            "Select all",
            lambda: select_all(True),
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=2)
        create_button(
            btn_row,
            "Select none",
            lambda: select_all(False),
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=2)

        def apply():
            pairs = [
                (raw, fixed, itype)
                for (raw, _t), (var, fixed, itype) in vars_by_key.items()
                if var.get()
            ]
            if not pairs:
                dlg.destroy()
                return
            n = self.db.apply_name_fixes(pairs)
            dlg.destroy()
            messagebox.showinfo(
                "Fix names",
                f"Updated {n} pull row(s) across {len(pairs)} name(s).",
            )
            self.invalidate_cache()
            self.refresh()
            if self.on_change:
                self.on_change()

        create_button(
            btn_row,
            "Apply selected",
            apply,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.RIGHT, padx=2)
        create_button(
            btn_row,
            "Cancel",
            dlg.destroy,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.RIGHT, padx=2)

    def refresh(self):
        source = self.source_var.get()
        item_type = self.type_var.get()
        rarity = self.rarity_var.get()
        date_from = self.from_picker.get() or None
        date_to = self.to_picker.get() or None
        if date_to and len(date_to) == 10:
            date_to = date_to + " 23:59:59"

        # Reload timeline only when DB size changes or date filter changes
        count = self.db.count_pulls()
        cache_key = (count, date_from, date_to)
        if self._cached_timeline is None or self._cache_count != cache_key:
            self._cached_timeline = self.db.list_all_oldest_first(
                date_from=date_from,
                date_to=date_to,
            )
            self._cache_count = cache_key

        sources = ["All"] + sorted(
            {p.get("purchase_source") or "" for p in self._cached_timeline if p.get("purchase_source")}
        )
        current = self.source_var.get()
        self.source_menu.configure(values=sources)
        if current not in sources:
            self.source_var.set("All")
            source = "All"

        display, summary = build_history(
            self._cached_timeline,
            purchase_source=None if source == "All" else source,
            item_type=None if item_type == "All" else item_type,
            rarity=None if rarity == "All" else rarity,
        )

        total_shown = len(display)
        truncated = total_shown > self.DISPLAY_LIMIT
        rows = display[: self.DISPLAY_LIMIT]

        self.tree.delete(*self.tree.get_children())
        inserts = []
        for p in rows:
            rarity_v = p.get("rarity") or "retired"
            pity = p.get("pity")
            pity_str = "" if pity is None else str(pity)
            tags = [rarity_v]
            if pity is not None and pity >= ELITE_HARD_PITY - 10:
                tags.append("pity_high")
            inserts.append(
                (
                    (
                        p.get("pull_index", ""),
                        pity_str,
                        p["purchase_time"],
                        p.get("banner") or p["purchase_source"],
                        p["item_type"],
                        p["item_name"],
                        rarity_v,
                    ),
                    tuple(tags),
                )
            )
        for values, tags in inserts:
            self.tree.insert("", tk.END, values=values, tags=tags)

        self._format_stats(summary, total_shown)
        if truncated:
            self.stats_quality.configure(
                text=self.stats_quality.cget("text")
                + f"  ·  Table shows newest {self.DISPLAY_LIMIT} of {total_shown}"
            )

    def invalidate_cache(self):
        self._cached_timeline = None
        self._cache_count = -1

    def clear_db(self):
        if not messagebox.askyesno(
            "Clear History",
            "This will permanently delete ALL saved gacha pulls from the local database.\n\n"
            "This data cannot be recovered. Continue?",
            icon="warning",
        ):
            return
        self.db.clear_all()
        self.invalidate_cache()
        self.refresh()
        if self.on_change:
            self.on_change()

