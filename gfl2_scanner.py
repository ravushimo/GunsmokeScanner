"""
GFL2 Leaderboard OCR Scanner - Unified Application
Combines visual region selector and capture tool with gunsmoke.app theme
"""
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab
import easyocr
import pandas as pd
import re
import os
from datetime import datetime, timedelta
import keyboard
import warnings

warnings.filterwarnings('ignore', message='.*pin_memory.*')

# gunsmoke.app Theme Colors
THEME = {
    'bg_dark': '#0f1419',           # Main background
    'bg_medium': '#1a1f2e',         # Panel background
    'bg_light': '#252d3d',          # Card background
    'accent_cyan': '#00d4ff',       # Primary accent (cyan)
    'accent_hover': '#00a8cc',      # Hover state
    'text_primary': '#ffffff',      # Main text
    'text_secondary': '#94a3b8',    # Secondary text
    'text_muted': '#64748b',        # Muted text
    'success': '#10b981',           # Success green
    'warning': '#f59e0b',           # Warning orange
    'danger': '#ef4444',            # Danger red
    'border': '#334155'             # Border color
}

class GFL2Scanner:
    def __init__(self):
        # Create default config if it doesn't exist
        if not os.path.exists("config.json"):
            self.create_default_config()
            first_run = True
        else:
            first_run = False
        
        # Load config
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config.json: {e}")
            exit()
        
        # Initialize EasyOCR
        print("Loading EasyOCR models...")
        languages = self.config.get("ocr_languages", ["ch_sim", "en"])
        self.reader = easyocr.Reader(languages, gpu=True, model_storage_directory='./easyocr_models')
        print("EasyOCR ready!")
        
        # State
        self.captured_data = []
        self.screen_w, self.screen_h = pyautogui.size()
        self.capture_count = 0
        
        # Auto-calculate season
        season_num, status = self.calculate_season()
        if status == "Active":
            self.season = season_num
            self.season_auto = True  # Track if auto-calculated
        else:
            self.season = None  # Off-season
            self.season_auto = False
        
        # Region selector state
        self.overlay_window = None
        self.current_row = 0
        self.current_col = "nickname"
        self.dragging = False
        self.drag_start = None
        
        # Inline editing state
        self.editing_item = None
        self.editing_column = None
        self.edit_entry = None
        
        # Create results directory
        os.makedirs("./results", exist_ok=True)
        
        # Setup main window
        self.root = tk.Tk()
        self.root.title("GFL2 Leaderboard Scanner - gunsmoke.app")
        self.root.geometry("800x1000")
        self.root.configure(bg=THEME['bg_dark'])
        
        # Apply theme to ttk styles
        self.setup_styles()
        
        # Create UI
        self.setup_ui()
        
        # Register hotkey
        keyboard.add_hotkey('f9', self.capture_once)
        
        # Show welcome message on first run
        if first_run:
            messagebox.showinfo("Welcome!", 
                "Welcome to GFL2 Scanner!\n\n" +
                "This is your first run. Please go to the 'Setup Regions' tab " +
                "to configure capture regions for your screen resolution.\n\n" +
                "Click 'Show Overlay' to see and adjust the regions.")
        
    def create_default_config(self):
        """Create default config.json with placeholder values"""
        # Use screen center for default regions
        screen_w, screen_h = pyautogui.size()
        center_x = screen_w // 2
        center_y = screen_h // 2
        
        # Create placeholder regions (user will adjust these)
        default_config = {
            "screen_resolution": [screen_w, screen_h],
            "ocr_languages": ["ch_sim", "en"],
            "preprocessing": {
                "threshold": 140,
                "adaptive": True,
                "kernel_size": [2, 2]
            },
            "validation": {
                "min_nickname_length": 2,
                "min_total_score": 0,
                "max_duplicate_check": 20
            },
            "rows": []
        }
        
        # Create 5 rows with placeholder positions
        for i in range(5):
            row_y = center_y + (i * 60) - 120  # Spread rows vertically
            default_config["rows"].append({
                "nickname": [center_x - 400, row_y, 300, 50],
                "single_high": [center_x - 50, row_y, 200, 50],
                "total_score": [center_x + 200, row_y, 200, 50]
            })
        
        # Add metadata
        default_config["metadata"] = {
            "generated_by": "gfl2_scanner_default",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolution": f"{screen_w}x{screen_h}",
            "note": "Default configuration - please adjust regions in Setup tab"
        }
        
        # Save to file
        with open("config.json", "w") as f:
            json.dump(default_config, f, indent=2)
        
        self.config = default_config
        
    def calculate_season(self):
        """Calculate current season based on date
        Season 17: Nov 30 - Dec 6, 2025 (Sunday to Saturday)
        Pattern: 7 days active + 14 days break = 21 day cycle
        """
        # Reference point
        reference_date = datetime(2025, 11, 30)  # Season 17 start
        reference_season = 17
        
        today = datetime.now()
        days_since_ref = (today.date() - reference_date.date()).days
        
        # Handle dates before reference
        if days_since_ref < 0:
            # Go backwards
            days_before = abs(days_since_ref)
            cycles_before = (days_before + 20) // 21  # Round up
            season_num = reference_season - cycles_before
            # Calculate where we are in that earlier cycle
            cycle_start = reference_date - timedelta(days=cycles_before * 21)
            days_in_cycle = (today.date() - cycle_start.date()).days % 21
        else:
            # Current or future dates
            cycle_num = days_since_ref // 21
            days_in_cycle = days_since_ref % 21
            season_num = reference_season + cycle_num
        
        # Determine if in active season or break
        if days_in_cycle < 7:
            return season_num, "Active"
        else:
            return season_num, "Break"
    
    def get_season_dates(self, season_num):
        """Get start and end dates for a given season"""
        # Calculate offset from reference season
        reference_date = datetime(2025, 11, 30)
        reference_season = 17
        
        season_offset = season_num - reference_season
        days_offset = season_offset * 21  # Each cycle is 21 days
        
        start_date = reference_date + timedelta(days=days_offset)
        end_date = start_date + timedelta(days=6)  # 7 days inclusive
        
        return start_date, end_date
        
    def setup_styles(self):
        """Setup ttk styles matching gunsmoke.app theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Treeview
        style.configure('Custom.Treeview',
                       background=THEME['bg_light'],
                       foreground=THEME['text_primary'],
                       fieldbackground=THEME['bg_light'],
                       borderwidth=0,
                       font=('Segoe UI', 10))
        style.configure('Custom.Treeview.Heading',
                       background=THEME['bg_medium'],
                       foreground=THEME['accent_cyan'],
                       borderwidth=1,
                       relief='flat',
                       font=('Segoe UI', 10, 'bold'))
        style.map('Custom.Treeview',
                 background=[('selected', THEME['accent_cyan'])],
                 foreground=[('selected', THEME['bg_dark'])])
        
        # Configure Notebook (tabs)
        style.configure('Custom.TNotebook',
                       background=THEME['bg_dark'],
                       borderwidth=0)
        style.configure('Custom.TNotebook.Tab',
                       background=THEME['bg_medium'],
                       foreground=THEME['text_secondary'],
                       padding=[12, 6],
                       borderwidth=0,
                       relief='flat',
                       font=('Segoe UI', 11, 'bold'))
        style.map('Custom.TNotebook.Tab',
                 background=[('selected', THEME['bg_light'])],
                 foreground=[('selected', THEME['accent_cyan'])],
                 padding=[('selected', [12, 6])])
        
    def setup_ui(self):
        """Setup main UI with tabs"""
        # Header
        header = tk.Frame(self.root, bg=THEME['bg_medium'], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Logo and title
        title_frame = tk.Frame(header, bg=THEME['bg_medium'])
        title_frame.pack(side=tk.LEFT, padx=20, pady=15)
        
        tk.Label(title_frame, text="⚡", font=("Arial", 24), 
                bg=THEME['bg_medium'], fg=THEME['accent_cyan']).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(title_frame, text="GFL2 Leaderboard Scanner",
                font=("Segoe UI", 18, "bold"), bg=THEME['bg_medium'], 
                fg=THEME['text_primary']).pack(side=tk.LEFT)
        
        # Season indicator and controls
        right_controls = tk.Frame(header, bg=THEME['bg_medium'])
        right_controls.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Season label at top with more space
        if self.season:
            start_date, end_date = self.get_season_dates(self.season)
            season_text = f"Season {self.season} ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
            season_color = THEME['accent_cyan']
        else:
            season_text = "Off-Season Break"
            season_color = THEME['warning']
        
        self.season_label = tk.Label(right_controls, text=season_text,
                                     font=("Segoe UI", 11, "bold"), bg=THEME['bg_medium'],
                                     fg=season_color)
        self.season_label.pack(side=tk.TOP, anchor=tk.E, pady=(0, 8))
        
        # Checkboxes side by side
        checkbox_frame = tk.Frame(right_controls, bg=THEME['bg_medium'])
        checkbox_frame.pack(side=tk.TOP, anchor=tk.E)
        
        # Always on top checkbox
        self.always_on_top_var = tk.BooleanVar(value=True)
        on_top_cb = tk.Checkbutton(checkbox_frame, text="Always on Top",
                                   variable=self.always_on_top_var,
                                   command=self.toggle_always_on_top,
                                   bg=THEME['bg_medium'], fg=THEME['text_secondary'],
                                   selectcolor=THEME['bg_dark'],
                                   activebackground=THEME['bg_medium'],
                                   activeforeground=THEME['accent_cyan'],
                                   font=("Segoe UI", 9))
        on_top_cb.pack(side=tk.LEFT, padx=(0, 10))
        
        # Toggle overlay checkbox
        self.show_overlay_var = tk.BooleanVar(value=False)
        overlay_cb = tk.Checkbutton(checkbox_frame, text="Show Overlay",
                                    variable=self.show_overlay_var,
                                    command=self.toggle_overlay,
                                    bg=THEME['bg_medium'], fg=THEME['text_secondary'],
                                    selectcolor=THEME['bg_dark'],
                                    activebackground=THEME['bg_medium'],
                                    activeforeground=THEME['accent_cyan'],
                                    font=("Segoe UI", 9))
        overlay_cb.pack(side=tk.LEFT)
        
        # Tabbed interface
        notebook = ttk.Notebook(self.root, style='Custom.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Setup tab
        setup_tab = tk.Frame(notebook, bg=THEME['bg_dark'])
        notebook.add(setup_tab, text="⚙ Setup Regions")
        self.create_setup_tab(setup_tab)
        
        # Capture tab
        capture_tab = tk.Frame(notebook, bg=THEME['bg_dark'])
        notebook.add(capture_tab, text="📊 Capture Data")
        self.create_capture_tab(capture_tab)
        
    def create_setup_tab(self, parent):
        """Create the region setup tab"""
        # Instructions
        inst_frame = tk.Frame(parent, bg=THEME['bg_light'], relief=tk.FLAT, bd=2)
        inst_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(inst_frame, text="Region Setup",
                font=("Segoe UI", 14, "bold"), bg=THEME['bg_light'],
                fg=THEME['text_primary']).pack(anchor=tk.W, padx=15, pady=(15, 5))
        
        tk.Label(inst_frame, 
                text="1. Select row and column below\n2. Click 'Show Overlay' to see the region on your game screen\n3. Drag the overlay with mouse or use arrow keys to adjust\n4. Click 'Save Config' when all regions are positioned correctly",
                font=("Segoe UI", 10), bg=THEME['bg_light'],
                fg=THEME['text_secondary'], justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 15))
        
        # Selection controls - centered (compact)
        ctrl_frame = tk.Frame(parent, bg=THEME['bg_light'])
        ctrl_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        # Container for centering
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
        
        # Region info with editable fields (expanded)
        info_frame = tk.Frame(parent, bg=THEME['bg_medium'])
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 15))
        
        tk.Label(info_frame, text="Current Region (editable):", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_medium'], fg=THEME['text_primary']).pack(pady=(15, 10))
        
        # Create entry fields for X, Y, W, H in 2x2 grid
        fields_frame = tk.Frame(info_frame, bg=THEME['bg_medium'])
        fields_frame.pack(pady=(10, 10))
        
        self.region_entries = {}
        # Layout: [X, Y] on top row, [Width, Height] on bottom row
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
        
        # Apply button - larger and centered
        apply_btn = self.create_button(info_frame, "Apply Changes", self.apply_manual_values, THEME['accent_cyan'])
        apply_btn.pack(pady=(5, 15))
        
        # Action buttons
        btn_frame = tk.Frame(parent, bg=THEME['bg_dark'])
        btn_frame.pack(pady=20)
        
        self.create_button(btn_frame, "Save Config", self.save_config,
                          THEME['success']).pack(side=tk.LEFT, padx=5)
        
        self.update_region_info()
        
    def create_capture_tab(self, parent):
        """Create the data capture tab"""
        # Control panel
        ctrl_frame = tk.Frame(parent, bg=THEME['bg_medium'])
        ctrl_frame.pack(fill=tk.X, padx=20, pady=20)
        
        btn_container = tk.Frame(ctrl_frame, bg=THEME['bg_medium'])
        btn_container.pack(pady=15)
        
        self.create_button(btn_container, "Set Season", self.set_season,
                          THEME['accent_cyan']).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_container, "📸 Capture (F9)", self.capture_once,
                          THEME['success']).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_container, "Clear All", self.clear_all,
                          THEME['warning']).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_container, "💾 Save to CSV", self.save_to_csv,
                          THEME['accent_cyan']).pack(side=tk.LEFT, padx=5)
        
        # Stats
        stats_frame = tk.Frame(parent, bg=THEME['bg_light'])
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.stats_label = tk.Label(stats_frame, text="Total Players: 0 | Captures: 0",
                                    font=("Segoe UI", 11), bg=THEME['bg_light'],
                                    fg=THEME['text_secondary'])
        self.stats_label.pack(pady=12)
        
        # Data table
        table_container = tk.Frame(parent, bg=THEME['bg_dark'])
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Create Treeview
        columns = ("Season", "IGN", "Top Score", "Total Score")
        self.tree = ttk.Treeview(table_container, columns=columns, show='headings',
                                height=20, style='Custom.Treeview')
        
        self.tree.heading("Season", text="Season")
        self.tree.heading("IGN", text="IGN (Nickname)")
        self.tree.heading("Top Score", text="Single High")
        self.tree.heading("Total Score", text="Total Score")
        
        self.tree.column("Season", width=80, anchor=tk.CENTER)
        self.tree.column("IGN", width=250)
        self.tree.column("Top Score", width=120, anchor=tk.E)
        self.tree.column("Total Score", width=120, anchor=tk.E)
        
        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click for inline editing
        self.tree.bind('<Double-1>', self.on_cell_double_click)
        
        # Status bar
        status_frame = tk.Frame(parent, bg=THEME['bg_medium'], height=35)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready. Press F9 to capture.",
                                     font=("Segoe UI", 9), bg=THEME['bg_medium'],
                                     fg=THEME['text_secondary'])
        self.status_label.pack(pady=8)
        
    def create_button(self, parent, text, command, bg_color):
        """Create themed button"""
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg=THEME['text_primary'],
                       font=("Segoe UI", 10, "bold"),
                       padx=20, pady=10,
                       relief=tk.FLAT,
                       cursor="hand2",
                       activebackground=THEME['accent_hover'],
                       activeforeground=THEME['text_primary'])
        return btn
    
    # Region selector methods
    def get_current_bbox(self):
        """Get current selected region"""
        row = self.row_var.get()
        col = self.col_var.get()
        return self.config["rows"][row][col]
    
    def set_current_bbox(self, bbox):
        """Update current region"""
        row = self.row_var.get()
        col = self.col_var.get()
        self.config["rows"][row][col] = bbox
        self.update_region_info()
    
    def toggle_always_on_top(self):
        """Toggle window always on top"""
        self.root.attributes('-topmost', self.always_on_top_var.get())
    
    def toggle_overlay(self):
        """Toggle overlay visibility"""
        if self.show_overlay_var.get():
            self.show_overlay()
        else:
            self.hide_overlay()
    
    def apply_manual_values(self, event=None):
        """Apply manually entered values to current region"""
        try:
            x = int(self.region_entries['x'].get())
            y = int(self.region_entries['y'].get())
            w = int(self.region_entries['w'].get())
            h = int(self.region_entries['h'].get())
            
            self.set_current_bbox([x, y, w, h])
            
            # Refresh overlay if visible
            if hasattr(self, 'overlay_windows') and self.overlay_windows:
                self.show_overlay()
        except ValueError:
            pass  # Ignore invalid input
    
    def update_region_info(self):
        """Update region info display and entry fields"""
        bbox = self.get_current_bbox()
        self.region_entries['x'].delete(0, tk.END)
        self.region_entries['x'].insert(0, str(bbox[0]))
        self.region_entries['y'].delete(0, tk.END)
        self.region_entries['y'].insert(0, str(bbox[1]))
        self.region_entries['w'].delete(0, tk.END)
        self.region_entries['w'].insert(0, str(bbox[2]))
        self.region_entries['h'].delete(0, tk.END)
        self.region_entries['h'].insert(0, str(bbox[3]))
    
    def on_selection_change(self):
        """Handle row/column selection change"""
        self.update_region_info()
        if self.overlay_window:
            self.show_overlay()
    
    def show_overlay(self):
        """Show all region overlays at once"""
        # Clear any existing overlays - same cleanup as hide_overlay
        if hasattr(self, 'overlay_windows'):
            for overlay in self.overlay_windows:
                if overlay:
                    # Destroy label window if it exists
                    if hasattr(overlay, 'label_win') and overlay.label_win:
                        try:
                            overlay.label_win.destroy()
                        except:
                            pass
                    # Destroy overlay
                    try:
                        overlay.destroy()
                    except:
                        pass
        
        self.overlay_windows = []
        
        # Color coding for different columns
        colors = {
            "nickname": THEME['accent_cyan'],      # Cyan for nicknames
            "single_high": '#10b981',              # Green for single high
            "total_score": '#f59e0b'               # Orange for total score
        }
        
        # Create overlay for each region
        for row_idx in range(5):
            for col_name in ["nickname", "single_high", "total_score"]:
                bbox = self.config["rows"][row_idx][col_name]
                x, y, w, h = bbox
                
                # Create text label window (above the overlay)
                label_height = 20
                label_win = tk.Toplevel(self.root)
                label_win.geometry(f"{w}x{label_height}+{x}+{y-label_height-2}")
                label_win.overrideredirect(True)
                label_win.attributes('-alpha', 0.8)
                label_win.attributes('-topmost', True)
                
                color = colors[col_name]
                col_short = {"nickname": "Nick", "single_high": "Single", "total_score": "Total"}
                label_text = f"R{row_idx+1} {col_short[col_name]}"
                
                label_frame = tk.Frame(label_win, bg=color)
                label_frame.pack(fill=tk.BOTH, expand=True)
                
                tk.Label(label_frame, text=label_text,
                        bg=color, fg=THEME['bg_dark'],
                        font=("Segoe UI", 8, "bold")).pack()
                
                # Create overlay window (now without text inside)
                overlay = tk.Toplevel(self.root)
                overlay.geometry(f"{w}x{h}+{x}+{y}")
                overlay.overrideredirect(True)
                overlay.attributes('-alpha', 0.15)  # Increased from 0.3 to 0.5
                overlay.attributes('-topmost', True)
                
                # Colored background
                frame = tk.Frame(overlay, bg=color, width=w, height=h, cursor="fleur")
                frame.pack(fill=tk.BOTH, expand=True)
                
                # Store references for dragging
                overlay.row_idx = row_idx
                overlay.col_name = col_name
                overlay.label_win = label_win  # Keep reference to label
                
                # Bind mouse drag
                frame.bind('<Button-1>', lambda e, o=overlay: self.start_drag_multi(e, o))
                frame.bind('<B1-Motion>', lambda e, o=overlay: self.do_drag_multi(e, o))
                frame.bind('<ButtonRelease-1>', self.end_drag)
                
                # Also update selection when clicking overlay (not dragging)
                overlay.click_start = None
                frame.bind('<ButtonPress-1>', lambda e, o=overlay: self.on_overlay_press(e, o))
                frame.bind('<ButtonRelease-1>', lambda e, o=overlay: self.on_overlay_release(e, o))
                
                self.overlay_windows.append(overlay)
    
    def on_overlay_press(self, event, overlay):
        """Track click start position"""
        overlay.click_start = (event.x_root, event.y_root)
    
    def on_overlay_release(self, event, overlay):
        """Handle overlay click (if not dragged)"""
        if hasattr(overlay, 'click_start') and overlay.click_start:
            # Check if this was a click (not a drag)
            dx = abs(event.x_root - overlay.click_start[0])
            dy = abs(event.y_root - overlay.click_start[1])
            
            if dx < 5 and dy < 5:  # Threshold for click vs drag
                # Auto-select this row and column
                self.row_var.set(overlay.row_idx)
                self.col_var.set(overlay.col_name)
                self.update_region_info()
            
            overlay.click_start = None
    
    def start_drag_multi(self, event, overlay):
        """Start dragging overlay in multi-overlay mode"""
        self.dragging = True
        self.drag_start = (event.x_root, event.y_root)
        self.dragging_overlay = overlay
    
    def do_drag_multi(self, event, overlay):
        """Drag overlay in multi-overlay mode"""
        if not self.dragging or self.dragging_overlay != overlay:
            return
        
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        
        # Get the bbox for this specific overlay
        row_idx = overlay.row_idx
        col_name = overlay.col_name
        bbox = self.config["rows"][row_idx][col_name]
        
        new_x = bbox[0] + dx
        new_y = bbox[1] + dy
        
        # Update config
        self.config["rows"][row_idx][col_name] = [new_x, new_y, bbox[2], bbox[3]]
        
        # Move overlay window
        overlay.geometry(f"+{new_x}+{new_y}")
        
        # Move label window too
        if hasattr(overlay, 'label_win') and overlay.label_win:
            overlay.label_win.geometry(f"+{new_x}+{new_y-22}")
        
        # Update info if this is the currently selected field
        if row_idx == self.row_var.get() and col_name == self.col_var.get():
            self.update_region_info()
        
        self.drag_start = (event.x_root, event.y_root)
    
    def end_drag(self, event):
        """End dragging"""
        self.dragging = False
    
    def adjust_position(self, dx, dy):
        """Adjust position with arrow keys"""
        bbox = self.get_current_bbox()
        self.set_current_bbox([bbox[0] + dx, bbox[1] + dy, bbox[2], bbox[3]])
        if self.overlay_window:
            self.overlay_window.geometry(f"+{bbox[0] + dx}+{bbox[1] + dy}")
    
    def hide_overlay(self):
        """Hide all overlays"""
        if hasattr(self, 'overlay_windows'):
            for overlay in self.overlay_windows:
                if overlay:
                    # Destroy label window if it exists
                    if hasattr(overlay, 'label_win') and overlay.label_win:
                        try:
                            overlay.label_win.destroy()
                        except:
                            pass
                    # Destroy overlay
                    try:
                        overlay.destroy()
                    except:
                        pass
            self.overlay_windows = []
        
        # Uncheck the toggle button
        self.show_overlay_var.set(False)
    
    def save_config(self):
        """Save configuration"""
        self.hide_overlay()
        try:
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=2)
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    # Capture methods
    def set_season(self):
        """Override season number"""
        current_msg = f"Current: Season {self.season}" if self.season else "Current: Off-Season"
        season = simpledialog.askinteger("Override Season", 
                                        f"{current_msg}\n\nEnter season number to override:",
                                        initialvalue=self.season if self.season else 1,
                                        minvalue=1, maxvalue=999)
        if season:
            self.season = season
            self.season_auto = False  # Mark as manually overridden
            start_date, end_date = self.get_season_dates(season)
            season_text = f"Season {season} ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}) [Manual]"
            self.season_label.config(text=season_text, fg=THEME['accent_cyan'])
            self.status_label.config(text=f"Season manually set to {season}.")
    
    def safe_grab(self, bbox):
        """Safely capture screen region"""
        x, y, w, h = bbox
        x = max(0, x)
        y = max(0, y)
        right = min(self.screen_w, x + w)
        bottom = min(self.screen_h, y + h)
        
        if right <= x or bottom <= y or w <= 0 or h <= 0:
            return None
        
        try:
            img = ImageGrab.grab(bbox=(x, y, right, bottom))
            return np.array(img)
        except:
            return None
    
    def preprocess_image(self, img, adaptive=True):
        """Preprocess image for OCR"""
        if img is None or img.size == 0:
            return None
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if adaptive:
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            threshold_value = self.config.get("preprocessing", {}).get("threshold", 150)
            _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
        
        kernel_size = self.config.get("preprocessing", {}).get("kernel_size", [2, 2])
        kernel = np.ones(kernel_size, np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed
    
    def extract_text_ocr(self, img, is_number=False):
        """Extract text using EasyOCR"""
        if img is None:
            return ""
        
        try:
            processed = self.preprocess_image(img, adaptive=True)
            
            if is_number:
                result = self.reader.readtext(processed, detail=0, allowlist='0123456789,')
            else:
                result = self.reader.readtext(processed, detail=0, paragraph=False)
            
            text = ''.join(result)
            
            if is_number and not text.strip():
                processed = self.preprocess_image(img, adaptive=False)
                result = self.reader.readtext(processed, detail=0, allowlist='0123456789,')
                text = ''.join(result)
            
            return text.strip()
        except:
            return ""
    
    def clean_nickname(self, text):
        """Clean nickname"""
        cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        return cleaned.strip()
    
    def clean_number(self, text, is_single_score=False):
        """Clean and convert number"""
        cleaned = re.sub(r'[^\d]', '', text)
        
        # Fix spurious leading '1' from flame icon
        if is_single_score and cleaned and len(cleaned) == 5 and cleaned[0] == '1':
            potential_fix = cleaned[1:]
            if 1000 <= int(potential_fix) <= 9999:
                cleaned = potential_fix
        
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0
    
    def capture_once(self):
        """Capture 5 rows"""
        if self.season is None:
            messagebox.showwarning("Season Not Set", "Please set the season number first!")
            return
        
        self.capture_count += 1
        self.status_label.config(text=f"Capturing... (#{self.capture_count})")
        self.root.update()
        
        batch = []
        
        for i, row_config in enumerate(self.config["rows"]):
            nick_img = self.safe_grab(row_config["nickname"])
            single_img = self.safe_grab(row_config["single_high"])
            total_img = self.safe_grab(row_config["total_score"])
            
            if nick_img is None or single_img is None or total_img is None:
                continue
            
            nickname = self.extract_text_ocr(nick_img, is_number=False)
            single_text = self.extract_text_ocr(single_img, is_number=True)
            total_text = self.extract_text_ocr(total_img, is_number=True)
            
            nickname = self.clean_nickname(nickname)
            single_score = self.clean_number(single_text, is_single_score=True)
            total_score = self.clean_number(total_text, is_single_score=False)
            
            min_nick_len = self.config.get("validation", {}).get("min_nickname_length", 2)
            
            if len(nickname) >= min_nick_len:
                batch.append({
                    "season": self.season,
                    "ign": nickname,
                    "topscore": single_score,
                    "totalscore": total_score
                })
        
        # Remove duplicates
        if batch and self.captured_data:
            recent_players = [p["ign"] for p in self.captured_data[-20:]]
            batch = [p for p in batch if p["ign"] not in recent_players]
        
        self.captured_data.extend(batch)
        self.refresh_table()
        
        self.stats_label.config(text=f"Total Players: {len(self.captured_data)} | Captures: {self.capture_count}")
        self.status_label.config(text=f"✓ Captured {len(batch)} new players. Total: {len(self.captured_data)}")
    
    def refresh_table(self):
        """Refresh data table"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for player in self.captured_data:
            self.tree.insert('', tk.END, values=(
                player["season"],
                player["ign"],
                f"{player['topscore']:,}",
                f"{player['totalscore']:,}"
            ))
    
    def on_cell_double_click(self, event):
        """Handle double-click on cell to start inline editing"""
        # Get clicked item and column
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if not item or not column:
            return
        
        # Get column index (columns are #1, #2, etc.)
        col_idx = int(column.replace('#', '')) - 1
        col_names = ["season", "ign", "topscore", "totalscore"]
        col_name = col_names[col_idx]
        
        self.start_inline_edit(item, col_idx, col_name)
    
    def start_inline_edit(self, item, col_idx, col_name):
        """Start inline editing of a cell"""
        # Close any existing editor
        self.close_editor()
        
        # Get cell bounding box
        x, y, width, height = self.tree.bbox(item, col_idx)
        
        # Get current value
        row_idx = self.tree.index(item)
        current_value = self.captured_data[row_idx][col_name]
        
        # Create entry widget
        self.edit_entry = tk.Entry(self.tree, bg=THEME['bg_light'], 
                                   fg=THEME['accent_cyan'],
                                   font=("Segoe UI", 10),
                                   insertbackground=THEME['accent_cyan'])
        self.edit_entry.insert(0, str(current_value))
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        
        # Position the entry
        self.edit_entry.place(x=x, y=y, width=width, height=height)
        
        # Store editing state
        self.editing_item = item
        self.editing_column = col_idx
        self.editing_col_name = col_name
        self.editing_row_idx = row_idx
        
        # Bind keys
        self.edit_entry.bind('<Return>', self.save_and_next)
        self.edit_entry.bind('<Escape>', lambda e: self.close_editor())
        self.edit_entry.bind('<FocusOut>', self.on_edit_focus_out)
    
    def save_and_next(self, event=None):
        """Save current edit and move to next cell"""
        self.save_current_edit()
        
        # Move to next column
        col_names = ["season", "ign", "topscore", "totalscore"]
        next_col_idx = self.editing_column + 1
        
        if next_col_idx < len(col_names):
            # Move to next column in same row
            self.start_inline_edit(self.editing_item, next_col_idx, col_names[next_col_idx])
        else:
            # Move to first column of next row
            items = self.tree.get_children()
            current_idx = items.index(self.editing_item)
            if current_idx + 1 < len(items):
                next_item = items[current_idx + 1]
                self.start_inline_edit(next_item, 0, col_names[0])
            else:
                # Last cell, just close editor
                self.close_editor()
    
    def save_current_edit(self):
        """Save the current inline edit"""
        if not self.edit_entry:
            return
        
        new_value = self.edit_entry.get().strip()
        col_name = self.editing_col_name
        
        try:
            # Validate and convert based on column type
            if col_name == "season":
                new_value = int(new_value)
            elif col_name in ["topscore", "totalscore"]:
                new_value = int(new_value.replace(',', ''))
            # ign stays as string
            
            # Update data
            self.captured_data[self.editing_row_idx][col_name] = new_value
            
            # Refresh display
            self.refresh_table()
            
        except ValueError:
            messagebox.showerror("Invalid Input", f"Please enter a valid value for {col_name}")
    
    def on_edit_focus_out(self, event):
        """Handle focus out from edit entry"""
        # Small delay to allow button clicks to register
        self.root.after(100, self.close_editor)
    
    def close_editor(self):
        """Close the inline editor"""
        if self.edit_entry:
            self.edit_entry.destroy()
            self.edit_entry = None
        self.editing_item = None
        self.editing_column = None
    
    def clear_all(self):
        """Clear all data"""
        if messagebox.askyesno("Clear All", "Clear all captured data?"):
            self.captured_data = []
            self.refresh_table()
            self.stats_label.config(text="Total Players: 0 | Captures: 0")
            self.status_label.config(text="All data cleared.")
    
    def save_to_csv(self):
        """Save to CSV"""
        if not self.captured_data:
            messagebox.showwarning("No Data", "No data to save!")
            return
        
        if self.season is None:
            messagebox.showwarning("Season Not Set", "Please set season first!")
            return
        
        df = pd.DataFrame(self.captured_data)
        df = df.sort_values("totalscore", ascending=False)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"./results/GFL2_Season{self.season}_{timestamp}.csv"
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        messagebox.showinfo("Saved", f"✓ Data saved!\n\n{filename}\n\nTotal players: {len(df)}")
        self.status_label.config(text=f"Saved {len(df)} players to {filename}")
    
    def run(self):
        """Start the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing"""
        keyboard.unhook_all()
        if hasattr(self, 'overlay_windows'):
            for overlay in self.overlay_windows:
                if overlay:
                    # Destroy label window if it exists
                    if hasattr(overlay, 'label_win') and overlay.label_win:
                        try:
                            overlay.label_win.destroy()
                        except:
                            pass
                    # Destroy overlay
                    try:
                        overlay.destroy()
                    except:
                        pass
        self.root.destroy()

if __name__ == "__main__":
    app = GFL2Scanner()
    app.run()
