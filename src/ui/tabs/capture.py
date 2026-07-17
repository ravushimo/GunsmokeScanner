import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import customtkinter as ctk

from src.constants import THEME
from src.core.scanner import safe_grab
from src.data.models import PlayerScore
from src.data.storage import save_to_csv
from src.ui.styles import create_button


class CaptureTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager, ocr_processor, season_manager, fonts):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.season_num = season_manager.season_num
        self.season_manager = season_manager
        self.fonts = fonts

        # Internal data is dicts so we can edit cells in-place without
        # reconstructing PlayerScore instances on every keystroke.
        self.captured_data = []
        self.capture_count = 0
        self.is_capturing = False

        self.edit_entry = None
        self.editing_item = None

        self.setup_ui()

    def setup_ui(self):
        # Control panel
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
            "Set Season",
            self.set_season_dialog,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Capture (F9)",
            self.start_capture_thread,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Clear All",
            self.clear_all,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_container,
            "Save to CSV",
            self.save_data,
            variant="featured",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)

        # Stats
        stats_frame = ctk.CTkFrame(self, fg_color=THEME["bg_raised"], corner_radius=4)
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="Total Players: 0 | Captures: 0",
            font=self.fonts.body_medium,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        )
        self.stats_label.pack(pady=10)

        # Data table - ttk.Treeview restyled via the Custom.Treeview ttk style
        table_container = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
        )
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        columns = ("Season", "IGN", "Top Score", "Total Score")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=20,
            style="Custom.Treeview",
        )

        self.tree.heading("Season", text="Season")
        self.tree.heading("IGN", text="IGN (Nickname)")
        self.tree.heading("Top Score", text="Single High Score")
        self.tree.heading("Total Score", text="Total Score")

        self.tree.column("Season", width=80, anchor=tk.CENTER)
        self.tree.column("IGN", width=250)
        self.tree.column("Top Score", width=120, anchor=tk.E)
        self.tree.column("Total Score", width=120, anchor=tk.E)

        scrollbar = ctk.CTkScrollbar(table_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=4)

        self.tree.bind("<Double-1>", self.on_cell_double_click)

        # Status bar
        status_frame = ctk.CTkFrame(
            self, fg_color=THEME["bg_surface"], corner_radius=0, height=30
        )
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready. Press F9 to capture.",
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        )
        self.status_label.pack(pady=6)

    def set_season_dialog(self):
        current = self.season_num if self.season_num else 1
        new_season = simpledialog.askinteger(
            "Override Season",
            "Enter season number:",
            initialvalue=current,
            minvalue=1,
            maxvalue=999,
        )
        if new_season:
            self.season_num = new_season
            if hasattr(self.season_manager, "set_manual_season"):
                self.season_manager.set_manual_season(new_season)
            self.status_label.configure(text=f"Season set to {new_season}")

    def start_capture_thread(self, _event=None):
        if self.is_capturing:
            return

        if self.season_num is None:
            messagebox.showwarning(
                "Season Not Set", "Please set the season number first!"
            )
            return

        self.is_capturing = True
        self.status_label.configure(text="Capturing... (Processing)")

        threading.Thread(target=self._capture_logic, daemon=True).start()

    def _capture_logic(self):
        try:
            batch = []
            rows = self.config_manager.get("rows", [])

            for row_config in rows:
                nick_img = safe_grab(row_config["nickname"])
                single_img = safe_grab(row_config["single_high"])
                total_img = safe_grab(row_config["total_score"])

                if nick_img is None:
                    continue

                nickname = self.ocr_processor.extract_text(
                    nick_img, is_number=False, config=self.config_manager.config
                )
                single_text = self.ocr_processor.extract_text(
                    single_img, is_number=True, config=self.config_manager.config
                )
                total_text = self.ocr_processor.extract_text(
                    total_img, is_number=True, config=self.config_manager.config
                )

                nickname = self.ocr_processor.clean_nickname(nickname)
                single_score = self.ocr_processor.clean_number(
                    single_text, is_single_score=True
                )
                total_score = self.ocr_processor.clean_number(total_text)

                min_nick_len = self.config_manager.get("validation", {}).get(
                    "min_nickname_length", 2
                )

                if len(nickname) >= min_nick_len:
                    batch.append(
                        PlayerScore(
                            season=self.season_num,
                            ign=nickname,
                            topscore=single_score,
                            totalscore=total_score,
                        )
                    )

            self.after(0, lambda: self._on_capture_complete(batch))

        except Exception as e:
            print(f"Capture error: {e}")
            err = str(e)
            self.after(
                0, lambda msg=err: self.status_label.configure(text=f"Error: {msg}")
            )
            self.is_capturing = False

    def _on_capture_complete(self, batch):
        self.capture_count += 1

        if batch and self.captured_data:
            recent = [p["ign"] for p in self.captured_data[-20:]]
            batch = [p for p in batch if p.ign not in recent]

        for p in batch:
            self.captured_data.append(p.to_dict())

        self.refresh_table()

        self.stats_label.configure(
            text=f"Total Players: {len(self.captured_data)} | Captures: {self.capture_count}"
        )
        self.status_label.configure(text=f"Captured {len(batch)} new players.")
        self.is_capturing = False

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for player in self.captured_data:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    player["season"],
                    player["ign"],
                    f"{player['topscore']:,}",
                    f"{player['totalscore']:,}",
                ),
            )

    def clear_all(self):
        if messagebox.askyesno("Clear All", "Clear all captured data?"):
            self.captured_data = []
            self.refresh_table()
            self.stats_label.configure(text="Total Players: 0 | Captures: 0")

    def save_data(self):
        if not self.captured_data:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Save CSV - Optional Guild Rank")
        dialog.geometry("420x200")
        dialog.configure(fg_color=THEME["bg_canvas"])
        dialog.resizable(False, False)

        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 210
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 100
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text="Add Guild Rank (Optional)",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            dialog,
            text="Enter rank to include it in the file:",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(pady=(0, 10))

        entry = ctk.CTkEntry(dialog, font=self.fonts.mono, width=120, justify="center")
        entry.pack(pady=5)
        entry.focus_set()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        result_rank = [None]

        def on_update():
            rank = entry.get().strip()
            if rank:
                result_rank[0] = rank
            dialog.destroy()

        def on_skip():
            dialog.destroy()

        create_button(
            btn_frame,
            "Update Rank (Enter)",
            on_update,
            variant="primary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)
        create_button(
            btn_frame,
            "No, Just Save (Esc)",
            on_skip,
            variant="secondary",
            font=self.fonts.ui,
        ).pack(side=tk.LEFT, padx=5)

        dialog.bind("<Return>", lambda _e: on_update())
        dialog.bind("<Escape>", lambda _e: on_skip())

        self.wait_window(dialog)

        models = [PlayerScore(**d) for d in self.captured_data]
        filename = save_to_csv(models, self.season_num, guild_rank=result_rank[0])
        messagebox.showinfo("Saved", f"Data saved to {filename}")

    # Inline editing for the Treeview - the Entry is placed over the cell bbox.
    # This is the same fragile pattern as before; PySide6 would replace it.
    def on_cell_double_click(self, event):
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return

        x, y, w, h = self.tree.bbox(item, column)

        self.editing_item = item
        col_idx = int(column.replace("#", "")) - 1
        self.editing_col = ["season", "ign", "topscore", "totalscore"][col_idx]
        self.editing_row_idx = self.tree.index(item)

        current_val = self.captured_data[self.editing_row_idx][self.editing_col]

        # Use a plain tk.Entry - CTkEntry's wrapper Frame interferes with the
        # pixel-precise overlay positioning needed for inline cell editing.
        self.edit_entry = tk.Entry(
            self.tree,
            bg=THEME["bg_surface"],
            fg=THEME["text_input"],
            insertbackground=THEME["text_input"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["accent_orange"],
            highlightcolor=THEME["accent_orange"],
        )
        self.edit_entry.place(x=x, y=y, width=w, height=h)
        self.edit_entry.insert(0, str(current_val))
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()

        self.edit_entry.bind("<Return>", self.finish_edit)
        self.edit_entry.bind("<FocusOut>", self.finish_edit)
        self.edit_entry.bind("<Escape>", self.cancel_edit)

    def finish_edit(self, _event):
        if not self.edit_entry:
            return

        new_val = self.edit_entry.get()
        self.edit_entry.destroy()
        self.edit_entry = None

        try:
            if self.editing_col in ("season", "topscore", "totalscore"):
                val = int(new_val.replace(",", ""))
            else:
                val = new_val

            self.captured_data[self.editing_row_idx][self.editing_col] = val
            self.refresh_table()
        except ValueError:
            pass

    def cancel_edit(self, _event):
        if self.edit_entry:
            self.edit_entry.destroy()
            self.edit_entry = None
