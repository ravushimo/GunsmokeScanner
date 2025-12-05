import json
import os
import pyautogui
from datetime import datetime
from src.constants import DEFAULT_CONFIG

CONFIG_FILE = "config.json"

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.load_config()

    def load_config(self):
        """Load config or create default if not exists"""
        if not os.path.exists(CONFIG_FILE):
            self.create_default_config()
        else:
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"Failed to load config.json: {e}")
                self.create_default_config()

    def create_default_config(self):
        """Create default config.json with placeholder values"""
        # Use screen center for default regions
        screen_w, screen_h = pyautogui.size()
        center_x = screen_w // 2
        center_y = screen_h // 2
        
        # Start with base default config
        self.config = DEFAULT_CONFIG.copy()
        self.config["screen_resolution"] = [screen_w, screen_h]
        self.config["rows"] = []
        
        # Create 5 rows with placeholder positions
        for i in range(5):
            row_y = center_y + (i * 60) - 120  # Spread rows vertically
            self.config["rows"].append({
                "nickname": [center_x - 400, row_y, 300, 50],
                "single_high": [center_x - 50, row_y, 200, 50],
                "total_score": [center_x + 200, row_y, 200, 50]
            })
        
        # Add metadata
        self.config["metadata"] = {
            "generated_by": "gunsmoke_scanner_default",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolution": f"{screen_w}x{screen_h}",
            "note": "Default configuration - please adjust regions in Setup tab"
        }
        
        self.save_config()

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
