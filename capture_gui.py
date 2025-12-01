"""
GFL2 Leaderboard OCR Capture Tool - GUI Version
Visual interface with data review and editing before saving
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
from datetime import datetime
import keyboard
import warnings

# Suppress harmless PyTorch warning about pin_memory on CPU
warnings.filterwarnings('ignore', message='.*pin_memory.*')

class GFL2CaptureGUI:
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
        
        # Create results directory
        os.makedirs("./results", exist_ok=True)
        
        # Setup GUI
        self.root = tk.Tk()
        self.root.title("GFL2 Leaderboard OCR Capture")
        self.root.geometry("1000x700")
        self.setup_ui()
        
        # Register hotkey
        keyboard.add_hotkey('f9', self.capture_once)
        
    def setup_ui(self):
        """Setup the main UI"""
        # Header
        header = tk.Frame(self.root, bg='#2c3e50', height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="GFL2 Leaderboard OCR Capture", 
                font=("Arial", 20, "bold"), bg='#2c3e50', fg='white').pack(pady=10)
        
        info_frame = tk.Frame(header, bg='#2c3e50')
        info_frame.pack()
        
        tk.Label(info_frame, text="Press F9 to capture | ", 
                font=("Arial", 10), bg='#2c3e50', fg='#ecf0f1').pack(side=tk.LEFT)
        
        self.season_label = tk.Label(info_frame, text="Season: Not Set", 
                                     font=("Arial", 10, "bold"), bg='#2c3e50', fg='#f39c12')
        self.season_label.pack(side=tk.LEFT)
        
        # Control panel
        control_frame = tk.Frame(self.root, bg='#34495e', height=60)
        control_frame.pack(fill=tk.X)
        control_frame.pack_propagate(False)
        
        btn_frame = tk.Frame(control_frame, bg='#34495e')
        btn_frame.pack(expand=True)
        
        tk.Button(btn_frame, text="Set Season", command=self.set_season,
                 bg='#3498db', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Capture (F9)", command=self.capture_once,
                 bg='#27ae60', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Clear All", command=self.clear_all,
                 bg='#e67e22', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Save to CSV", command=self.save_to_csv,
                 bg='#2ecc71', fg='white', font=("Arial", 11, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        # Stats
        stats_frame = tk.Frame(self.root, bg='#ecf0f1', height=40)
        stats_frame.pack(fill=tk.X)
        stats_frame.pack_propagate(False)
        
        self.stats_label = tk.Label(stats_frame, text="Total Players: 0 | Captures: 0",
                                    font=("Arial", 10), bg='#ecf0f1', fg='#2c3e50')
        self.stats_label.pack(pady=10)
        
        # Data table
        table_frame = tk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create Treeview
        columns = ("Season", "IGN", "Top Score", "Total Score")
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Define headings
        self.tree.heading("Season", text="Season")
        self.tree.heading("IGN", text="IGN (Nickname)")
        self.tree.heading("Top Score", text="Single High")
        self.tree.heading("Total Score", text="Total Score")
        
        # Define column widths
        self.tree.column("Season", width=80, anchor=tk.CENTER)
        self.tree.column("IGN", width=250)
        self.tree.column("Top Score", width=120, anchor=tk.E)
        self.tree.column("Total Score", width=120, anchor=tk.E)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Double-click to edit
        self.tree.bind('<Double-1>', self.edit_row)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg='#95a5a6', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready. Press F9 to capture or click 'Set Season' to begin.",
                                     font=("Arial", 9), bg='#95a5a6', fg='white')
        self.status_label.pack(pady=5)
        
    def set_season(self):
        """Set the season number"""
        season = simpledialog.askinteger("Set Season", "Enter season number:", 
                                         initialvalue=self.season if self.season else 1,
                                         minvalue=1, maxvalue=999)
        if season:
            self.season = season
            self.season_label.config(text=f"Season: {season}")
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
        """Capture 5 rows from leaderboard"""
        if self.season is None:
            messagebox.showwarning("Season Not Set", "Please set the season number first!")
            return
        
        self.capture_count += 1
        self.status_label.config(text=f"Capturing... (Capture #{self.capture_count})")
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
        
        # Add to data and update table
        self.captured_data.extend(batch)
        self.refresh_table()
        
        self.stats_label.config(text=f"Total Players: {len(self.captured_data)} | Captures: {self.capture_count}")
        self.status_label.config(text=f"Captured {len(batch)} new players. Total: {len(self.captured_data)}")
    
    def refresh_table(self):
        """Refresh the data table"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add all data
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
        
        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Player Data")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Edit Player Data", font=("Arial", 14, "bold")).pack(pady=10)
        
        form_frame = tk.Frame(dialog)
        form_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(form_frame, text="Season:").grid(row=0, column=0, sticky=tk.W, pady=5)
        season_entry = tk.Entry(form_frame, width=30)
        season_entry.insert(0, str(player["season"]))
        season_entry.grid(row=0, column=1, pady=5)
        
        tk.Label(form_frame, text="IGN:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ign_entry = tk.Entry(form_frame, width=30)
        ign_entry.insert(0, player["ign"])
        ign_entry.grid(row=1, column=1, pady=5)
        
        tk.Label(form_frame, text="Top Score:").grid(row=2, column=0, sticky=tk.W, pady=5)
        top_entry = tk.Entry(form_frame, width=30)
        top_entry.insert(0, str(player["topscore"]))
        top_entry.grid(row=2, column=1, pady=5)
        
        tk.Label(form_frame, text="Total Score:").grid(row=3, column=0, sticky=tk.W, pady=5)
        total_entry = tk.Entry(form_frame, width=30)
        total_entry.insert(0, str(player["totalscore"]))
        total_entry.grid(row=3, column=1, pady=5)
        
        def save_edit():
            try:
                self.captured_data[idx] = {
                    "season": int(season_entry.get()),
                    "ign": ign_entry.get().strip(),
                    "topscore": int(top_entry.get().replace(',', '')),
                    "totalscore": int(total_entry.get().replace(',', ''))
                }
                self.refresh_table()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for season and scores.")
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Save", command=save_edit, bg='#27ae60', fg='white',
                 font=("Arial", 10, "bold"), padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, bg='#95a5a6', fg='white',
                 font=("Arial", 10, "bold"), padx=20, pady=5).pack(side=tk.LEFT, padx=5)
    
    def clear_all(self):
        """Clear all captured data"""
        if messagebox.askyesno("Clear All", "Are you sure you want to clear all captured data?"):
            self.captured_data = []
            self.refresh_table()
            self.stats_label.config(text="Total Players: 0 | Captures: 0")
            self.status_label.config(text="All data cleared.")
    
    def save_to_csv(self):
        """Save data to CSV"""
        if not self.captured_data:
            messagebox.showwarning("No Data", "No data to save!")
            return
        
        if self.season is None:
            messagebox.showwarning("Season Not Set", "Please set the season number first!")
            return
        
        # Create DataFrame
        df = pd.DataFrame(self.captured_data)
        
        # Sort by total score (descending)
        df = df.sort_values("totalscore", ascending=False)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"./results/GFL2_Season{self.season}_{timestamp}.csv"
        
        # Save to CSV
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        messagebox.showinfo("Saved", f"Data saved to:\n{filename}\n\nTotal players: {len(df)}")
        self.status_label.config(text=f"Saved {len(df)} players to {filename}")
    
    def run(self):
        """Start the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing"""
        keyboard.unhook_all()
        self.root.destroy()

if __name__ == "__main__":
    app = GFL2CaptureGUI()
    app.run()
