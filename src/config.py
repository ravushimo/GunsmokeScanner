import json
import os
from datetime import datetime

import pyautogui

from src.constants import (
    DEFAULT_CONFIG,
    DEFAULT_UI,
    GACHA_DEFAULT_PREPROCESSING,
    GACHA_EXTRA_REGIONS,
    GACHA_ROW_COLUMNS,
)

CONFIG_FILE = "config.json"


def _default_gacha_block(screen_w: int, screen_h: int) -> dict:
    """Placeholder Access Records regions centered on screen."""
    center_x = screen_w // 2
    center_y = screen_h // 2
    # Rough layout matching the Access Records table proportions.
    col_widths = {
        "purchase_time": 200,
        "purchase_source": 180,
        "type": 90,
        "name": 260,
    }
    col_x = {
        "purchase_time": center_x - 360,
        "purchase_source": center_x - 140,
        "type": center_x + 60,
        "name": center_x + 170,
    }
    row_h = 36
    row_gap = 42
    first_row_y = center_y - 110

    rows = []
    for i in range(6):
        row_y = first_row_y + i * row_gap
        rows.append(
            {
                col: [col_x[col], row_y, col_widths[col], row_h]
                for col in GACHA_ROW_COLUMNS
            }
        )

    page_y = first_row_y + 6 * row_gap + 20
    return {
        "rows": rows,
        "page_number": [center_x - 20, page_y, 40, 32],
        "btn_prev": [center_x - 70, page_y, 36, 32],
        "btn_next": [center_x + 30, page_y, 36, 32],
        "click_delay_ms": 150,
        "ocr_settle_ms": 100,
        "preprocessing": dict(GACHA_DEFAULT_PREPROCESSING),
    }


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
                return
            self.ensure_gacha_config()
            self.ensure_ui_config()

    def create_default_config(self):
        """Create default config.json with placeholder values"""
        screen_w, screen_h = pyautogui.size()
        center_x = screen_w // 2
        center_y = screen_h // 2

        self.config = DEFAULT_CONFIG.copy()
        self.config["ui"] = {
            "mode": DEFAULT_UI["mode"],
            "last_tab": dict(DEFAULT_UI["last_tab"]),
        }
        self.config["screen_resolution"] = [screen_w, screen_h]
        self.config["rows"] = []

        for i in range(5):
            row_y = center_y + (i * 60) - 120
            self.config["rows"].append(
                {
                    "nickname": [center_x - 400, row_y, 300, 50],
                    "single_high": [center_x - 50, row_y, 200, 50],
                    "total_score": [center_x + 200, row_y, 200, 50],
                }
            )

        self.config["gacha"] = _default_gacha_block(screen_w, screen_h)

        self.config["metadata"] = {
            "generated_by": "gunsmoke_scanner_default",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolution": f"{screen_w}x{screen_h}",
            "note": "Default configuration - please adjust regions in Setup tab",
        }

        self.save_config()

    def ensure_gacha_config(self):
        """Migrate older configs that lack the gacha block."""
        if "gacha" in self.config and isinstance(self.config["gacha"], dict):
            gacha = self.config["gacha"]
            changed = False
            if "rows" not in gacha or len(gacha.get("rows", [])) != 6:
                screen_w, screen_h = pyautogui.size()
                self.config["gacha"] = _default_gacha_block(screen_w, screen_h)
                self.save_config()
                return
            for key in GACHA_EXTRA_REGIONS:
                if key not in gacha:
                    screen_w, screen_h = pyautogui.size()
                    defaults = _default_gacha_block(screen_w, screen_h)
                    gacha[key] = defaults[key]
                    changed = True
            for key in ("click_delay_ms", "ocr_settle_ms", "preprocessing"):
                if key not in gacha:
                    defaults = _default_gacha_block(*pyautogui.size())
                    gacha[key] = defaults[key]
                    changed = True
            # Migrate previous stock defaults → current recommended defaults
            if gacha.get("click_delay_ms") in (800, 270):
                gacha["click_delay_ms"] = 150
                changed = True
            if gacha.get("ocr_settle_ms") in (500, 170):
                gacha["ocr_settle_ms"] = 100
                changed = True
            if changed:
                self.save_config()
            return

        screen_w, screen_h = pyautogui.size()
        self.config["gacha"] = _default_gacha_block(screen_w, screen_h)
        self.save_config()

    def get_gacha(self) -> dict:
        self.ensure_gacha_config()
        return self.config["gacha"]

    def ensure_ui_config(self) -> None:
        """Ensure ui.mode / ui.last_tab exist with valid values."""
        ui = self.config.get("ui")
        changed = False
        if not isinstance(ui, dict):
            self.config["ui"] = {
                "mode": DEFAULT_UI["mode"],
                "last_tab": dict(DEFAULT_UI["last_tab"]),
            }
            self.save_config()
            return

        mode = ui.get("mode")
        if mode not in ("gunsmoke", "gacha"):
            ui["mode"] = DEFAULT_UI["mode"]
            changed = True

        last = ui.get("last_tab")
        if not isinstance(last, dict):
            ui["last_tab"] = dict(DEFAULT_UI["last_tab"])
            changed = True
        else:
            for key, default_tab in DEFAULT_UI["last_tab"].items():
                if key not in last or not isinstance(last[key], str):
                    last[key] = default_tab
                    changed = True

        if changed:
            self.save_config()

    def get_ui(self) -> dict:
        self.ensure_ui_config()
        return self.config["ui"]

    def set_ui_mode(self, mode: str) -> None:
        ui = self.get_ui()
        if mode not in ("gunsmoke", "gacha"):
            return
        ui["mode"] = mode
        self.save_config()

    def set_ui_tab(self, mode: str, tab_id: str) -> None:
        ui = self.get_ui()
        if mode not in ("gunsmoke", "gacha"):
            return
        last = ui.setdefault("last_tab", {})
        last[mode] = tab_id
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
