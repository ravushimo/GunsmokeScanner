import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path

import customtkinter as ctk
import keyboard
from PIL import Image

from src.config import ConfigManager
from src.constants import APP_VERSION, GITHUB_URL, SITE_URL, THEME
from src.core.ocr import OCRProcessor
from src.core.season import SeasonManager
from src.core.updater import UpdateChecker
from src.data.gacha_db import GachaDB
from src.ui.components.mode_nav import ModeNav, build_mode_switch
from src.ui.components.overlay import OverlayManager
from src.ui.fonts import load_fonts
from src.ui.styles import apply_ctk_theme, attach_hover_flash, setup_ttk_styles
from src.ui.tabs.capture import CaptureTab
from src.ui.tabs.gacha_capture import GachaCaptureTab
from src.ui.tabs.gacha_history import GachaHistoryTab
from src.ui.tabs.gacha_setup import GachaSetupTab
from src.ui.tabs.gacha_stats import GachaStatsTab
from src.ui.tabs.setup import SetupTab
from src.ui.tabs.upload import UploadTab


def _asset_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).resolve().parents[2] / "assets" / name


class GunsmokeApp:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config_manager.ensure_ui_config()

        self.season_manager = SeasonManager()
        self.ocr_processor = OCRProcessor(self.config_manager.get("ocr_languages"))
        self.updater = UpdateChecker()
        self.gacha_db = GachaDB()

        # CTk theme has to be applied before the root window is constructed so
        # that the dark gunsmoke.app palette takes effect.
        apply_ctk_theme()

        self.root = ctk.CTk()
        self.root.title(
            f"Gunsmoke Scanner v{APP_VERSION} - Leaderboard Scanner for gunsmoke.app"
        )
        self.root.geometry("860x1000")
        self.root.configure(fg_color=THEME["bg_canvas"])

        logo_path = _asset_path("logo.png")
        if logo_path.is_file():
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=str(logo_path)))
            except Exception:
                pass

        self.fonts = load_fonts()
        setup_ttk_styles(self.fonts)

        self.overlay_manager = OverlayManager(
            self.root, self.config_manager, self.fonts
        )

        self._pages: dict = {}
        self._mode = "gunsmoke"
        self._tab_id = "capture"

        self.setup_ui()
        self._restore_ui_state()

        try:
            keyboard.add_hotkey("f9", self._on_f9)
            keyboard.add_hotkey("f5", self._on_f5)
        except Exception as e:
            print(f"Failed to register hotkey: {e}")

        self.root.after(1000, self.check_updates)

    def _on_f9(self):
        """Mode-aware F9: gacha scan in Gacha Capture; else Gunsmoke capture."""
        if self._mode == "gacha" and self._tab_id == "capture":
            self.gacha_capture_tab.start_scan_thread()
        else:
            self.capture_tab.start_capture_thread()

    def _on_f5(self):
        """Stop automated gacha multi-page scan (same as Stop button)."""
        if self._mode != "gacha":
            return
        self.gacha_capture_tab.stop_scan()

    def check_updates(self):
        def _check():
            has_update, version, url = self.updater.check_for_updates()
            if has_update:
                self.root.after(0, lambda: self.show_update_banner(version, url))

        threading.Thread(target=_check, daemon=True).start()

    def show_update_banner(self, version, url):
        banner = ctk.CTkFrame(
            self.root,
            fg_color=THEME["bg_featured"],
            corner_radius=0,
            height=32,
        )
        banner.pack(side=tk.TOP, fill=tk.X, before=self.header)
        banner.pack_propagate(False)

        msg = ctk.CTkLabel(
            banner,
            text=f"New version available: {version}  -  click to download",
            text_color=THEME["text_strong"],
            fg_color="transparent",
            font=self.fonts.body_medium,
            cursor="hand2",
        )
        msg.pack(side=tk.LEFT, padx=20)
        msg.bind("<Button-1>", lambda _e: webbrowser.open(url))
        attach_hover_flash(msg, THEME["text_strong"], THEME["accent_orange"])

        close = ctk.CTkLabel(
            banner,
            text="X",
            text_color=THEME["text_strong"],
            fg_color="transparent",
            font=self.fonts.ui,
            cursor="hand2",
        )
        close.pack(side=tk.RIGHT, padx=20)
        close.bind("<Button-1>", lambda _e: banner.destroy())
        attach_hover_flash(close, THEME["text_strong"], THEME["accent_orange"])

    def _open_site(self, _event=None):
        webbrowser.open(SITE_URL)

    def _open_github(self, _event=None):
        webbrowser.open(GITHUB_URL)

    def setup_ui(self):
        self.header = ctk.CTkFrame(
            self.root,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            height=70,
        )
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        # Logo + gunsmoke.app → site; Scanner version → GitHub
        brand = ctk.CTkFrame(self.header, fg_color="transparent")
        brand.pack(side=tk.LEFT, padx=16, pady=8)

        logo_path = _asset_path("logo.png")
        if logo_path.is_file():
            self._logo_image = ctk.CTkImage(
                light_image=Image.open(logo_path),
                dark_image=Image.open(logo_path),
                size=(36, 36),
            )
            logo_lbl = ctk.CTkLabel(
                brand,
                image=self._logo_image,
                text="",
                fg_color="transparent",
                cursor="hand2",
            )
            logo_lbl.pack(side=tk.LEFT, padx=(0, 10))
            logo_lbl.bind("<Button-1>", self._open_site)
            attach_hover_flash(logo_lbl, THEME["text_strong"], THEME["accent_orange"])

        title_col = ctk.CTkFrame(brand, fg_color="transparent")
        title_col.pack(side=tk.LEFT)

        brand_row = ctk.CTkFrame(title_col, fg_color="transparent", cursor="hand2")
        brand_row.pack(anchor=tk.W)

        word = ctk.CTkLabel(
            brand_row,
            text="gunsmoke",
            font=self.fonts.heading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            cursor="hand2",
        )
        word.pack(side=tk.LEFT)
        suffix = ctk.CTkLabel(
            brand_row,
            text=".app",
            font=self.fonts.heading,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            cursor="hand2",
        )
        suffix.pack(side=tk.LEFT)

        subtitle = ctk.CTkLabel(
            title_col,
            text=f"Scanner v{APP_VERSION}",
            font=self.fonts.caption,
            text_color=THEME["text_muted"],
            fg_color="transparent",
            cursor="hand2",
        )
        subtitle.pack(anchor=tk.W)

        for w in (brand_row, word, suffix):
            w.bind("<Button-1>", self._open_site)
        attach_hover_flash(word, THEME["text_strong"], THEME["accent_orange"])
        attach_hover_flash(suffix, THEME["text_muted"], THEME["accent_orange"])

        subtitle.bind("<Button-1>", self._open_github)
        attach_hover_flash(subtitle, THEME["text_muted"], THEME["accent_orange"])

        # Mode switch between brand and toggles
        ui = self.config_manager.get_ui()
        self.mode_switch = build_mode_switch(
            self.header,
            self.fonts,
            initial=ui.get("mode", "gunsmoke"),
            on_mode=self._on_mode_switch,
        )
        self.mode_switch.pack(side=tk.LEFT, padx=(20, 12), pady=19)

        controls = ctk.CTkFrame(self.header, fg_color="transparent")
        controls.pack(side=tk.RIGHT, padx=20)

        toggles_frame = ctk.CTkFrame(controls, fg_color="transparent")
        toggles_frame.pack(side=tk.TOP, anchor=tk.E)

        self.top_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            toggles_frame,
            text="Always on Top",
            variable=self.top_var,
            command=self.toggle_top,
            font=self.fonts.body,
            text_color=THEME["text_primary"],
        ).pack(side=tk.LEFT)
        self.toggle_top()

        self.overlay_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            toggles_frame,
            text="Show Overlay",
            variable=self.overlay_var,
            command=self._toggle_overlay,
            font=self.fonts.body,
            text_color=THEME["text_primary"],
        ).pack(side=tk.LEFT, padx=10)

        # Underline tab strip for active mode
        self.mode_nav = ModeNav(
            self.root,
            self.fonts,
            on_tab=self._on_nav_tab,
        )
        self.mode_nav.pack(fill=tk.X)

        # Content host — all pages mounted once, shown/hidden by mode+tab
        self.content = ctk.CTkFrame(
            self.root, fg_color=THEME["bg_canvas"], corner_radius=0
        )
        self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        def page(key: str) -> ctk.CTkFrame:
            fr = ctk.CTkFrame(self.content, fg_color=THEME["bg_canvas"], corner_radius=0)
            self._pages[key] = fr
            return fr

        self.setup_tab = SetupTab(
            page("gunsmoke.setup"),
            self.config_manager,
            self.overlay_manager,
            self.fonts,
            ocr_processor=self.ocr_processor,
        )
        self.setup_tab.pack(fill=tk.BOTH, expand=True)

        self.capture_tab = CaptureTab(
            page("gunsmoke.capture"),
            self.config_manager,
            self.ocr_processor,
            self.season_manager,
            self.fonts,
        )
        self.capture_tab.pack(fill=tk.BOTH, expand=True)

        self.upload_tab = UploadTab(
            page("gunsmoke.upload"),
            self.config_manager,
            self.fonts,
        )
        self.upload_tab.pack(fill=tk.BOTH, expand=True)

        self.gacha_setup_tab = GachaSetupTab(
            page("gacha.setup"),
            self.config_manager,
            self.overlay_manager,
            self.fonts,
            ocr_processor=self.ocr_processor,
        )
        self.gacha_setup_tab.pack(fill=tk.BOTH, expand=True)

        self.gacha_history_tab = GachaHistoryTab(
            page("gacha.history"),
            self.fonts,
            db=self.gacha_db,
        )
        self.gacha_history_tab.pack(fill=tk.BOTH, expand=True)

        self.gacha_stats_tab = GachaStatsTab(
            page("gacha.stats"),
            self.fonts,
            db=self.gacha_db,
        )
        self.gacha_stats_tab.pack(fill=tk.BOTH, expand=True)

        def _refresh_gacha_views():
            self.gacha_history_tab.refresh()
            self.gacha_stats_tab.refresh()

        self.gacha_capture_tab = GachaCaptureTab(
            page("gacha.capture"),
            self.config_manager,
            self.ocr_processor,
            self.overlay_manager,
            self.fonts,
            db=self.gacha_db,
            on_history_refresh=_refresh_gacha_views,
            overlay_var=self.overlay_var,
        )
        self.gacha_capture_tab.pack(fill=tk.BOTH, expand=True)

    def _restore_ui_state(self):
        ui = self.config_manager.get_ui()
        mode = ui.get("mode", "gunsmoke")
        tab_id = (ui.get("last_tab") or {}).get(mode, "capture")
        # Avoid double-save on first paint: set mode switch label, then nav
        label = "Gunsmoke" if mode == "gunsmoke" else "Gacha"
        self.mode_switch.set(label)
        self.mode_nav.set_mode(mode, tab_id)

    def _on_mode_switch(self, mode: str):
        ui = self.config_manager.get_ui()
        tab_id = (ui.get("last_tab") or {}).get(mode, "capture")
        self.config_manager.set_ui_mode(mode)
        self.mode_nav.set_mode(mode, tab_id)

    def _on_nav_tab(self, mode: str, tab_id: str):
        self._mode = mode
        self._tab_id = tab_id
        self.config_manager.set_ui_tab(mode, tab_id)
        self._show_page(mode, tab_id)
        self._sync_overlay_profile()
        if not self.overlay_manager.active and self.overlay_var.get():
            self.overlay_var.set(False)
        if mode == "gacha" and tab_id == "stats":
            self.gacha_stats_tab.refresh()

    def _show_page(self, mode: str, tab_id: str):
        key = f"{mode}.{tab_id}"
        for name, frame in self._pages.items():
            if name == key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

    def _toggle_overlay(self):
        self._sync_overlay_profile()
        if self.overlay_var.get():
            if not self.overlay_manager.active:
                self.overlay_manager.show()
        else:
            self.overlay_manager.hide()

    def _sync_overlay_profile(self):
        if self._mode == "gacha" and self._tab_id == "setup":
            self.gacha_setup_tab.activate()
        elif self._mode == "gunsmoke" and self._tab_id == "setup":
            self.setup_tab.activate()
        elif self._mode == "gacha":
            self.overlay_manager.set_profile("gacha")
        else:
            self.overlay_manager.set_profile("gunsmoke")

    def toggle_top(self):
        self.root.attributes("-topmost", self.top_var.get())

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        try:
            self.config_manager.set_ui_mode(self._mode)
            self.config_manager.set_ui_tab(self._mode, self._tab_id)
        except Exception:
            pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.overlay_manager.hide()
        self.root.destroy()
