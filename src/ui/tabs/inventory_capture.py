"""Growth Data capture controls (Inventory mode)."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from src.constants import CLASS_COLORS, THEME, class_tag, configure_class_tags
from src.core.growth_scanner import GrowthScanner
from src.data.inventory_db import InventoryDB
from src.ui.styles import create_button

_LOG_TYPE_RE = re.compile(
    r"\[(" + "|".join(re.escape(t) for t in CLASS_COLORS) + r")\]"
)


class InventoryCaptureTab(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        config_manager,
        ocr_processor,
        overlay_manager,
        fonts,
        db: InventoryDB = None,
        on_inventory_refresh=None,
        overlay_var=None,
    ):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.db = db or InventoryDB()
        self.on_inventory_refresh = on_inventory_refresh
        self.overlay_var = overlay_var
        self.scanner = GrowthScanner(config_manager, ocr_processor, self.db)
        self.is_scanning = False
        self.session_cores = []
        self.setup_ui()

    def setup_ui(self):
        ctrl = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        ctrl.pack(fill=tk.X, padx=20, pady=20)

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.pack(pady=12)
        create_button(
            btn_row,
            "Full scan (F9)",
            self.start_full_scan,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row,
            "Last row (F10)",
            self.start_last_row,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row,
            "Current core (F8)",
            self.start_single,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row,
            "Stop (F5)",
            self.stop_scan,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)
        create_button(
            btn_row,
            "Clear log",
            self.clear_log,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkLabel(
            ctrl,
            text=(
                "Before first run: unlock all Growth Data cores in-game.\n"
                "F9 walks 14×6, locks each scanned core, scrolls (~5 rows + extra px), "
                "skips top overlap row after scroll.\n"
                "F10 retries the bottom row · F8 scans the currently selected core only.\n"
                "If scroll leaves a partial top row, raise scroll_extra_px a little. "
                "Turn overlays off while scanning."
            ),
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            justify=tk.LEFT,
        ).pack(padx=16, pady=(0, 8))

        growth = self.config_manager.get_inventory_growth()
        tune = ctk.CTkFrame(ctrl, fg_color="transparent")
        tune.pack(padx=16, pady=(0, 12))
        self.scroll_rows_entry = self._tune_field(
            tune, "Scroll rows", str(growth.get("scroll_rows", 5))
        )
        self.scroll_extra_entry = self._tune_field(
            tune, "Extra px", str(growth.get("scroll_extra_px", 24))
        )
        self.skip_top_entry = self._tune_field(
            tune, "Skip top after scroll", str(growth.get("skip_rows_after_scroll", 1))
        )
        create_button(
            tune,
            "Save scroll",
            self.save_scroll_settings,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=8)

        stats = ctk.CTkFrame(self, fg_color=THEME["bg_raised"], corner_radius=4)
        stats.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.stats_label = ctk.CTkLabel(
            stats,
            text="Session: 0 | DB cores: 0 | Total qty: 0",
            font=self.fonts.body_medium,
            text_color=THEME["text_strong"],
        )
        self.stats_label.pack(pady=10)

        log_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))
        self.log = ctk.CTkTextbox(log_frame, font=self.fonts.caption)
        self.log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        configure_class_tags(self.log)

        table = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        table.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        cols = ("Type", "Perks", "Qty")
        self.tree = ttk.Treeview(
            table, columns=cols, show="headings", height=8, style="Custom.Treeview"
        )
        for c, w in (
            ("Type", 100),
            ("Perks", 420),
            ("Qty", 50),
        ):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor=tk.W if c != "Qty" else tk.CENTER)
        configure_class_tags(self.tree)
        sb = ctk.CTkScrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)
        self._refresh_stats()

    def _tune_field(self, parent, label: str, value: str) -> ctk.CTkEntry:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(side=tk.LEFT, padx=6)
        ctk.CTkLabel(
            wrap,
            text=label,
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
        ).pack(anchor=tk.W)
        entry = ctk.CTkEntry(wrap, width=70, font=self.fonts.body)
        entry.insert(0, value)
        entry.pack()
        return entry

    def save_scroll_settings(self, *, quiet: bool = False) -> bool:
        g = self.config_manager.get_inventory_growth()
        try:
            g["scroll_rows"] = float(self.scroll_rows_entry.get().strip())
            g["scroll_extra_px"] = int(self.scroll_extra_entry.get().strip())
            g["skip_rows_after_scroll"] = int(self.skip_top_entry.get().strip())
        except ValueError:
            if not quiet:
                messagebox.showerror(
                    "Invalid", "Scroll rows / extra px / skip top must be numbers."
                )
            return False
        self.config_manager.save_config()
        if not quiet:
            self._append_log(
                f"Saved scroll: rows={g['scroll_rows']} extra={g['scroll_extra_px']}px "
                f"skip_top={g['skip_rows_after_scroll']}"
            )
        return True

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def _append_log(self, msg: str):
        # Newest lines on top; color [Bulwark]/[Sentinel]/… with class hues
        self.log.insert("1.0", "\n")
        m = _LOG_TYPE_RE.search(msg)
        if m:
            before, typ, after = msg[: m.start()], m.group(1), msg[m.end() :]
            self.log.insert("1.0", after)
            self.log.insert("1.0", f"[{typ}]", class_tag(typ))
            self.log.insert("1.0", before)
        else:
            self.log.insert("1.0", msg)
        self.log.see("1.0")

    def _status(self, msg: str):
        self.after(0, lambda m=msg: self._append_log(m))

    def _on_core(self, core: dict):
        def _ui():
            perks = ", ".join(
                f"{p['name']} Lv.{p['level']}" for p in core.get("perks") or []
            )
            ctype = core.get("type")
            tag = class_tag(ctype)
            self.tree.insert(
                "",
                0,
                values=(
                    ctype,
                    perks,
                    core.get("quantity", 1),
                ),
                tags=(tag,) if tag else (),
            )
            self.session_cores.append(core)
            self._refresh_stats()
            if self.on_inventory_refresh:
                self.on_inventory_refresh()

        self.after(0, _ui)

    def _refresh_stats(self):
        self.stats_label.configure(
            text=(
                f"Session: {len(self.session_cores)} | "
                f"DB unique: {self.db.unique_count()} | "
                f"Total qty: {self.db.total_quantity()}"
            )
        )

    def _busy(self) -> bool:
        if self.is_scanning:
            messagebox.showinfo("Busy", "A scan is already running.")
            return True
        return False

    def _hide_overlay(self):
        if self.overlay_manager.active:
            self.overlay_manager.hide()
            if self.overlay_var is not None:
                self.overlay_var.set(False)

    def stop_scan(self):
        self.scanner.stop()
        self._status("Stop requested…")

    def start_full_scan(self):
        if self._busy():
            return
        self.save_scroll_settings(quiet=True)
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Full scan (F9) ===")

        def _run():
            try:
                result = self.scanner.scan_full(
                    status=self._status, on_core=self._on_core
                )
                self._status(
                    f"Done: scanned={result['scanned']} "
                    f"skipped={result['skipped_locked']} pages={result['pages']}"
                )
            finally:
                self.is_scanning = False
                self.after(0, self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()

    def start_last_row(self):
        if self._busy():
            return
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Last row (F10) ===")

        def _run():
            try:
                self.scanner.scan_last_row(status=self._status, on_core=self._on_core)
            finally:
                self.is_scanning = False
                self.after(0, self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()

    def start_single(self):
        if self._busy():
            return
        self._hide_overlay()
        self.is_scanning = True
        self._status("=== Single core (F8) ===")

        def _run():
            try:
                self.scanner.scan_single(status=self._status, on_core=self._on_core)
            finally:
                self.is_scanning = False
                self.after(0, self._refresh_stats)

        threading.Thread(target=_run, daemon=True).start()
