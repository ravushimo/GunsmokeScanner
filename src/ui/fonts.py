"""IBM Plex Sans loading and typography scale for the CTk UI.

DESIGN.md mandates IBM Plex Sans Variable. We bundle the four weights we
actually use (Regular/Medium/SemiBold/Bold) and register them privately
into the process via GDI on Windows so no install is required.

If registration fails (locked-down account, non-Windows runtime), we fall
back to Segoe UI which is the closest font in DESIGN.md's fallback list.
"""

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

import customtkinter as ctk

# AddFontResourceExW flags - private to the calling process, no broadcast.
_FR_PRIVATE = 0x10
_FR_NOT_ENUM = 0x20

_FONT_FILES = (
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-Medium.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "IBMPlexSans-Bold.ttf",
)


@dataclass(frozen=True)
class Fonts:
    """Typography scale used across the app. Sizes are in points (Tk's unit).

    The pixel sizes from DESIGN.md were translated to the closest practical
    point sizes for an 800x1000 desktop window.
    """

    heading: ctk.CTkFont  # Section title (DESIGN: 24px/700)
    subheading: ctk.CTkFont  # Sub-heading (DESIGN: 16-20px/700)
    body: ctk.CTkFont  # Body text (DESIGN: 14px/400)
    body_medium: ctk.CTkFont  # Body medium (DESIGN: 14px/500)
    ui: ctk.CTkFont  # Buttons / nav labels (DESIGN: 14px/600)
    caption: ctk.CTkFont  # Status bar / micro labels (DESIGN: 12px/400)
    mono: ctk.CTkFont  # Monospace (Consolas - per DESIGN fallback list)


def _assets_dir() -> Path:
    """Locate `assets/` in dev and inside a PyInstaller onedir bundle."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def _register_plex_fonts() -> bool:
    """Register bundled IBM Plex TTFs with the current process on Windows.

    Returns True if every file registered, False otherwise.
    """
    if sys.platform != "win32":
        return False

    fonts_dir = _assets_dir() / "fonts"
    if not fonts_dir.is_dir():
        return False

    try:
        gdi32 = ctypes.windll.gdi32
    except (AttributeError, OSError):
        return False

    ok = True
    for name in _FONT_FILES:
        path = fonts_dir / name
        if not path.is_file():
            ok = False
            continue
        # AddFontResourceExW returns >0 fonts added on success, 0 on failure.
        added = gdi32.AddFontResourceExW(str(path), _FR_PRIVATE | _FR_NOT_ENUM, 0)
        if not added:
            ok = False
    return ok


def load_fonts() -> Fonts:
    """Register IBM Plex Sans (best-effort) and build the typography scale."""
    family = "IBM Plex Sans" if _register_plex_fonts() else "Segoe UI"

    return Fonts(
        heading=ctk.CTkFont(family=family, size=18, weight="bold"),
        subheading=ctk.CTkFont(family=family, size=12, weight="bold"),
        body=ctk.CTkFont(family=family, size=10, weight="normal"),
        body_medium=ctk.CTkFont(family=family, size=10, weight="bold"),
        ui=ctk.CTkFont(family=family, size=10, weight="bold"),
        caption=ctk.CTkFont(family=family, size=9, weight="normal"),
        mono=ctk.CTkFont(family="Consolas", size=10, weight="normal"),
    )
