"""Main application window (PySide6)."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

import keyboard
import pyautogui
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import ConfigManager
from src.constants import APP_VERSION, GITHUB_URL, SITE_URL, THEME
from src.core.layouts import (
    apply_gacha_layout,
    apply_gunsmoke_layout,
    apply_inventory_layout,
    find_layout,
)
from src.core.ocr import OCRProcessor
from src.core.season import SeasonManager
from src.core.updater import UpdateChecker
from src.data.gacha_db import GachaDB
from src.data.inventory_db import InventoryDB
from src.ui.components.mode_nav import ModeNav, build_mode_switch, mode_label
from src.ui.components.overlay import OverlayManager
from src.ui.components.splash import StartupSplash
from src.ui.fonts import load_fonts
from src.ui.qt_util import call_soon, warm_call_soon
from src.ui.styles import attach_hover_flash, build_stylesheet
from src.ui.tabs.capture import CaptureTab
from src.ui.tabs.gacha_capture import GachaCaptureTab
from src.ui.tabs.gacha_collection import GachaCollectionTab
from src.ui.tabs.gacha_history import GachaHistoryTab
from src.ui.tabs.gacha_setup import GachaSetupTab
from src.ui.tabs.gacha_stats import GachaStatsTab
from src.ui.tabs.inventory_capture import InventoryCaptureTab
from src.ui.tabs.inventory_list import InventoryListTab
from src.ui.tabs.inventory_setup import InventorySetupTab
from src.ui.tabs.setup import SetupTab
from src.ui.tabs.settings import SettingsTab
from src.ui.tabs.upload import UploadTab


def _asset_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).resolve().parents[2] / "assets" / name


class _MainWindow(QMainWindow):
    """QMainWindow that forwards close to GunsmokeApp.on_closing."""

    def __init__(self, app_ref: "GunsmokeApp"):
        super().__init__()
        self._app_ref = app_ref

    def closeEvent(self, event):  # noqa: N802
        self._app_ref.on_closing()
        event.accept()


class GunsmokeApp:
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName("Gunsmoke Scanner")
        self.app.setStyle("Fusion")
        warm_call_soon()

        splash = StartupSplash()
        splash.show_centered()

        def status(pct: int, msg: str) -> None:
            splash.set_progress(pct, msg)

        status(5, "Loading configuration...")
        self.config_manager = ConfigManager()
        self.config_manager.ensure_ui_config()

        status(15, "Loading fonts...")
        self.fonts = load_fonts()
        self.app.setStyleSheet(build_stylesheet(self.fonts.family))

        status(25, "Preparing season and databases...")
        self.season_manager = SeasonManager()
        self.updater = UpdateChecker()
        self.gacha_db = GachaDB()
        self.inventory_db = InventoryDB()

        langs = self.config_manager.get_ocr_languages()
        lang_label = ", ".join(langs)
        status(
            40,
            f"Loading EasyOCR ({lang_label})...\n"
            "First launch may download model files.",
        )
        self.ocr_processor = OCRProcessor(langs)

        status(70, "Building interface...")
        self.root = _MainWindow(self)
        self.root.setWindowTitle(
            f"Gunsmoke Scanner v{APP_VERSION} - Leaderboard / Gacha / Inventory"
        )
        self.root.resize(720, 960)
        self.root.setMinimumSize(640, 720)

        icon_ico = _asset_path("icon.ico")
        if icon_ico.is_file():
            self.root.setWindowIcon(QIcon(str(icon_ico)))

        central = QWidget()
        self.root.setCentralWidget(central)
        self._outer = QVBoxLayout(central)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        self.overlay_manager = OverlayManager(
            self.root, self.config_manager, self.fonts
        )

        self._pages: dict = {}
        self._page_index: dict = {}
        self._mode = "gunsmoke"
        self._tab_id = "capture"
        self._update_banner: QFrame | None = None
        self._overlay_on = False

        self.setup_ui()
        status(90, "Restoring last session...")
        self._restore_ui_state()

        status(95, "Registering hotkeys...")
        try:
            keyboard.add_hotkey("f9", self._on_f9)
            keyboard.add_hotkey("f8", self._on_f8)
            keyboard.add_hotkey("f7", self._on_f7)
            keyboard.add_hotkey("f10", self._on_f10)
            keyboard.add_hotkey("f5", self._on_f5)
            keyboard.add_hotkey("f4", self._on_f4)
        except Exception as e:
            print(f"Failed to register hotkey: {e}")

        status(100, "Ready")
        splash.close()
        splash.deleteLater()

    def _on_f9(self):
        if self._mode == "inventory":
            self.inventory_capture_tab.start_full_scan()
        elif self._mode == "gacha" and self._tab_id == "capture":
            self.gacha_capture_tab.start_scan_thread()
        else:
            self.capture_tab.start_capture_thread()

    def _on_f8(self):
        if self._mode == "inventory":
            self.inventory_capture_tab.start_single()

    def _on_f7(self):
        if self._mode == "inventory":
            self.inventory_capture_tab.start_last_row()

    def _on_f10(self):
        # Capture current state on the hotkey thread; apply on the GUI thread.
        nxt = not self._overlay_on
        call_soon(lambda on=nxt: self.set_overlay_visible(on))

    def _on_f5(self):
        if self._mode == "gacha":
            self.gacha_capture_tab.stop_scan()
        elif self._mode == "inventory":
            self.inventory_capture_tab.stop_scan()

    def _on_f4(self):
        call_soon(self.apply_layout_for_screen)

    def apply_layout_for_screen(self):
        width, height = pyautogui.size()
        mode = (
            self._mode
            if self._mode in ("gacha", "gunsmoke", "inventory")
            else "gunsmoke"
        )
        layout, reason = find_layout(mode, width, height)
        if not layout:
            QMessageBox.information(
                self.root,
                "No layout template",
                f"No {mode} layout for {width}x{height}.\n\n"
                "Calibrate in Setup, then use \"Save as layout template\",\n"
                "or add a screenshot under .docs/templates for a new resolution.",
            )
            return

        res = layout.get("resolution") or [width, height]
        label = f"{int(res[0])}x{int(res[1])}"
        if reason == "exact":
            note = f"Exact match: {label}"
        else:
            note = f"Nearest template: {label} (screen is {width}x{height})"

        if mode == "gacha":
            apply_gacha_layout(self.config_manager.config, layout)
        elif mode == "inventory":
            apply_inventory_layout(self.config_manager.config, layout)
        else:
            apply_gunsmoke_layout(self.config_manager.config, layout)
        self.config_manager.save_config()

        if self.overlay_manager.active:
            self.overlay_manager.sync_geometries()
        if mode == "gacha" and hasattr(self, "gacha_setup_tab"):
            self.gacha_setup_tab.update_region_info()
        if mode == "gunsmoke" and hasattr(self, "setup_tab"):
            self.setup_tab.update_region_info()
        if mode == "inventory" and hasattr(self, "inventory_setup_tab"):
            self.inventory_setup_tab.update_region_info()

        QMessageBox.information(
            self.root, "Layout applied", f"{note}\nOverlays refreshed if visible."
        )

    def check_updates(self, *, from_settings: bool = False):
        def _check():
            has_update, version, url = self.updater.check_for_updates()

            def done():
                if has_update:
                    self.show_update_banner(version, url)
                    if hasattr(self, "settings_tab"):
                        self.settings_tab.set_update_status(
                            f"Update available: {version}"
                        )
                elif from_settings and hasattr(self, "settings_tab"):
                    self.settings_tab.set_update_status(
                        "You are on the latest version."
                    )

            call_soon(done)

        threading.Thread(target=_check, daemon=True).start()

    def _check_updates_from_settings(self):
        self.check_updates(from_settings=True)

    def show_update_banner(self, version, url):
        if self._update_banner is not None:
            return
        banner = QFrame()
        banner.setFixedHeight(32)
        banner.setStyleSheet(
            f"QFrame {{ background-color: {THEME['bg_featured']}; border: none; }}"
        )
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(20, 0, 20, 0)

        msg = QLabel(f"New version available: {version}  -  click to download")
        msg.setFont(self.fonts.body_medium)
        msg.setStyleSheet(f"color: {THEME['text_strong']};")
        msg.setCursor(Qt.CursorShape.PointingHandCursor)
        msg.mousePressEvent = lambda _e: webbrowser.open(url)  # type: ignore
        attach_hover_flash(msg, THEME["text_strong"], THEME["accent_orange"])
        lay.addWidget(msg, 1)

        close = QLabel("X")
        close.setFont(self.fonts.ui)
        close.setStyleSheet(f"color: {THEME['text_strong']};")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.mousePressEvent = lambda _e: self._dismiss_banner()  # type: ignore
        attach_hover_flash(close, THEME["text_strong"], THEME["accent_orange"])
        lay.addWidget(close)

        self._outer.insertWidget(0, banner)
        self._update_banner = banner

    def _dismiss_banner(self):
        if self._update_banner is not None:
            self._outer.removeWidget(self._update_banner)
            self._update_banner.deleteLater()
            self._update_banner = None

    def _open_site(self, _event=None):
        webbrowser.open(SITE_URL)

    def _open_github(self, _event=None):
        webbrowser.open(GITHUB_URL)

    def setup_ui(self):
        self.header = QFrame()
        self.header.setObjectName("AppHeader")
        self.header.setFixedHeight(64)
        self.header.setStyleSheet(
            f"QFrame#AppHeader {{ background-color: {THEME['bg_canvas']};"
            f" border: none; border-bottom: 1px solid {THEME['border']}; }}"
        )
        header_lay = QHBoxLayout(self.header)
        header_lay.setContentsMargins(14, 6, 14, 6)
        header_lay.setSpacing(14)

        brand = QWidget()
        brand.setStyleSheet("background: transparent;")
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(0, 0, 0, 0)
        brand_lay.setSpacing(10)

        logo_path = _asset_path("logo.png")
        if logo_path.is_file():
            pix = QPixmap.fromImage(ImageQt(Image.open(logo_path).convert("RGBA")))
            pix = pix.scaled(
                32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl = QLabel()
            logo_lbl.setPixmap(pix)
            logo_lbl.setStyleSheet("background: transparent;")
            logo_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            logo_lbl.mousePressEvent = lambda _e: self._open_site()  # type: ignore
            brand_lay.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(0)

        word = QLabel("gunsmoke")
        word.setFont(self.fonts.heading)
        word.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        word.setCursor(Qt.CursorShape.PointingHandCursor)
        word.mousePressEvent = lambda _e: self._open_site()  # type: ignore
        attach_hover_flash(word, THEME["text_strong"], THEME["accent_orange"])

        suffix = QLabel(".app")
        suffix.setFont(self.fonts.heading)
        suffix.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        suffix.setCursor(Qt.CursorShape.PointingHandCursor)
        suffix.mousePressEvent = lambda _e: self._open_site()  # type: ignore
        attach_hover_flash(suffix, THEME["text_muted"], THEME["accent_orange"])

        brand_row.addWidget(word)
        brand_row.addWidget(suffix)
        brand_row.addStretch()
        title_col.addLayout(brand_row)

        subtitle = QLabel(f"Scanner v{APP_VERSION}")
        subtitle.setFont(self.fonts.caption)
        subtitle.setStyleSheet(
            f"color: {THEME['text_muted']}; background: transparent; font-size: 8pt;"
        )
        subtitle.setCursor(Qt.CursorShape.PointingHandCursor)
        subtitle.mousePressEvent = lambda _e: self._open_github()  # type: ignore
        attach_hover_flash(subtitle, THEME["text_muted"], THEME["accent_orange"])
        title_col.addWidget(subtitle)

        brand_lay.addLayout(title_col)
        header_lay.addWidget(brand)

        ui = self.config_manager.get_ui()
        self.mode_switch = build_mode_switch(
            self.header,
            self.fonts,
            initial=ui.get("mode", "gunsmoke"),
            on_mode=self._on_mode_switch,
        )
        header_lay.addWidget(self.mode_switch, 1)
        self._outer.addWidget(self.header)

        self.mode_nav = ModeNav(None, self.fonts, on_tab=self._on_nav_tab)
        self._outer.addWidget(self.mode_nav)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        stack_wrap = QWidget()
        stack_lay = QVBoxLayout(stack_wrap)
        stack_lay.setContentsMargins(8, 4, 8, 8)
        stack_lay.addWidget(self.stack)
        self._outer.addWidget(stack_wrap, 1)

        def page(key: str) -> QWidget:
            fr = QWidget()
            fr.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
            idx = self.stack.addWidget(fr)
            self._pages[key] = fr
            self._page_index[key] = idx
            return fr

        def mount(parent: QWidget, child: QWidget) -> QWidget:
            lay = QVBoxLayout(parent)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(child)
            return child

        self.setup_tab = mount(
            page("gunsmoke.setup"),
            SetupTab(
                None,
                self.config_manager,
                self.overlay_manager,
                self.fonts,
                ocr_processor=self.ocr_processor,
                on_apply_layout=self.apply_layout_for_screen,
            ),
        )

        self.capture_tab = mount(
            page("gunsmoke.capture"),
            CaptureTab(
                None,
                self.config_manager,
                self.ocr_processor,
                self.season_manager,
                self.fonts,
            ),
        )

        self.upload_tab = mount(
            page("gunsmoke.upload"),
            UploadTab(None, self.config_manager, self.fonts),
        )

        self.gacha_setup_tab = mount(
            page("gacha.setup"),
            GachaSetupTab(
                None,
                self.config_manager,
                self.overlay_manager,
                self.fonts,
                ocr_processor=self.ocr_processor,
                on_apply_layout=self.apply_layout_for_screen,
            ),
        )

        self.gacha_history_tab = mount(
            page("gacha.history"),
            GachaHistoryTab(
                None,
                self.fonts,
                db=self.gacha_db,
                on_change=lambda: (
                    self.gacha_stats_tab.refresh(),
                    self.gacha_collection_tab.refresh(),
                ),
            ),
        )

        self.gacha_stats_tab = mount(
            page("gacha.stats"),
            GachaStatsTab(None, self.fonts, db=self.gacha_db),
        )

        self.gacha_collection_tab = mount(
            page("gacha.collection"),
            GachaCollectionTab(
                None,
                self.fonts,
                db=self.gacha_db,
                on_change=lambda: self.gacha_stats_tab.refresh(),
            ),
        )

        def _refresh_gacha_views():
            self.gacha_history_tab.refresh()
            self.gacha_stats_tab.refresh()
            self.gacha_collection_tab.refresh()

        self.gacha_capture_tab = mount(
            page("gacha.capture"),
            GachaCaptureTab(
                None,
                self.config_manager,
                self.ocr_processor,
                self.overlay_manager,
                self.fonts,
                db=self.gacha_db,
                on_history_refresh=_refresh_gacha_views,
                on_overlay_off=self.force_overlay_off,
            ),
        )

        self.inventory_setup_tab = mount(
            page("inventory.setup"),
            InventorySetupTab(
                None,
                self.config_manager,
                self.overlay_manager,
                self.fonts,
                ocr_processor=self.ocr_processor,
                on_apply_layout=self.apply_layout_for_screen,
            ),
        )

        self.inventory_list_tab = mount(
            page("inventory.list"),
            InventoryListTab(None, self.fonts, db=self.inventory_db),
        )

        self.inventory_capture_tab = mount(
            page("inventory.capture"),
            InventoryCaptureTab(
                None,
                self.config_manager,
                self.ocr_processor,
                self.overlay_manager,
                self.fonts,
                db=self.inventory_db,
                on_inventory_refresh=self.inventory_list_tab.refresh,
                on_overlay_off=self.force_overlay_off,
            ),
        )

        ui = self.config_manager.get_ui()
        self.settings_tab = mount(
            page("settings.main"),
            SettingsTab(
                None,
                config_manager=self.config_manager,
                fonts=self.fonts,
                ocr_processor=self.ocr_processor,
                always_on_top=bool(ui.get("always_on_top", True)),
                overlay_on=self._overlay_on,
                on_always_on_top=lambda on: self.set_always_on_top(on, persist=True),
                on_overlay=self.set_overlay_visible,
                on_check_updates=self._check_updates_from_settings,
            ),
        )

        self.set_always_on_top(bool(ui.get("always_on_top", True)), persist=False)

    def _restore_ui_state(self):
        ui = self.config_manager.get_ui()
        mode = ui.get("mode", "gunsmoke")
        default_tab = "main" if mode == "settings" else "capture"
        tab_id = (ui.get("last_tab") or {}).get(mode, default_tab)
        self.mode_switch.set(mode_label(mode))
        self.mode_nav.set_mode(mode, tab_id)

    def _on_mode_switch(self, mode: str):
        ui = self.config_manager.get_ui()
        default_tab = "main" if mode == "settings" else "capture"
        tab_id = (ui.get("last_tab") or {}).get(mode, default_tab)
        self.config_manager.set_ui_mode(mode)
        self.mode_nav.set_mode(mode, tab_id)

    def _on_nav_tab(self, mode: str, tab_id: str):
        self._mode = mode
        self._tab_id = tab_id
        self.config_manager.set_ui_tab(mode, tab_id)
        self._show_page(mode, tab_id)
        self._sync_overlay_profile()
        if not self.overlay_manager.active and self._overlay_on:
            self.set_overlay_visible(False)
        if mode == "gacha" and tab_id == "stats":
            self.gacha_stats_tab.refresh()
        if mode == "gacha" and tab_id == "collection":
            self.gacha_collection_tab.refresh()
        if mode == "inventory" and tab_id == "list":
            self.inventory_list_tab.refresh()

    def _show_page(self, mode: str, tab_id: str):
        key = f"{mode}.{tab_id}"
        idx = self._page_index.get(key)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

    def set_overlay_visible(self, on: bool):
        self._overlay_on = bool(on)
        self._sync_overlay_profile()
        if self._overlay_on:
            if not self.overlay_manager.active:
                self.overlay_manager.show()
        else:
            self.overlay_manager.hide()
        if hasattr(self, "settings_tab"):
            self.settings_tab.sync_overlay_checkbox(self._overlay_on)

    def force_overlay_off(self):
        self.set_overlay_visible(False)

    def _sync_overlay_profile(self):
        if self._mode == "gacha" and self._tab_id == "setup":
            self.gacha_setup_tab.activate()
        elif self._mode == "gunsmoke" and self._tab_id == "setup":
            self.setup_tab.activate()
        elif self._mode == "inventory" and self._tab_id == "setup":
            self.inventory_setup_tab.activate()
        elif self._mode == "gacha":
            self.overlay_manager.set_profile("gacha")
        elif self._mode == "inventory":
            self.overlay_manager.set_profile("inventory")
        else:
            self.overlay_manager.set_profile("gunsmoke")

    def set_always_on_top(self, on: bool, *, persist: bool = True):
        on = bool(on)
        flags = self.root.windowFlags()
        if on:
            self.root.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.root.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        if self.root.isVisible():
            self.root.show()
        if persist:
            self.config_manager.set_always_on_top(on)

    def run(self):
        self.root.show()
        sys.exit(self.app.exec())

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
