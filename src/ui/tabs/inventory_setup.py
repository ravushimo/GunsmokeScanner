"""Growth Data region calibration (Inventory mode)."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import pyautogui

from src.constants import INVENTORY_GROWTH_REGIONS, THEME
from src.core.growth_scanner import GrowthScanner, has_orange_lock
from src.core.layouts import layout_from_inventory_growth, save_layout
from src.core.scanner import safe_grab
from src.ui.region_helpers import bind_entry_arrow_nudge
from src.ui.styles import create_button

REGION_LABELS = {
    "grid": "Item Grid",
    "type": "Type line",
    "perks": "Perks block",
    "lock_btn": "Detail lock button",
    "own_count": "Own count",
}


class InventorySetupTab(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        config_manager,
        overlay_manager,
        fonts,
        ocr_processor=None,
        on_apply_layout=None,
    ):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.config_manager = config_manager
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.ocr_processor = ocr_processor
        self.on_apply_layout = on_apply_layout
        self.region_var = tk.StringVar(value="grid")
        self.setup_ui()

    def activate(self):
        self.overlay_manager.on_update_callback = self.on_overlay_update
        self.overlay_manager.set_profile("inventory")
        self.overlay_manager.set_move_lock("none")
        self._sync_overlay_selection()
        self.update_region_info()

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
            text="Growth Data Regions (3440×1440)",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
        ).pack(anchor=tk.W, padx=15, pady=(15, 5))
        ctk.CTkLabel(
            head,
            text=(
                "1. Open Growth Data → Storeroom · Show Overlay\n"
                "2. Drag Grid / Type / Perks / Lock / Own regions\n"
                "   Identity (name/icon) is not stored — only type + perks.\n"
                "3. Set cell lock inset (orange padlock on tile, left side)\n"
                "4. OCR Peek / Lock Peek · Save Config · F4 apply template"
            ),
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=15, pady=(0, 15))

        body = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=16, pady=12)

        ctk.CTkLabel(
            left,
            text="Region",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
        ).pack(anchor=tk.W, pady=(0, 6))
        for key in INVENTORY_GROWTH_REGIONS:
            ctk.CTkRadioButton(
                left,
                text=REGION_LABELS[key],
                variable=self.region_var,
                value=key,
                font=self.fonts.body,
                text_color=THEME["text_primary"],
                command=self.on_selection_change,
            ).pack(anchor=tk.W, pady=2)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=12)

        coords = ctk.CTkFrame(right, fg_color="transparent")
        coords.pack(anchor=tk.W)
        self.entries = {}
        for i, (label, field) in enumerate(
            (("X", "x"), ("Y", "y"), ("W", "w"), ("H", "h"))
        ):
            ctk.CTkLabel(
                coords,
                text=label,
                font=self.fonts.caption,
                text_color=THEME["text_muted"],
            ).grid(row=0, column=i, padx=4)
            e = ctk.CTkEntry(coords, width=70, font=self.fonts.body)
            e.grid(row=1, column=i, padx=4, pady=4)
            bind_entry_arrow_nudge(e, field, self.nudge_field)
            self.entries[field] = e

        inset = ctk.CTkFrame(right, fg_color="transparent")
        inset.pack(anchor=tk.W, pady=(12, 0))
        ctk.CTkLabel(
            inset,
            text="Cell lock inset (relative px inside each tile)",
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
        ).pack(anchor=tk.W)
        inset_row = ctk.CTkFrame(inset, fg_color="transparent")
        inset_row.pack(anchor=tk.W, pady=4)
        self.inset_entries = {}
        for i, lab in enumerate(("X", "Y", "W", "H")):
            ctk.CTkLabel(
                inset_row, text=lab, font=self.fonts.caption, text_color=THEME["text_muted"]
            ).grid(row=0, column=i, padx=4)
            e = ctk.CTkEntry(inset_row, width=60, font=self.fonts.body)
            e.grid(row=1, column=i, padx=4)
            self.inset_entries[lab.lower()] = e

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(anchor=tk.W, pady=(16, 0))
        create_button(
            btn_row, "Apply coords", self.apply_coords, variant="secondary", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row, "OCR Peek", self.ocr_peek, variant="secondary", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row, "Lock Peek", self.lock_peek, variant="secondary", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row, "Save Config", self.save_config, variant="primary", font=self.fonts.ui
        ).pack(side=tk.LEFT, padx=4)

        btn_row2 = ctk.CTkFrame(right, fg_color="transparent")
        btn_row2.pack(anchor=tk.W, pady=(8, 0))
        create_button(
            btn_row2,
            "Save as layout template",
            self.save_layout_template,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        if self.on_apply_layout:
            create_button(
                btn_row2,
                "Apply F4 layout",
                self.on_apply_layout,
                variant="ghost",
                font=self.fonts.ui,
            ).pack(side=tk.LEFT, padx=4)

        self.preview = ctk.CTkTextbox(
            right, height=160, font=self.fonts.caption, fg_color=THEME["bg_raised"]
        )
        self.preview.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.update_region_info()

    def _growth(self) -> dict:
        return self.config_manager.get_inventory_growth()

    def on_selection_change(self):
        self.update_region_info()
        self._sync_overlay_selection()

    def _sync_overlay_selection(self):
        self.overlay_manager.set_selected(None, self.region_var.get())

    def on_overlay_update(self, row_idx, col_name, select=False):
        if select and col_name in INVENTORY_GROWTH_REGIONS:
            self.region_var.set(col_name)
        self.update_region_info()

    def update_region_info(self):
        g = self._growth()
        key = self.region_var.get()
        bbox = g.get(key) or [0, 0, 0, 0]
        for field, val in zip(("x", "y", "w", "h"), bbox):
            e = self.entries[field]
            e.delete(0, tk.END)
            e.insert(0, str(int(val)))
        inset = g.get("cell_lock_inset") or [10, 48, 40, 40]
        for field, val in zip(("x", "y", "w", "h"), inset):
            e = self.inset_entries[field]
            e.delete(0, tk.END)
            e.insert(0, str(int(val)))

    def nudge_field(self, field: str, delta: int):
        e = self.entries.get(field)
        if not e:
            return
        try:
            val = int(e.get().strip())
        except ValueError:
            val = 0
        e.delete(0, tk.END)
        e.insert(0, str(val + delta))
        self.apply_coords()

    def apply_coords(self):
        g = self._growth()
        key = self.region_var.get()
        try:
            bbox = [int(self.entries[f].get()) for f in ("x", "y", "w", "h")]
            inset = [int(self.inset_entries[f].get()) for f in ("x", "y", "w", "h")]
        except ValueError:
            messagebox.showerror("Invalid", "Coordinates must be integers.")
            return
        g[key] = bbox
        g["cell_lock_inset"] = inset
        self.config_manager.save_config()
        if self.overlay_manager.active:
            self.overlay_manager.sync_geometries()
        self._log(f"Updated {key} = {bbox}; cell_lock_inset = {inset}")

    def save_config(self):
        self.apply_coords()
        messagebox.showinfo("Saved", "Inventory Growth config saved.")

    def save_layout_template(self):
        self.apply_coords()
        w, h = pyautogui.size()
        layout = layout_from_inventory_growth(self._growth(), w, h)
        path = save_layout(layout)
        messagebox.showinfo("Layout saved", f"Wrote {path}")

    def _log(self, text: str):
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)

    def ocr_peek(self):
        if not self.ocr_processor:
            return

        def _run():
            key = self.region_var.get()
            g = self._growth()
            bbox = g.get(key)
            img = safe_grab(bbox) if bbox else None
            text = (
                self.ocr_processor.extract_text(img, config=self.config_manager.config)
                if img is not None
                else "(no image)"
            )
            if key in ("type", "perks"):
                from src.core.growth_names import parse_perks_from_text, parse_type_line

                if key == "type":
                    parsed = parse_type_line(text)
                    msg = f"OCR [type]:\n{text}\n\nparsed: {parsed!r}"
                else:
                    perks = parse_perks_from_text(text)
                    lines = [
                        f"  {p.get('name')} Lv.{p.get('level')}" for p in perks
                    ]
                    msg = f"OCR [perks]:\n{text}\n\nparsed ({len(perks)}):\n" + (
                        "\n".join(lines) if lines else "  (none)"
                    )
                self.after(0, lambda: self._log(msg))
                return
            self.after(0, lambda: self._log(f"OCR [{key}]:\n{text}"))

        threading.Thread(target=_run, daemon=True).start()

    def lock_peek(self):
        def _run():
            scanner = GrowthScanner(self.config_manager, self.ocr_processor)
            detail = scanner.is_detail_locked()
            # Sample R1C1 grid lock
            grid_locked = scanner.is_cell_locked(0, 0)
            g = self._growth()
            img = safe_grab(g.get("lock_btn"))
            px = has_orange_lock(img)
            msg = (
                f"Detail lock_btn orange={detail} (sample={px})\n"
                f"Grid R1C1 lock badge={grid_locked}\n"
                f"Select an unlocked vs locked core and re-check."
            )
            self.after(0, lambda: self._log(msg))

        threading.Thread(target=_run, daemon=True).start()
