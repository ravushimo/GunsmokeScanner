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
    INVENTORY_GROWTH_REGIONS,
)

CONFIG_FILE = "config.json"


def _default_inventory_growth_block(screen_w: int, screen_h: int) -> dict:
    """Placeholder Growth Data regions (tuned for 3440×1440; calibrate in Setup)."""
    # Prefer ultrawide layout defaults when screen matches; else scale from center.
    if screen_w >= 3400 and screen_h >= 1400:
        return {
            "cols": 14,
            "rows": 6,
            "grid": [420, 220, 1680, 780],
            "cell_lock_inset": [10, 48, 40, 40],
            "type": [2580, 720, 420, 36],
            "perks": [2580, 780, 720, 300],
            "lock_btn": [3320, 175, 52, 52],
            "own_count": [1980, 130, 220, 36],
            "click_delay_ms": 80,
            "ocr_settle_ms": 250,
            "lock_click_delay_ms": 120,
            # Scroll ~5 cell heights (1-row overlap); tune scroll_extra_px if needed
            "scroll_rows": 5,
            "scroll_extra_px": 24,
            "skip_rows_after_scroll": 1,
            "scroll_duration_ms": 700,
            "scroll_settle_ms": 500,
        }

    cx, cy = screen_w // 2, screen_h // 2
    return {
        "cols": 14,
        "rows": 6,
        "grid": [cx - 700, cy - 320, 900, 520],
        "cell_lock_inset": [8, 36, 32, 32],
        "type": [cx + 280, cy + 80, 280, 32],
        "perks": [cx + 280, cy + 120, 400, 220],
        "lock_btn": [cx + 700, cy - 300, 44, 44],
        "own_count": [cx + 40, cy - 340, 160, 32],
        "click_delay_ms": 80,
        "ocr_settle_ms": 250,
        "lock_click_delay_ms": 120,
        "scroll_rows": 5,
        "scroll_extra_px": 16,
        "skip_rows_after_scroll": 1,
        "scroll_duration_ms": 700,
        "scroll_settle_ms": 500,
    }


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
            self.ensure_inventory_config()
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
        self.config["inventory"] = {
            "growth": _default_inventory_growth_block(screen_w, screen_h),
        }

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

    def ensure_inventory_config(self) -> None:
        """Migrate older configs that lack the inventory.growth block."""
        inv = self.config.get("inventory")
        changed = False
        if not isinstance(inv, dict):
            screen_w, screen_h = pyautogui.size()
            self.config["inventory"] = {
                "growth": _default_inventory_growth_block(screen_w, screen_h),
            }
            self.save_config()
            return

        growth = inv.get("growth")
        if not isinstance(growth, dict):
            screen_w, screen_h = pyautogui.size()
            inv["growth"] = _default_inventory_growth_block(screen_w, screen_h)
            self.save_config()
            return

        defaults = _default_inventory_growth_block(*pyautogui.size())
        # Drop abandoned identity regions (name OCR / icon match)
        for legacy in ("name", "icon"):
            if legacy in growth:
                del growth[legacy]
                changed = True
        for key in INVENTORY_GROWTH_REGIONS:
            if key not in growth or not isinstance(growth.get(key), list):
                growth[key] = list(defaults[key])
                changed = True
        for key, default in defaults.items():
            if key not in growth:
                growth[key] = default
                changed = True
        if changed:
            self.save_config()

    def get_inventory_growth(self) -> dict:
        self.ensure_inventory_config()
        return self.config["inventory"]["growth"]

    def ensure_ui_config(self) -> None:
        """Ensure ui.mode / ui.last_tab / ui.always_on_top exist with valid values."""
        ui = self.config.get("ui")
        changed = False
        if not isinstance(ui, dict):
            self.config["ui"] = {
                "mode": DEFAULT_UI["mode"],
                "last_tab": dict(DEFAULT_UI["last_tab"]),
                "always_on_top": DEFAULT_UI.get("always_on_top", True),
            }
            self.save_config()
            return

        mode = ui.get("mode")
        if mode not in ("gunsmoke", "gacha", "inventory", "settings"):
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

        if "always_on_top" not in ui or not isinstance(ui.get("always_on_top"), bool):
            ui["always_on_top"] = DEFAULT_UI.get("always_on_top", True)
            changed = True

        if changed:
            self.save_config()

    def get_ocr_languages(self) -> list:
        langs = self.config.get("ocr_languages")
        if not isinstance(langs, list) or not langs:
            return ["en"]
        cleaned = [str(x).strip() for x in langs if str(x).strip()]
        if "en" not in cleaned:
            cleaned.insert(0, "en")
        return cleaned

    def set_ocr_languages(self, languages: list) -> None:
        cleaned = [str(x).strip() for x in languages if str(x).strip()]
        if "en" not in cleaned:
            cleaned.insert(0, "en")
        self.config["ocr_languages"] = cleaned
        self.save_config()

    def set_always_on_top(self, enabled: bool) -> None:
        ui = self.get_ui()
        ui["always_on_top"] = bool(enabled)
        self.save_config()

    def get_ui(self) -> dict:
        self.ensure_ui_config()
        return self.config["ui"]

    def set_ui_mode(self, mode: str) -> None:
        ui = self.get_ui()
        if mode not in ("gunsmoke", "gacha", "inventory", "settings"):
            return
        ui["mode"] = mode
        self.save_config()

    def set_ui_tab(self, mode: str, tab_id: str) -> None:
        ui = self.get_ui()
        if mode not in ("gunsmoke", "gacha", "inventory", "settings"):
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
