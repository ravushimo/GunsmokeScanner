"""
GFL2 Visual Region Selector - GUI Tool
Shows semi-transparent overlays on screen to visually adjust capture regions
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import pyautogui
from PIL import Image, ImageGrab, ImageTk
import cv2
import numpy as np

class VisualRegionSelector:
    def __init__(self):
        # Load existing config or create default
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
        except:
            messagebox.showerror("Error", "config.json not found!\nRun selector.py or manual_config.py first.")
            exit()
        
        self.screen_w, self.screen_h = pyautogui.size()
        self.current_row = 0
        self.current_col = "nickname"
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("GFL2 Visual Region Selector")
        self.root.geometry("800x900")
        self.root.configure(bg='#2b2b2b')
        
        self.setup_ui()
        self.overlay_window = None
        
    def setup_ui(self):
        """Setup the control panel UI"""
        # Title
        title = tk.Label(self.root, text="GFL2 Visual Region Selector", 
                        font=("Arial", 16, "bold"), bg='#2b2b2b', fg='white')
        title.pack(pady=10)
        
        # Instructions
        instructions = tk.Label(self.root, 
            text="1. Select row and column below\n2. Click 'Show Overlay' to see current region\n3. Adjust using arrow keys or buttons\n4. Click 'Capture Preview' to see what OCR will read\n5. Save when satisfied",
            font=("Arial", 10), bg='#2b2b2b', fg='#cccccc', justify=tk.LEFT)
        instructions.pack(pady=10)
        
        # Selection Frame
        select_frame = tk.Frame(self.root, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        select_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Row selection
        tk.Label(select_frame, text="Select Row:", bg='#3b3b3b', fg='white', font=("Arial", 11, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        row_frame = tk.Frame(select_frame, bg='#3b3b3b')
        row_frame.grid(row=0, column=1, padx=10, pady=10)
        
        self.row_var = tk.IntVar(value=0)
        for i in range(5):
            tk.Radiobutton(row_frame, text=f"Row {i+1}", variable=self.row_var, value=i,
                          bg='#3b3b3b', fg='white', selectcolor='#5b5b5b',
                          command=self.on_selection_change).pack(side=tk.LEFT, padx=5)
        
        # Column selection
        tk.Label(select_frame, text="Select Column:", bg='#3b3b3b', fg='white', font=("Arial", 11, "bold")).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        col_frame = tk.Frame(select_frame, bg='#3b3b3b')
        col_frame.grid(row=1, column=1, padx=10, pady=10)
        
        self.col_var = tk.StringVar(value="nickname")
        cols = [("Nickname", "nickname"), ("Single High", "single_high"), ("Total Score", "total_score")]
        for text, value in cols:
            tk.Radiobutton(col_frame, text=text, variable=self.col_var, value=value,
                          bg='#3b3b3b', fg='white', selectcolor='#5b5b5b',
                          command=self.on_selection_change).pack(side=tk.LEFT, padx=5)
        
        # Current region info
        info_frame = tk.Frame(self.root, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        info_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(info_frame, text="Current Region:", bg='#3b3b3b', fg='white', font=("Arial", 11, "bold")).pack(pady=5)
        self.region_info = tk.Label(info_frame, text="", bg='#3b3b3b', fg='#00ff00', font=("Courier", 10))
        self.region_info.pack(pady=5)
        
        # Action buttons
        btn_frame = tk.Frame(self.root, bg='#2b2b2b')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Show Overlay", command=self.show_overlay,
                 bg='#4a9eff', fg='white', font=("Arial", 11, "bold"), 
                 padx=20, pady=10).grid(row=0, column=0, padx=5)
        
        tk.Button(btn_frame, text="Capture Preview", command=self.capture_preview,
                 bg='#ff9a4a', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=10).grid(row=0, column=1, padx=5)
        
        tk.Button(btn_frame, text="Hide Overlay", command=self.hide_overlay,
                 bg='#6b6b6b', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=10).grid(row=0, column=2, padx=5)
        
        # Adjustment controls
        adj_frame = tk.LabelFrame(self.root, text="Adjust Position & Size", 
                                 bg='#3b3b3b', fg='white', font=("Arial", 11, "bold"),
                                 relief=tk.RAISED, bd=2)
        adj_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Position controls
        pos_frame = tk.Frame(adj_frame, bg='#3b3b3b')
        pos_frame.pack(pady=10)
        
        tk.Label(pos_frame, text="Position:", bg='#3b3b3b', fg='white', font=("Arial", 10, "bold")).grid(row=0, column=1, pady=5)
        
        tk.Button(pos_frame, text="↑", command=lambda: self.adjust('y', -1),
                 width=5, height=2).grid(row=1, column=1, padx=2, pady=2)
        tk.Button(pos_frame, text="←", command=lambda: self.adjust('x', -1),
                 width=5, height=2).grid(row=2, column=0, padx=2, pady=2)
        tk.Button(pos_frame, text="→", command=lambda: self.adjust('x', 1),
                 width=5, height=2).grid(row=2, column=2, padx=2, pady=2)
        tk.Button(pos_frame, text="↓", command=lambda: self.adjust('y', 1),
                 width=5, height=2).grid(row=3, column=1, padx=2, pady=2)
        
        # Size controls
        size_frame = tk.Frame(adj_frame, bg='#3b3b3b')
        size_frame.pack(pady=10)
        
        tk.Label(size_frame, text="Width:", bg='#3b3b3b', fg='white').grid(row=0, column=0, padx=5)
        tk.Button(size_frame, text="-", command=lambda: self.adjust('w', -5), width=5).grid(row=0, column=1, padx=2)
        tk.Button(size_frame, text="+", command=lambda: self.adjust('w', 5), width=5).grid(row=0, column=2, padx=2)
        
        tk.Label(size_frame, text="Height:", bg='#3b3b3b', fg='white').grid(row=1, column=0, padx=5, pady=5)
        tk.Button(size_frame, text="-", command=lambda: self.adjust('h', -5), width=5).grid(row=1, column=1, padx=2, pady=5)
        tk.Button(size_frame, text="+", command=lambda: self.adjust('h', 5), width=5).grid(row=1, column=2, padx=2, pady=5)
        
        # Step size
        step_frame = tk.Frame(adj_frame, bg='#3b3b3b')
        step_frame.pack(pady=5)
        tk.Label(step_frame, text="Step Size:", bg='#3b3b3b', fg='white').pack(side=tk.LEFT, padx=5)
        self.step_var = tk.IntVar(value=5)
        for val in [1, 5, 10]:
            tk.Radiobutton(step_frame, text=str(val), variable=self.step_var, value=val,
                          bg='#3b3b3b', fg='white', selectcolor='#5b5b5b').pack(side=tk.LEFT, padx=5)
        
        # Preview image
        preview_frame = tk.LabelFrame(self.root, text="Capture Preview", 
                                     bg='#3b3b3b', fg='white', font=("Arial", 11, "bold"))
        preview_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.preview_label = tk.Label(preview_frame, bg='#2b2b2b', text="Click 'Capture Preview' to see region")
        self.preview_label.pack(pady=10, expand=True, fill=tk.BOTH)
        
        # Save/Exit buttons
        bottom_frame = tk.Frame(self.root, bg='#2b2b2b')
        bottom_frame.pack(pady=10)
        
        tk.Button(bottom_frame, text="Save Config", command=self.save_config,
                 bg='#4ade80', fg='black', font=("Arial", 12, "bold"),
                 padx=30, pady=10).pack(side=tk.LEFT, padx=10)
        
        tk.Button(bottom_frame, text="Exit", command=self.root.quit,
                 bg='#ef4444', fg='white', font=("Arial", 12, "bold"),
                 padx=30, pady=10).pack(side=tk.LEFT, padx=10)
        
        # Bind keyboard shortcuts
        self.root.bind('<Up>', lambda e: self.adjust('y', -1))
        self.root.bind('<Down>', lambda e: self.adjust('y', 1))
        self.root.bind('<Left>', lambda e: self.adjust('x', -1))
        self.root.bind('<Right>', lambda e: self.adjust('x', 1))
        self.root.bind('<space>', lambda e: self.capture_preview())
        
        self.update_region_info()
    
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
    
    def update_region_info(self):
        """Update region info display"""
        bbox = self.get_current_bbox()
        text = f"X: {bbox[0]}  Y: {bbox[1]}  Width: {bbox[2]}  Height: {bbox[3]}"
        self.region_info.config(text=text)
    
    def on_selection_change(self):
        """Handle row/column selection change"""
        self.update_region_info()
        if self.overlay_window:
            self.show_overlay()  # Refresh overlay
    
    def adjust(self, param, delta):
        """Adjust region parameter"""
        bbox = self.get_current_bbox()
        x, y, w, h = bbox
        
        step = self.step_var.get()
        delta = delta * step
        
        if param == 'x':
            x += delta
        elif param == 'y':
            y += delta
        elif param == 'w':
            w = max(50, w + delta)
        elif param == 'h':
            h = max(20, h + delta)
        
        self.set_current_bbox([x, y, w, h])
        
        # Update overlay if visible
        if self.overlay_window:
            self.show_overlay()
    
    def show_overlay(self):
        """Show semi-transparent overlay on screen"""
        if self.overlay_window:
            self.overlay_window.destroy()
        
        bbox = self.get_current_bbox()
        x, y, w, h = bbox
        
        # Create overlay window
        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes('-alpha', 0.3)
        self.overlay_window.attributes('-topmost', True)
        
        # Red background
        frame = tk.Frame(self.overlay_window, bg='red', width=w, height=h)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Label
        row = self.row_var.get()
        col = self.col_var.get()
        label = tk.Label(frame, text=f"Row {row+1}\n{col}", 
                        bg='red', fg='white', font=("Arial", 14, "bold"))
        label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    def hide_overlay(self):
        """Hide overlay window"""
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
    
    def capture_preview(self):
        """Capture and display current region"""
        bbox = self.get_current_bbox()
        x, y, w, h = bbox
        
        try:
            img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
            
            # Resize for display (max 400px wide)
            display_w = min(400, w)
            display_h = int(h * (display_w / w))
            img_display = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img_display)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo  # Keep reference
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        self.hide_overlay()
        
        try:
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=2)
            
            messagebox.showinfo("Success", "Configuration saved!\n\nRun 'python validator.py' to verify all regions,\nthen 'python capture.py' to start capturing.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()
        self.hide_overlay()

if __name__ == "__main__":
    app = VisualRegionSelector()
    app.run()
