"""Local Growth Data inventory browser."""

from __future__ import annotations

import csv
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk

from src.constants import THEME, class_tag, configure_class_tags
from src.data.inventory_db import InventoryDB
from src.ui.styles import create_button

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


class InventoryListTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: InventoryDB = None, on_change=None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or InventoryDB()
        self.on_change = on_change
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        head = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        head.pack(fill=tk.X, padx=20, pady=20)
        ctk.CTkLabel(
            head,
            text="Scanned Growth Data",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
        ).pack(anchor=tk.W, padx=15, pady=(12, 4))
        self.summary = ctk.CTkLabel(
            head,
            text="",
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
        )
        self.summary.pack(anchor=tk.W, padx=15, pady=(0, 8))

        filters = ctk.CTkFrame(head, fg_color="transparent")
        filters.pack(fill=tk.X, padx=15, pady=(0, 12))
        ctk.CTkLabel(
            filters, text="Type:", font=self.fonts.body, text_color=THEME["text_primary"]
        ).pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filters,
            variable=self.type_var,
            values=["All", "Bulwark", "Sentinel", "Vanguard", "Support"],
            command=lambda _v: self.refresh(),
            font=self.fonts.body,
        ).pack(side=tk.LEFT, padx=8)
        create_button(
            filters, "Refresh", self.refresh, variant="ghost", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            filters,
            "Export CSV",
            self.export_csv,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            filters,
            "Clear all…",
            self.clear_all,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)

        table = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        table.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))
        cols = ("id", "Type", "Perk1", "Perk2", "Perk3", "Qty")
        self.tree = ttk.Treeview(
            table, columns=cols, show="headings", height=18, style="Custom.Treeview"
        )
        widths = {
            "id": 40,
            "Type": 100,
            "Perk1": 160,
            "Perk2": 160,
            "Perk3": 160,
            "Qty": 50,
        }
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor=tk.CENTER if c in ("id", "Qty") else tk.W)
        configure_class_tags(self.tree)
        sb = ctk.CTkScrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        edit = ctk.CTkFrame(self, fg_color="transparent")
        edit.pack(fill=tk.X, padx=20, pady=(0, 20))
        ctk.CTkLabel(
            edit, text="Qty:", font=self.fonts.body, text_color=THEME["text_primary"]
        ).pack(side=tk.LEFT)
        self.qty_entry = ctk.CTkEntry(edit, width=60, font=self.fonts.body)
        self.qty_entry.pack(side=tk.LEFT, padx=6)
        create_button(
            edit, "Set quantity", self.set_quantity, variant="secondary", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            edit, "Delete row", self.delete_selected, variant="ghost", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        t = self.type_var.get()
        cores = self.db.list_cores(core_type=None if t == "All" else t)
        for c in cores:
            p1 = f"{c['perk1_name']} {c['perk1_level']}"
            p2 = f"{c['perk2_name']} {c['perk2_level']}"
            p3 = (
                f"{c['perk3_name']} {c['perk3_level']}"
                if c.get("perk3_name")
                else ""
            )
            tag = class_tag(c.get("type"))
            self.tree.insert(
                "",
                tk.END,
                values=(
                    c["id"],
                    c["type"],
                    p1,
                    p2,
                    p3,
                    c["quantity"],
                ),
                tags=(tag,) if tag else (),
            )
        self.summary.configure(
            text=(
                f"{len(cores)} unique · {self.db.total_quantity()} total copies "
                f"(filter: {t})"
            )
        )

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0], "values")[0])

    def set_quantity(self):
        core_id = self._selected_id()
        if core_id is None:
            messagebox.showinfo("Select", "Select a row first.")
            return
        try:
            qty = int(self.qty_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid", "Quantity must be an integer.")
            return
        self.db.update_quantity(core_id, qty)
        self.refresh()
        if self.on_change:
            self.on_change()

    def delete_selected(self):
        core_id = self._selected_id()
        if core_id is None:
            return
        if not messagebox.askyesno("Delete", f"Delete core id {core_id}?"):
            return
        self.db.delete_core(core_id)
        self.refresh()
        if self.on_change:
            self.on_change()

    def export_csv(self):
        t = self.type_var.get()
        cores = self.db.list_cores(core_type=None if t == "All" else t)
        if not cores:
            messagebox.showinfo("Export", "No cores to export for the current filter.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            title="Export Growth Data CSV",
            defaultextension=".csv",
            initialfile=f"growth_cores_{stamp}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
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
            messagebox.showerror("Export failed", str(e))
            return
        messagebox.showinfo(
            "Export",
            f"Wrote {len(cores)} row(s) to:\n{path}",
        )

    def clear_all(self):
        if not messagebox.askyesno(
            "Clear inventory",
            "Delete ALL scanned Growth Data from local DB?\n"
            "Also unlock all cores in-game before a full rescan.",
        ):
            return
        self.db.clear_all()
        self.refresh()
        if self.on_change:
            self.on_change()
