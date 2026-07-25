"""Entry point - configure Windows DPI before GUI / pyautogui imports."""

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

from src.ui.app import GunsmokeApp  # noqa: E402


if __name__ == "__main__":
    app = GunsmokeApp()
    app.run()
