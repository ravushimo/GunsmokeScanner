import tkinter as tk
from src.constants import THEME
from src.ui.styles import create_button

class SetupTab(tk.Frame):
    def __init__(self, parent, config_manager, overlay_manager):
        super().__init__(parent, bg=THEME['bg_dark'])
        self.config_manager = config_manager
        self.overlay_manager = overlay_manager
        
        # Connect overlay callback to this tab
        self.overlay_manager.on_update_callback = self.on_overlay_update
        
        self.setup_ui()
    
    def setup_ui(self):
        # Instructions
        inst_frame = tk.Frame(self, bg=THEME['bg_light'], relief=tk.FLAT, bd=2)
        inst_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(inst_frame, text="Region Setup",
                font=("Segoe UI", 14, "bold"), bg=THEME['bg_light'],
                fg=THEME['text_primary']).pack(anchor=tk.W, padx=15, pady=(15, 5))
        
        tk.Label(inst_frame, 
                text="1. Select row and column below\n2. Click 'Show Overlay' to see the region on your game screen\n3. Drag the overlay with mouse or use arrow keys to adjust\n4. Click 'Save Config' when all regions are positioned correctly",
                font=("Segoe UI", 10), bg=THEME['bg_light'],
                fg=THEME['text_secondary'], justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 15))
        
        # Selection controls
        ctrl_frame = tk.Frame(self, bg=THEME['bg_light'])
        ctrl_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        center_container = tk.Frame(ctrl_frame, bg=THEME['bg_light'])
        center_container.pack()
        
        # Row selection
        row_frame = tk.Frame(center_container, bg=THEME['bg_light'])
        row_frame.pack(side=tk.LEFT, padx=40, pady=10)
        
        tk.Label(row_frame, text="Select Row:", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_light'], fg=THEME['text_primary']).pack(anchor=tk.W, pady=5)
        
        self.row_var = tk.IntVar(value=0)
        for i in range(5):
            rb = tk.Radiobutton(row_frame, text=f"Row {i+1}", variable=self.row_var, value=i,
                              bg=THEME['bg_light'], fg=THEME['text_secondary'],
                              selectcolor=THEME['bg_medium'], activebackground=THEME['bg_light'],
                              activeforeground=THEME['accent_cyan'],
                              font=("Segoe UI", 10),
                              command=self.on_selection_change)
            rb.pack(anchor=tk.W, pady=2)
        
        # Column selection
        col_frame = tk.Frame(center_container, bg=THEME['bg_light'])
        col_frame.pack(side=tk.LEFT, padx=40, pady=10)
        
        tk.Label(col_frame, text="Select Column:", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_light'], fg=THEME['text_primary']).pack(anchor=tk.W, pady=5)
        
        self.col_var = tk.StringVar(value="nickname")
        cols = [("Nickname", "nickname"), ("Single High", "single_high"), ("Total Score", "total_score")]
        for text, value in cols:
            rb = tk.Radiobutton(col_frame, text=text, variable=self.col_var, value=value,
                              bg=THEME['bg_light'], fg=THEME['text_secondary'],
                              selectcolor=THEME['bg_medium'], activebackground=THEME['bg_light'],
                              activeforeground=THEME['accent_cyan'],
                              font=("Segoe UI", 10),
                              command=self.on_selection_change)
            rb.pack(anchor=tk.W, pady=2)
        
        # Region info
        info_frame = tk.Frame(self, bg=THEME['bg_medium'])
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 15))
        
        tk.Label(info_frame, text="Current Region (editable):", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_medium'], fg=THEME['text_primary']).pack(pady=(15, 10))
        
        fields_frame = tk.Frame(info_frame, bg=THEME['bg_medium'])
        fields_frame.pack(pady=(10, 10))
        
        self.region_entries = {}
        labels = [
            ("X:", "x", 0, 0),
            ("Y:", "y", 0, 1),
            ("Width:", "w", 1, 0),
            ("Height:", "h", 1, 1)
        ]
        
        for label_text, field_name, row, col in labels:
            field_container = tk.Frame(fields_frame, bg=THEME['bg_medium'])
            field_container.grid(row=row, column=col, padx=15, pady=8)
            
            tk.Label(field_container, text=label_text, bg=THEME['bg_medium'],
                    fg=THEME['text_secondary'], font=("Segoe UI", 10, "bold"),
                    width=7, anchor=tk.E).pack(side=tk.LEFT, padx=(0, 8))
            
            entry = tk.Entry(field_container, width=12, bg=THEME['bg_light'],
                           fg=THEME['text_primary'], font=("Consolas", 11),
                           insertbackground=THEME['accent_cyan'])
            entry.pack(side=tk.LEFT)
            entry.bind('<Return>', self.apply_manual_values)
            entry.bind('<FocusOut>', self.apply_manual_values)
            
            self.region_entries[field_name] = entry
        
        # Apply button
        apply_btn = create_button(info_frame, "Apply Changes", self.apply_manual_values, THEME['accent_cyan'])
        apply_btn.pack(pady=(5, 15))
        
        # Save button
        btn_frame = tk.Frame(self, bg=THEME['bg_dark'])
        btn_frame.pack(pady=20)
        
        create_button(btn_frame, "Save Config", self.save_config,
                      THEME['success']).pack(side=tk.LEFT, padx=5)
        
        self.update_region_info()

    def on_selection_change(self):
        self.update_region_info()
        # If overlay is showing, refresh it to highlight or just update info
        if self.overlay_manager.active:
            self.overlay_manager.show() # Refresh to update drag handlers context if needed? NO, handlers use live config

    def on_overlay_update(self, row_idx, col_name, select=False):
        """Called by overlay manager when a region changes"""
        if select:
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
        self.region_entries['x'].delete(0, tk.END)
        self.region_entries['x'].insert(0, str(bbox[0]))
        self.region_entries['y'].delete(0, tk.END)
        self.region_entries['y'].insert(0, str(bbox[1]))
        self.region_entries['w'].delete(0, tk.END)
        self.region_entries['w'].insert(0, str(bbox[2]))
        self.region_entries['h'].delete(0, tk.END)
        self.region_entries['h'].insert(0, str(bbox[3]))

    def apply_manual_values(self, event=None):
        try:
            x = int(self.region_entries['x'].get())
            y = int(self.region_entries['y'].get())
            w = int(self.region_entries['w'].get())
            h = int(self.region_entries['h'].get())
            
            self.set_current_bbox([x, y, w, h])
            
            if self.overlay_manager.active:
                self.overlay_manager.show()
        except ValueError:
            pass

    def save_config(self):
        self.overlay_manager.hide()
        if self.config_manager.save_config():
            tk.messagebox.showinfo("Success", "Configuration saved successfully!")
        else:
            tk.messagebox.showerror("Error", "Failed to save configuration")
