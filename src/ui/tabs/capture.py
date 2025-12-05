import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from src.constants import THEME
from src.ui.styles import create_button
from src.core.scanner import safe_grab
from src.data.models import PlayerScore
from src.data.storage import save_to_csv
import threading

class CaptureTab(tk.Frame):
    def __init__(self, parent, config_manager, ocr_processor, season_manager):
        super().__init__(parent, bg=THEME['bg_dark'])
        self.config_manager = config_manager
        self.ocr_processor = ocr_processor
        self.season_num = season_manager.season_num
        self.season_manager = season_manager # We might need this to check current season
        
        self.captured_data = [] # List of PlayerScore or dicts? Let's use dicts internally for compatibility then convert
        self.capture_count = 0
        self.is_capturing = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # Control panel
        ctrl_frame = tk.Frame(self, bg=THEME['bg_medium'])
        ctrl_frame.pack(fill=tk.X, padx=20, pady=20)
        
        btn_container = tk.Frame(ctrl_frame, bg=THEME['bg_medium'])
        btn_container.pack(pady=15)
        
        create_button(btn_container, "Set Season", self.set_season_dialog,
                      THEME['accent_cyan']).pack(side=tk.LEFT, padx=5)
        create_button(btn_container, "📸 Capture (F9)", self.start_capture_thread,
                      THEME['success']).pack(side=tk.LEFT, padx=5)
        create_button(btn_container, "Clear All", self.clear_all,
                      THEME['warning']).pack(side=tk.LEFT, padx=5)
        create_button(btn_container, "💾 Save to CSV", self.save_data,
                      THEME['accent_cyan']).pack(side=tk.LEFT, padx=5)
        
        # Stats
        stats_frame = tk.Frame(self, bg=THEME['bg_light'])
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.stats_label = tk.Label(stats_frame, text="Total Players: 0 | Captures: 0",
                                    font=("Segoe UI", 11), bg=THEME['bg_light'],
                                    fg=THEME['text_secondary'])
        self.stats_label.pack(pady=12)
        
        # Data table
        table_container = tk.Frame(self, bg=THEME['bg_dark'])
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        columns = ("Season", "IGN", "Top Score", "Total Score")
        self.tree = ttk.Treeview(table_container, columns=columns, show='headings',
                                height=20, style='Custom.Treeview')
        
        self.tree.heading("Season", text="Season")
        self.tree.heading("IGN", text="IGN (Nickname)")
        self.tree.heading("Top Score", text="Single High Score")
        self.tree.heading("Total Score", text="Total Score")
        
        self.tree.column("Season", width=80, anchor=tk.CENTER)
        self.tree.column("IGN", width=250)
        self.tree.column("Top Score", width=120, anchor=tk.E)
        self.tree.column("Total Score", width=120, anchor=tk.E)
        
        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Double click to edit
        self.tree.bind('<Double-1>', self.on_cell_double_click)
        
        # Status bar
        status_frame = tk.Frame(self, bg=THEME['bg_medium'], height=35)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready. Press F9 to capture.",
                                     font=("Segoe UI", 9), bg=THEME['bg_medium'],
                                     fg=THEME['text_secondary'])
        self.status_label.pack(pady=8)

        # Inline editing state
        self.edit_entry = None
        self.editing_item = None

    def set_season_dialog(self):
        # Callback to parent or season manager?
        # For now just update local attribute
        current = self.season_num if self.season_num else 1
        new_season = simpledialog.askinteger("Override Season", "Enter season number:", 
                                            initialvalue=current, minvalue=1, maxvalue=999)
        if new_season:
            self.season_num = new_season
            # Also notify season manager likely
            if hasattr(self.season_manager, 'set_manual_season'):
                self.season_manager.set_manual_season(new_season)
            self.status_label.config(text=f"Season set to {new_season}")

    def start_capture_thread(self, event=None):
        if self.is_capturing:
            return
        
        if self.season_num is None:
            messagebox.showwarning("Season Not Set", "Please set the season number first!")
            return

        self.is_capturing = True
        self.status_label.config(text="Capturing... (Processing)")
        
        # Run in thread
        threading.Thread(target=self._capture_logic, daemon=True).start()

    def _capture_logic(self):
        try:
            batch = []
            rows = self.config_manager.get("rows", [])
            
            for row_config in rows:
                nick_img = safe_grab(row_config["nickname"])
                single_img = safe_grab(row_config["single_high"])
                total_img = safe_grab(row_config["total_score"])
                
                if nick_img is None: continue
                
                nickname = self.ocr_processor.extract_text(nick_img, is_number=False, config=self.config_manager.config)
                single_text = self.ocr_processor.extract_text(single_img, is_number=True, config=self.config_manager.config)
                total_text = self.ocr_processor.extract_text(total_img, is_number=True, config=self.config_manager.config)
                
                nickname = self.ocr_processor.clean_nickname(nickname)
                single_score = self.ocr_processor.clean_number(single_text, is_single_score=True)
                total_score = self.ocr_processor.clean_number(total_text)
                
                min_nick_len = self.config_manager.get("validation", {}).get("min_nickname_length", 2)
                
                if len(nickname) >= min_nick_len:
                    batch.append(PlayerScore(
                        season=self.season_num,
                        ign=nickname,
                        topscore=single_score,
                        totalscore=total_score
                    ))
            
            # Update UI in main thread
            self.after(0, lambda: self._on_capture_complete(batch))
            
        except Exception as e:
            print(f"Capture error: {e}")
            self.after(0, lambda: self.status_label.config(text=f"Error: {e}"))
            self.is_capturing = False

    def _on_capture_complete(self, batch):
        self.capture_count += 1
        
        # Deduplicate
        if batch and self.captured_data:
            # We convert captured_data (dicts) to check
            recent = [p["ign"] for p in self.captured_data[-20:]]
            batch = [p for p in batch if p.ign not in recent]
        
        # Convert batch to dicts
        for p in batch:
            self.captured_data.append(p.to_dict())
            
        self.refresh_table()
        
        self.stats_label.config(text=f"Total Players: {len(self.captured_data)} | Captures: {self.capture_count}")
        self.status_label.config(text=f"✓ Captured {len(batch)} new players.")
        self.is_capturing = False

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for player in self.captured_data:
            self.tree.insert('', tk.END, values=(
                player["season"],
                player["ign"],
                f"{player['topscore']:,}",
                f"{player['totalscore']:,}"
            ))

    def clear_all(self):
        if messagebox.askyesno("Clear All", "Clear all captured data?"):
            self.captured_data = []
            self.refresh_table()
            self.stats_label.config(text="Total Players: 0 | Captures: 0")

    def save_data(self):
        if not self.captured_data:
            return
        
        # Convert dicts back to objects for storage module... or just update storage module to accept dicts?
        # Storage module accepts PlayerScore objects.
        # Let's convert back
        models = [PlayerScore(**d) for d in self.captured_data]
        filename = save_to_csv(models, self.season_num)
        messagebox.showinfo("Saved", f"Data saved to {filename}")

    # Inline editing
    def on_cell_double_click(self, event):
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column: return
        
        # Calculate cell coordinates
        x, y, w, h = self.tree.bbox(item, column)
        
        # Prepare editing state
        self.editing_item = item
        col_idx = int(column.replace('#', '')) - 1
        self.editing_col = ["season", "ign", "topscore", "totalscore"][col_idx]
        self.editing_row_idx = self.tree.index(item)
        
        # Get current value
        current_val = self.captured_data[self.editing_row_idx][self.editing_col]
        
        # Create entry widget
        self.edit_entry = tk.Entry(self.tree, width=10) # Width shouldn't matter as we place it
        self.edit_entry.place(x=x, y=y, width=w, height=h)
        self.edit_entry.insert(0, str(current_val))
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        
        # Bind events
        self.edit_entry.bind('<Return>', self.finish_edit)
        self.edit_entry.bind('<FocusOut>', self.finish_edit)
        self.edit_entry.bind('<Escape>', self.cancel_edit)

    def finish_edit(self, event):
        if not self.edit_entry: return
        
        new_val = self.edit_entry.get()
        self.edit_entry.destroy()
        self.edit_entry = None
        
        try:
            if self.editing_col in ['season', 'topscore', 'totalscore']:
                val = int(new_val.replace(',', ''))
            else:
                val = new_val
            
            self.captured_data[self.editing_row_idx][self.editing_col] = val
            self.refresh_table()
        except ValueError:
            pass # Ignore invalid inputs
            
    def cancel_edit(self, event):
        if self.edit_entry:
            self.edit_entry.destroy()
            self.edit_entry = None
