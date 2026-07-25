"""Startup splash - logo, status text, and progress while the app boots."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.constants import APP_VERSION, THEME


def _asset_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).resolve().parents[3] / "assets" / name


class StartupSplash(QWidget):
    """Frameless splash shown before the main window is ready."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gunsmoke Scanner")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(420, 280)
        self.setStyleSheet(
            f"QWidget {{ background-color: {THEME['bg_canvas']};"
            f" color: {THEME['text_primary']}; }}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(12)

        logo_path = _asset_path("logo.png")
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setStyleSheet("background: transparent;")
        if logo_path.is_file():
            pix = QPixmap.fromImage(ImageQt(Image.open(logo_path).convert("RGBA")))
            pix = pix.scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo.setPixmap(pix)
        lay.addWidget(self.logo)

        brand = QLabel("gunsmoke.app")
        brand_font = QFont()
        brand_font.setPointSize(16)
        brand_font.setBold(True)
        brand.setFont(brand_font)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(
            f"color: {THEME['text_strong']}; background: transparent;"
        )
        lay.addWidget(brand)

        ver = QLabel(f"Scanner v{APP_VERSION}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color: {THEME['text_muted']}; background: transparent; font-size: 9pt;"
        )
        lay.addWidget(ver)

        lay.addStretch(1)

        self.status = QLabel("Starting...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color: {THEME['text_primary']}; background: transparent; font-size: 10pt;"
        )
        lay.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            f"QProgressBar {{"
            f" background-color: {THEME['bg_raised']};"
            f" border: none; border-radius: 4px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f" background-color: {THEME['cta_dark']};"
            f" border-radius: 4px;"
            f"}}"
        )
        lay.addWidget(self.bar)

        self.hint = QLabel("First launch may download EasyOCR models.")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(
            f"color: {THEME['text_muted']}; background: transparent; font-size: 8pt;"
        )
        lay.addWidget(self.hint)

    def show_centered(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.show()
        self.raise_()
        QApplication.processEvents()

    def set_busy(self, busy: bool) -> None:
        """Indeterminate bar while waiting (e.g. loading models already on disk)."""
        if busy:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 100)
        QApplication.processEvents()

    def set_progress(self, percent: int, message: str) -> None:
        if self.bar.minimum() == 0 and self.bar.maximum() == 0:
            self.bar.setRange(0, 100)
        self.bar.setValue(max(0, min(100, int(percent))))
        self.status.setText(message)
        QApplication.processEvents()
