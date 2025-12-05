import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import webbrowser
import threading
from src.constants import THEME, APP_VERSION
from src.config import ConfigManager
from src.core.ocr import OCRProcessor
from src.core.season import SeasonManager
from src.core.updater import UpdateChecker
from src.ui.components.overlay import OverlayManager
from src.ui.tabs.setup import SetupTab
from src.ui.tabs.capture import CaptureTab
from src.ui.tabs.upload import UploadTab
from src.ui.styles import setup_styles

class GunsmokeApp:
    def __init__(self):
        self.config_manager = ConfigManager()
        
        # Initialize Core components
        self.season_manager = SeasonManager()
        self.ocr_processor = OCRProcessor(self.config_manager.get("ocr_languages"))
        self.updater = UpdateChecker()
        
        self.root = tk.Tk()
        self.root.title(f"Gunsmoke Scanner v{APP_VERSION} - Leaderboard Scanner for gunsmoke.app")
        self.root.geometry("800x1000")
        self.root.configure(bg=THEME['bg_dark'])
        
        self.overlay_manager = OverlayManager(self.root, self.config_manager)
        
        setup_styles()
        self.setup_ui()
        
        # Register global hotkey
        try:
            keyboard.add_hotkey('f9', self.capture_tab.start_capture_thread)
        except Exception as e:
            print(f"Failed to register hotkey: {e}")
            
        # Check for updates in background
        self.root.after(1000, self.check_updates)

    def check_updates(self):
        def _check():
            has_update, version, url = self.updater.check_for_updates()
            if has_update:
                self.root.after(0, lambda: self.show_update_banner(version, url))
        
        threading.Thread(target=_check, daemon=True).start()

    def show_update_banner(self, version, url):
        banner = tk.Frame(self.root, bg=THEME['accent_cyan'], height=30)
        banner.pack(side=tk.TOP, fill=tk.X, before=self.header) # Pack at the very top
        banner.pack_propagate(False)
        
        msg = tk.Label(banner, text=f"✨ New version available: {version}", 
                      bg=THEME['accent_cyan'], fg='#000000', font=("Segoe UI", 9, "bold"),
                      cursor="hand2")
        msg.pack(side=tk.LEFT, padx=20, pady=5)
        msg.bind("<Button-1>", lambda e: webbrowser.open(url))
        
        close = tk.Label(banner, text="✕", bg=THEME['accent_cyan'], fg='#000000',
                        font=("Segoe UI", 9, "bold"), cursor="hand2")
        close.pack(side=tk.RIGHT, padx=20)
        close.bind("<Button-1>", lambda e: banner.destroy())

    def setup_ui(self):
        # Header
        self.header = tk.Frame(self.root, bg=THEME['bg_medium'], height=70)
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)
        
        # Logo
        tk.Label(self.header, text="⚡ Gunsmoke Scanner", font=("Segoe UI", 18, "bold"),
                bg=THEME['bg_medium'], fg=THEME['text_primary']).pack(side=tk.LEFT, padx=20)
        
        # Right controls (simplified)
        controls = tk.Frame(self.header, bg=THEME['bg_medium'])
        controls.pack(side=tk.RIGHT, padx=20)
        
        # Link to website
        link_label = tk.Label(controls, text="gunsmoke.app ↗", 
                             bg=THEME['bg_medium'], fg=THEME['accent_cyan'],
                             font=("Segoe UI", 10, "underline"), cursor="hand2")
        link_label.pack(side=tk.TOP, anchor=tk.E, pady=(0, 5))
        link_label.bind("<Button-1>", lambda e: webbrowser.open("https://gunsmoke.app/frontpage"))
        
        # Toggles Container
        toggles_frame = tk.Frame(controls, bg=THEME['bg_medium'])
        toggles_frame.pack(side=tk.TOP, anchor=tk.E)

        # Always on top
        self.top_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toggles_frame, text="Always on Top", variable=self.top_var,
                      command=self.toggle_top, bg=THEME['bg_medium'], fg=THEME['text_primary'],
                      selectcolor=THEME['bg_dark'], activebackground=THEME['bg_medium']).pack(side=tk.LEFT)
        self.toggle_top()
        
        # Show Overlay
        self.overlay_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toggles_frame, text="Show Overlay", variable=self.overlay_var,
                      command=self.overlay_manager.toggle, bg=THEME['bg_medium'], fg=THEME['text_primary'],
                      selectcolor=THEME['bg_dark'], activebackground=THEME['bg_medium']).pack(side=tk.LEFT, padx=10)

        # Tabs
        notebook = ttk.Notebook(self.root, style='Custom.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)
        
        self.setup_tab = SetupTab(notebook, self.config_manager, self.overlay_manager)
        notebook.add(self.setup_tab, text="⚙ Setup Regions")
        
        self.capture_tab = CaptureTab(notebook, self.config_manager, self.ocr_processor, self.season_manager)
        notebook.add(self.capture_tab, text="📊 Capture Data")
        
        self.upload_tab = UploadTab(notebook, self.config_manager)
        notebook.add(self.upload_tab, text="🌐 Upload")

    def toggle_top(self):
        self.root.attributes('-topmost', self.top_var.get())

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        try:
            keyboard.unhook_all()
        except: pass
        self.overlay_manager.hide()
        self.root.destroy()
