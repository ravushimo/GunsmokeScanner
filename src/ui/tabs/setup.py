import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import pyautogui

from src.constants import THEME
from src.core.layouts import layout_from_gunsmoke_rows, save_layout
from src.core.scanner import safe_grab
from src.ui.region_helpers import (
    FIELD_INDEX,
    bind_entry_arrow_nudge,
    distribute_ys_from_first_two,
    fill_field_across_rows,
)
from src.ui.styles import create_button


class SetupTab(ctk.CTkFrame):
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

        self.overlay_manager.on_update_callback = self.on_overlay_update

        self.setup_ui()

    def activate(self):
        """Called when this tab becomes active — switch overlay profile."""
        self.overlay_manager.on_update_callback = self.on_overlay_update
        self.overlay_manager.set_profile("gunsmoke")
        self.overlay_manager.set_move_lock(self.lock_var.get())
        self._sync_overlay_selection()

    def setup_ui(self):
        inst_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        inst_frame.pack(fill=tk.X, padx=20, pady=20)

        ctk.CTkLabel(
            inst_frame,
            text="Gunsmoke Region Setup",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, padx=15, pady=(15, 5))

        ctk.CTkLabel(
            inst_frame,
            text=(
                "1. Select row/column, enable Show Overlay\n"
                "2. Drag to move · edges/corner to resize\n"
                "3. Arrows in X/Y/W/H fields nudge that value (Shift = 10). "
                "With Overlay on and focus outside fields, arrows move the selection.\n"
                "4. Lock Column/Row · Save Config when done"
            ),
            font=self.fonts.body,
            text_color=THEME["text_primary"],
            fg_color="transparent",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=15, pady=(0, 15))

        ctrl_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        ctrl_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        center_container = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        center_container.pack()

        row_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        row_frame.pack(side=tk.LEFT, padx=24, pady=10)

        ctk.CTkLabel(
            row_frame,
            text="Select Row:",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, pady=5)

        self.row_var = tk.IntVar(value=0)
        for i in range(5):
            ctk.CTkRadioButton(
                row_frame,
                text=f"Row {i + 1}",
                variable=self.row_var,
                value=i,
                font=self.fonts.body,
                text_color=THEME["text_primary"],
                command=self.on_selection_change,
            ).pack(anchor=tk.W, pady=2)

        col_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        col_frame.pack(side=tk.LEFT, padx=24, pady=10)

        ctk.CTkLabel(
            col_frame,
            text="Select Column:",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, pady=5)

        self.col_var = tk.StringVar(value="nickname")
        for text, value in (
            ("Nickname", "nickname"),
            ("Single High", "single_high"),
            ("Total Score", "total_score"),
        ):
            ctk.CTkRadioButton(
                col_frame,
                text=text,
                variable=self.col_var,
                value=value,
                font=self.fonts.body,
                text_color=THEME["text_primary"],
                command=self.on_selection_change,
            ).pack(anchor=tk.W, pady=2)

        lock_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        lock_frame.pack(side=tk.LEFT, padx=24, pady=10)

        ctk.CTkLabel(
            lock_frame,
            text="Move Lock:",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(anchor=tk.W, pady=5)

        self.lock_var = tk.StringVar(value="none")
        for text, value in (
            ("Off", "none"),
            ("Whole Column", "column"),
            ("Whole Row", "row"),
        ):
            ctk.CTkRadioButton(
                lock_frame,
                text=text,
                variable=self.lock_var,
                value=value,
                font=self.fonts.body,
                text_color=THEME["text_primary"],
                command=self.on_lock_change,
            ).pack(anchor=tk.W, pady=2)

        info_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 15))

        ctk.CTkLabel(
            info_frame,
            text="Current Region (editable)",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(pady=(15, 10))

        fields_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        fields_frame.pack(pady=(10, 10))

        self.region_entries = {}
        self.fill_buttons = {}
        for label_text, field_name, row, col in (
            ("X:", "x", 0, 0),
            ("Y:", "y", 0, 1),
            ("Width:", "w", 1, 0),
            ("Height:", "h", 1, 1),
        ):
            field_container = ctk.CTkFrame(fields_frame, fg_color="transparent")
            field_container.grid(row=row, column=col, padx=15, pady=8)

            ctk.CTkLabel(
                field_container,
                text=label_text,
                text_color=THEME["text_muted"],
                fg_color="transparent",
                font=self.fonts.ui,
                width=60,
                anchor=tk.E,
            ).pack(side=tk.LEFT, padx=(0, 8))

            entry = ctk.CTkEntry(field_container, width=90, font=self.fonts.mono)
            entry.pack(side=tk.LEFT)
            entry.bind("<Return>", self.apply_manual_values)
            entry.bind("<FocusOut>", self.apply_manual_values)
            bind_entry_arrow_nudge(entry, field_name, self.nudge_field)
            self.region_entries[field_name] = entry

            fill_btn = create_button(
                field_container,
                "Fill others",
                lambda f=field_name: self.fill_field_others(f),
                variant="ghost",
                font=self.fonts.caption,
                width=90,
                height=28,
            )
            fill_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.fill_buttons[field_name] = fill_btn

        ctk.CTkLabel(
            info_frame,
            text=(
                "Fill others → same column all rows.  "
                "Distribute Y → space selected column from Row 1–2 only.  "
                "OCR Peek → one-region test (cheap)."
            ),
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(pady=(0, 4))

        self.peek_label = ctk.CTkLabel(
            info_frame,
            text="OCR Peek: —",
            font=self.fonts.mono,
            text_color=THEME["text_primary"],
            fg_color=THEME["bg_raised"],
            corner_radius=4,
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.peek_label.pack(fill=tk.X, padx=15, pady=(4, 8))

        action_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        action_row.pack(pady=(5, 15))

        create_button(
            action_row,
            "Apply Changes",
            self.apply_manual_values,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            action_row,
            "Distribute Y from Row 1–2",
            self.distribute_y,
            variant="featured",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            action_row,
            "OCR Peek",
            self.ocr_peek,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

        create_button(
            btn_frame,
            "Save Config",
            self.save_config,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_frame,
            "Save as layout template",
            self.save_layout_template,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_frame,
            "Apply layout (F4)",
            self.apply_layout_f4,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)

        self.update_region_info()

    def on_lock_change(self):
        self.overlay_manager.set_move_lock(self.lock_var.get())

    def _sync_overlay_selection(self):
        self.overlay_manager.set_selected(self.row_var.get(), self.col_var.get())

    def _refresh_overlays(self):
        if self.overlay_manager.active:
            self.overlay_manager.sync_geometries()

    def on_selection_change(self):
        self.update_region_info()
        self._sync_overlay_selection()

    def on_overlay_update(self, row_idx, col_name, select=False):
        if select and row_idx is not None:
            self.row_var.set(row_idx)
            self.col_var.set(col_name)

        if self.row_var.get() == row_idx and self.col_var.get() == col_name:
            self.update_region_info()

    def get_current_bbox(self):
        row = self.row_var.get()
        col = self.col_var.get()
        rows = self.config_manager.get("rows")
        return rows[row][col]

    def set_current_bbox(self, bbox):
        row = self.row_var.get()
        col = self.col_var.get()
        rows = self.config_manager.get("rows")
        rows[row][col] = bbox
        self.update_region_info()

    def update_region_info(self):
        bbox = self.get_current_bbox()
        for idx, key in enumerate(("x", "y", "w", "h")):
            self.region_entries[key].delete(0, tk.END)
            self.region_entries[key].insert(0, str(bbox[idx]))

    def apply_manual_values(self, _event=None):
        try:
            x = int(self.region_entries["x"].get())
            y = int(self.region_entries["y"].get())
            w = int(self.region_entries["w"].get())
            h = int(self.region_entries["h"].get())
            self.set_current_bbox([x, y, w, h])
            self._refresh_overlays()
        except ValueError:
            pass

    def nudge_field(self, field: str, delta: int):
        """Adjust one bbox field from arrow keys while an entry is focused."""
        self._sync_overlay_selection()
        if field in ("x", "y") and self.overlay_manager.active:
            dx = delta if field == "x" else 0
            dy = delta if field == "y" else 0
            if self.overlay_manager.nudge_selected(dx, dy):
                self.update_region_info()
                return

        try:
            value = int(self.region_entries[field].get())
        except ValueError:
            value = int(self.get_current_bbox()[FIELD_INDEX[field]])
        new_val = value + delta
        if field == "w":
            new_val = max(16, new_val)
        elif field == "h":
            new_val = max(12, new_val)
        bbox = list(self.get_current_bbox())
        bbox[FIELD_INDEX[field]] = new_val
        self.set_current_bbox(bbox)
        self._refresh_overlays()

    def fill_field_others(self, field: str):
        try:
            value = int(self.region_entries[field].get())
        except ValueError:
            return
        self.apply_manual_values()
        col = self.col_var.get()
        rows = self.config_manager.get("rows", [])
        fill_field_across_rows(rows, col, field, value)
        self.update_region_info()
        self._refresh_overlays()

    def distribute_y(self):
        self.apply_manual_values()
        col = self.col_var.get()
        rows = self.config_manager.get("rows", [])
        gap = distribute_ys_from_first_two(rows, col, sync_all_columns=False)
        if gap is None:
            messagebox.showwarning(
                "Distribute Y",
                "Align Row 1 and Row 2 first (different Y values required).",
            )
            return
        self.update_region_info()
        self._refresh_overlays()

    def ocr_peek(self):
        if self.ocr_processor is None:
            messagebox.showwarning("OCR Peek", "OCR is not available.")
            return
        self.apply_manual_values()
        self.peek_label.configure(text="OCR Peek: reading…")
        was_active = self.overlay_manager.active
        if was_active:
            self.overlay_manager.hide()

        def worker():
            try:
                img = safe_grab(self.get_current_bbox())
                text = self.ocr_processor.extract_text(
                    img, config=self.config_manager.config
                )
                display = text if text else "(empty)"
            except Exception as e:
                display = f"Error: {e}"
            self.after(0, lambda: self._on_peek_done(display, was_active))

        threading.Thread(target=worker, daemon=True).start()

    def _on_peek_done(self, text: str, restore_overlays: bool):
        self.peek_label.configure(text=f"OCR Peek: {text}")
        if restore_overlays:
            self.overlay_manager.show()
            self._sync_overlay_selection()

    def save_config(self):
        self.overlay_manager.hide()
        if self.config_manager.save_config():
            messagebox.showinfo("Success", "Configuration saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save configuration")

    def save_layout_template(self):
        width, height = pyautogui.size()
        rows = self.config_manager.get("rows") or []
        layout = layout_from_gunsmoke_rows(rows, width, height)
        try:
            path = save_layout(layout)
        except OSError as e:
            messagebox.showerror("Error", f"Could not write layout:\n{e}")
            return
        messagebox.showinfo(
            "Layout saved",
            f"Saved gunsmoke template for {width}x{height}:\n{path}",
        )

    def apply_layout_f4(self):
        if self.on_apply_layout:
            self.on_apply_layout()
        else:
            messagebox.showwarning("Layout", "Apply layout is not wired in this build.")
