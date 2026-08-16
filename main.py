"""Entry point - configure Windows DPI, show splash early, then boot the app."""

from __future__ import annotations

import sys


def _prepare_windows_dpi() -> None:
    """Claim per-monitor DPI awareness before pyautogui locks a weaker mode.

    PyAutoGUI calls SetProcessDPIAware on import, which then makes Qt's
    SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2) fail with Access Denied.
    Setting V2 first keeps Qt happy and scaling correct.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass


_prepare_windows_dpi()

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.ui.components.splash import StartupSplash  # noqa: E402
from src.ui.qt_util import warm_call_soon  # noqa: E402


if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Gunsmoke Scanner")
    qt_app.setStyle("Fusion")
    warm_call_soon()

    # Show splash before importing the rest of the UI / heavy modules.
    splash = StartupSplash()
    splash.show_centered()
    splash.set_progress(2, "Starting...")

    from src.ui.app import GunsmokeApp  # noqa: E402

    app = GunsmokeApp(qt_app=qt_app, splash=splash)
    app.run()
