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
from PIL import ImageGrab, Image, ImageTk
import easyocr
import pandas as pd
import re
import os
from datetime import datetime
import keyboard
import warnings

# Suppress harmless PyTorch warning about pin_memory on CPU
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
        # Load config
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
        except:
            messagebox.showerror("Error", "config.json not found!")
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
        self.season = None
        
        # Region selector state
        self.overlay_window = None
        self.current_row = 0
        self.current_col = "nickname"
        self.dragging = False
        self.drag_start = None
        
        # Create results directory
        os.makedirs("./results", exist_ok=True)
        
        # Setup main window
        self.root = tk.Tk()
        self.root.title("GFL2 Leaderboard Scanner - gunsmoke.app")
        self.root.geometry("1200x600")
        self.root.configure(bg=THEME['bg_dark'])
        
        # Apply theme to ttk styles
        self.setup_styles()
        
        # Create UI
        self.setup_ui()
        
        # Register hotkey
        keyboard.add_hotkey('f9', self.capture_once)
        
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
                       padding=[20, 10],
                       borderwidth=0,
                       font=('Segoe UI', 11, 'bold'))
        style.map('Custom.TNotebook.Tab',
                 background=[('selected', THEME['bg_light'])],
                 foreground=[('selected', THEME['accent_cyan'])])
        
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
        right_controls.pack(side=tk.RIGHT, padx=20)
        
        # Always on top checkbox
        self.always_on_top_var = tk.BooleanVar(value=False)
        on_top_cb = tk.Checkbutton(right_controls, text="Always on Top",
                                   variable=self.always_on_top_var,
                                   command=self.toggle_always_on_top,
                                   bg=THEME['bg_medium'], fg=THEME['text_secondary'],
                                   selectcolor=THEME['bg_dark'],
                                   activebackground=THEME['bg_medium'],
                                   activeforeground=THEME['accent_cyan'],
                                   font=("Segoe UI", 9))
        on_top_cb.pack(side=tk.TOP, anchor=tk.E, pady=(0, 5))
        
        self.season_label = tk.Label(right_controls, text="Season: Not Set",
                                     font=("Segoe UI", 12, "bold"), bg=THEME['bg_medium'],
                                     fg=THEME['warning'])
        self.season_label.pack(side=tk.TOP, anchor=tk.E)
        
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
        
        # Selection controls
        ctrl_frame = tk.Frame(parent, bg=THEME['bg_light'])
        ctrl_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Row selection
        row_frame = tk.Frame(ctrl_frame, bg=THEME['bg_light'])
        row_frame.pack(side=tk.LEFT, padx=20, pady=15)
        
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
        col_frame = tk.Frame(ctrl_frame, bg=THEME['bg_light'])
        col_frame.pack(side=tk.LEFT, padx=20, pady=15)
        
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
        
        # Region info with editable fields
        info_frame = tk.Frame(parent, bg=THEME['bg_medium'])
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(info_frame, text="Current Region (editable):", font=("Segoe UI", 11, "bold"),
                bg=THEME['bg_medium'], fg=THEME['text_primary']).pack(pady=(10, 5))
        
        # Create entry fields for X, Y, W, H
        fields_frame = tk.Frame(info_frame, bg=THEME['bg_medium'])
        fields_frame.pack(pady=(5, 10))
        
        self.region_entries = {}
        labels = [("X:", "x"), ("Y:", "y"), ("Width:", "w"), ("Height:", "h")]
        
        for i, (label_text, field_name) in enumerate(labels):
            field_container = tk.Frame(fields_frame, bg=THEME['bg_medium'])
            field_container.pack(side=tk.LEFT, padx=10)
            
            tk.Label(field_container, text=label_text, bg=THEME['bg_medium'],
                    fg=THEME['text_secondary'], font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 5))
            
            entry = tk.Entry(field_container, width=8, bg=THEME['bg_light'],
                           fg=THEME['text_primary'], font=("Consolas", 10),
                           insertbackground=THEME['accent_cyan'])
            entry.pack(side=tk.LEFT)
            entry.bind('<Return>', self.apply_manual_values)
            entry.bind('<FocusOut>', self.apply_manual_values)
            
            self.region_entries[field_name] = entry
        
        # Apply button
        apply_btn = self.create_button(fields_frame, "Apply", self.apply_manual_values, THEME['accent_cyan'])
        apply_btn.pack(side=tk.LEFT, padx=10)
        
        # Action buttons
        btn_frame = tk.Frame(parent, bg=THEME['bg_dark'])
        btn_frame.pack(pady=20)
        
        self.create_button(btn_frame, "Show Overlay", self.show_overlay, 
                          THEME['accent_cyan']).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_frame, "Hide Overlay", self.hide_overlay,
                          THEME['bg_medium']).pack(side=tk.LEFT, padx=5)
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
        
        self.tree.bind('<Double-1>', self.edit_row)
        
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
        # Clear any existing overlays
        if hasattr(self, 'overlay_windows'):
            for win in self.overlay_windows:
                if win:
                    win.destroy()
        
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
                label_win.attributes('-alpha', 0.9)
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
                overlay.attributes('-alpha', 0.2)  # Increased from 0.3 to 0.5
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
                
                self.overlay_windows.append(overlay)
    
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
            for win in self.overlay_windows:
                if win:
                    try:
                        win.destroy()
                    except:
                        pass
            self.overlay_windows = []
    
    def save_config(self):
        """Save configuration"""
        self.hide_overlay()
        try:
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=2)
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    # Capture methods (same as before but with theme updates)
    def set_season(self):
        """Set season number"""
        season = simpledialog.askinteger("Set Season", "Enter season number:",
                                        initialvalue=self.season if self.season else 1,
                                        minvalue=1, maxvalue=999)
        if season:
            self.season = season
            self.season_label.config(text=f"Season: {season}", fg=THEME['accent_cyan'])
            self.status_label.config(text=f"Season {season} set. Ready to capture.")
    
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
    
    def edit_row(self, event):
        """Edit selected row"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        idx = self.tree.index(item)
        player = self.captured_data[idx]
        
        # Create edit dialog with theme
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Player Data")
        dialog.geometry("450x300")
        dialog.configure(bg=THEME['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Edit Player Data", font=("Segoe UI", 16, "bold"),
                bg=THEME['bg_dark'], fg=THEME['text_primary']).pack(pady=15)
        
        form_frame = tk.Frame(dialog, bg=THEME['bg_dark'])
        form_frame.pack(pady=10, padx=30, fill=tk.BOTH, expand=True)
        
        fields = [
            ("Season:", str(player["season"])),
            ("IGN:", player["ign"]),
            ("Top Score:", str(player["topscore"])),
            ("Total Score:", str(player["totalscore"]))
        ]
        
        entries = []
        for i, (label, value) in enumerate(fields):
            tk.Label(form_frame, text=label, bg=THEME['bg_dark'],
                    fg=THEME['text_secondary'], font=("Segoe UI", 10)).grid(row=i, column=0, sticky=tk.W, pady=8)
            entry = tk.Entry(form_frame, width=30, bg=THEME['bg_light'],
                           fg=THEME['text_primary'], font=("Segoe UI", 10),
                           insertbackground=THEME['accent_cyan'])
            entry.insert(0, value)
            entry.grid(row=i, column=1, pady=8, padx=(10, 0))
            entries.append(entry)
        
        def save_edit():
            try:
                self.captured_data[idx] = {
                    "season": int(entries[0].get()),
                    "ign": entries[1].get().strip(),
                    "topscore": int(entries[2].get().replace(',', '')),
                    "totalscore": int(entries[3].get().replace(',', ''))
                }
                self.refresh_table()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers.")
        
        btn_frame = tk.Frame(dialog, bg=THEME['bg_dark'])
        btn_frame.pack(pady=15)
        
        self.create_button(btn_frame, "Save", save_edit, THEME['success']).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_frame, "Cancel", dialog.destroy, THEME['bg_medium']).pack(side=tk.LEFT, padx=5)
    
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
