import threading
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from src.constants import THEME
from src.core.gacha_scanner import GachaScanner
from src.data.gacha_db import GachaDB
from src.ui.styles import create_button


class GachaCaptureTab(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        config_manager,
        ocr_processor,
        overlay_manager,
        fonts,
        db: GachaDB = None,
        on_history_refresh=None,
        overlay_var=None,
    ):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.overlay_manager = overlay_manager
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_history_refresh = on_history_refresh
        self.overlay_var = overlay_var

        self.scanner = GachaScanner(config_manager, ocr_processor, self.db)
        self.session_pulls = []
        self.is_scanning = False

        self.setup_ui()

    def setup_ui(self):
        ctrl_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        ctrl_frame.pack(fill=tk.X, padx=20, pady=20)

        btn_container = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_container.pack(pady=15)

        create_button(
            btn_container,
            "Scan Access Records (F9)",
            self.start_scan_thread,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Stop (F5)",
            self.stop_scan,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Clear Session",
            self.clear_session,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Clear History",
            self.clear_history,
            variant="ghost",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)

        timing_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        timing_row.pack(pady=(0, 8))

        gacha = self.config_manager.get_gacha()
        self.click_delay_entry = self._timing_field(
            timing_row,
            "Click delay (ms)",
            str(int(gacha.get("click_delay_ms", 150))),
        )
        self.settle_delay_entry = self._timing_field(
            timing_row,
            "OCR settle (ms)",
            str(int(gacha.get("ocr_settle_ms", 100))),
        )

        ctk.CTkLabel(
            ctrl_frame,
            text=(
                "Open Access Records on page 1 (or any page — scanner resets to 1). "
                "F9 starts scan on this tab · F5 stops (gacha mode). "
                "Lower delays = faster page turns (too low may skip pages)."
            ),
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(pady=(0, 12))

        stats_frame = ctk.CTkFrame(self, fg_color=THEME["bg_raised"], corner_radius=4)
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="Session pulls: 0 | DB total: 0",
            font=self.fonts.body_medium,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        )
        self.stats_label.pack(pady=10)

        table_container = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ("Time", "Source", "Type", "Name", "Rarity")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=18,
            style="Custom.Treeview",
        )
        for col, width, anchor in (
            ("Time", 160, tk.W),
            ("Source", 160, tk.W),
            ("Type", 80, tk.CENTER),
            ("Name", 220, tk.W),
            ("Rarity", 70, tk.CENTER),
        ):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=anchor)

        scrollbar = ctk.CTkScrollbar(table_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=4)

        status_frame = ctk.CTkFrame(
            self, fg_color=THEME["bg_surface"], corner_radius=0, height=30
        )
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready. Open Access Records, then F9 to scan (F5 to stop).",
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        )
        self.status_label.pack(pady=6)

        self._refresh_stats()

    def _timing_field(self, parent, label: str, initial: str) -> ctk.CTkEntry:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(side=tk.LEFT, padx=12)
        ctk.CTkLabel(
            wrap,
            text=label,
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT, padx=(0, 6))
        entry = ctk.CTkEntry(wrap, width=70, font=self.fonts.mono, justify="center")
        entry.insert(0, initial)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", self.apply_timing)
        entry.bind("<FocusOut>", self.apply_timing)
        return entry

    def apply_timing(self, _event=None):
        """Persist click/settle delays from the UI into gacha config."""
        gacha = self.config_manager.get_gacha()
        try:
            click_ms = int(self.click_delay_entry.get().strip())
            settle_ms = int(self.settle_delay_entry.get().strip())
        except ValueError:
            # Restore last saved values on bad input
            self.click_delay_entry.delete(0, tk.END)
            self.click_delay_entry.insert(0, str(int(gacha.get("click_delay_ms", 150))))
            self.settle_delay_entry.delete(0, tk.END)
            self.settle_delay_entry.insert(0, str(int(gacha.get("ocr_settle_ms", 100))))
            return

        click_ms = max(0, min(click_ms, 10000))
        settle_ms = max(0, min(settle_ms, 10000))
        gacha["click_delay_ms"] = click_ms
        gacha["ocr_settle_ms"] = settle_ms
        self.config_manager.save_config()

        # Keep fields showing the clamped values
        self.click_delay_entry.delete(0, tk.END)
        self.click_delay_entry.insert(0, str(click_ms))
        self.settle_delay_entry.delete(0, tk.END)
        self.settle_delay_entry.insert(0, str(settle_ms))

    def _refresh_stats(self):
        self.stats_label.configure(
            text=(
                f"Session pulls: {len(self.session_pulls)} | "
                f"DB total: {self.db.count_pulls()}"
            )
        )

    def start_scan_thread(self, _event=None):
        if self.is_scanning:
            return

        self.apply_timing()
        self.is_scanning = True
        self.session_pulls = []
        self.refresh_table()
        # Overlays would sit on top of the game and break OCR / clicks
        if self.overlay_manager.active:
            self.overlay_manager.hide()
            if self.overlay_var is not None:
                self.overlay_var.set(False)

        gacha = self.config_manager.get_gacha()
        self.status_label.configure(
            text=(
                f"Starting scan… "
                f"(click {gacha.get('click_delay_ms')}ms / "
                f"settle {gacha.get('ocr_settle_ms')}ms)"
            )
        )
        threading.Thread(target=self._scan_logic, daemon=True).start()

    def stop_scan(self):
        if self.is_scanning:
            self.scanner.request_stop()
            self.status_label.configure(text="Stopping…")

    def _set_status(self, msg: str):
        self.after(0, lambda m=msg: self.status_label.configure(text=m))

    def _on_pull(self, pull: dict):
        self.after(0, lambda p=pull: self._append_pull(p))

    def _append_pull(self, pull: dict):
        self.session_pulls.append(pull)
        self.tree.insert(
            "",
            tk.END,
            values=(
                pull["purchase_time"],
                pull["purchase_source"],
                pull["item_type"],
                pull["item_name"],
                (pull.get("rarity_color") or "").title(),
            ),
        )
        self._refresh_stats()

    def _scan_logic(self):
        try:
            summary = self.scanner.scan_all_pages(
                status_cb=self._set_status,
                on_pull=self._on_pull,
            )
            self.after(0, lambda s=summary: self._on_scan_complete(s))
        except Exception as e:
            print(f"Gacha scan error: {e}")
            err = str(e)
            self.after(
                0, lambda msg=err: self.status_label.configure(text=f"Error: {msg}")
            )
            self.is_scanning = False

    def _on_scan_complete(self, summary: dict):
        self.is_scanning = False
        self._refresh_stats()
        self.status_label.configure(
            text=(
                f"Done. Pages {summary['pages']}, "
                f"saved {summary['inserted']}, skipped {summary['skipped']}."
            )
        )
        if self.on_history_refresh:
            self.on_history_refresh()

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for pull in self.session_pulls:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    pull["purchase_time"],
                    pull["purchase_source"],
                    pull["item_type"],
                    pull["item_name"],
                    (pull.get("rarity_color") or "").title(),
                ),
            )

    def clear_session(self):
        if self.is_scanning:
            messagebox.showwarning("Scanning", "Stop the scan before clearing.")
            return
        self.session_pulls = []
        self.refresh_table()
        self._refresh_stats()
        self.status_label.configure(text="Session cleared.")

    def clear_history(self):
        """Wipe saved pulls from SQLite so a fresh scan can be tested."""
        if self.is_scanning:
            messagebox.showwarning("Scanning", "Stop the scan before clearing history.")
            return
        if not messagebox.askyesno(
            "Clear History",
            "Delete ALL saved gacha pulls from the local database?\n"
            "This cannot be undone.",
        ):
            return
        self.db.clear_all()
        self.session_pulls = []
        self.refresh_table()
        self._refresh_stats()
        self.status_label.configure(text="History cleared. Ready for a new scan.")
        if self.on_history_refresh:
            self.on_history_refresh()
