"""IBM Plex Sans loading and typography scale for the Qt UI.

DESIGN.md mandates IBM Plex Sans. We bundle Regular/Medium/SemiBold/Bold and
register them via QFontDatabase. Falls back to Segoe UI if registration fails.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

_FONT_FILES = (
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-Medium.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "IBMPlexSans-Bold.ttf",
)

# TrueType / OpenType / TrueType collection magic numbers
_FONT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")


@dataclass(frozen=True)
class Fonts:
    """Typography scale used across the app."""

    heading: QFont
    subheading: QFont
    body: QFont
    body_medium: QFont
    ui: QFont
    caption: QFont
    mono: QFont
    family: str


def _assets_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def _is_font_file(path: Path) -> bool:
    """Reject non-font payloads (e.g. HTML saved as .ttf from a bad download)."""
    try:
        with path.open("rb") as fh:
            magic = fh.read(4)
    except OSError:
        return False
    return magic in _FONT_MAGICS


def _register_plex_fonts() -> str | None:
    fonts_dir = _assets_dir() / "fonts"
    if not fonts_dir.is_dir():
        return None

    family: str | None = None
    for name in _FONT_FILES:
        path = fonts_dir / name
        if not path.is_file() or not _is_font_file(path):
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families and family is None:
            family = families[0]
    return family


def _mk(family: str, point_size: int, weight: QFont.Weight) -> QFont:
    font = QFont(family, point_size)
    font.setWeight(weight)
    return font


def load_fonts() -> Fonts:
    """Register IBM Plex Sans (best-effort) and build the typography scale."""
    family = _register_plex_fonts() or "Segoe UI"
    return Fonts(
        heading=_mk(family, 18, QFont.Weight.Bold),
        subheading=_mk(family, 12, QFont.Weight.Bold),
        body=_mk(family, 10, QFont.Weight.Normal),
        body_medium=_mk(family, 10, QFont.Weight.DemiBold),
        ui=_mk(family, 10, QFont.Weight.DemiBold),
        caption=_mk(family, 9, QFont.Weight.Normal),
        mono=_mk("Consolas", 10, QFont.Weight.Normal),
        family=family,
    )
