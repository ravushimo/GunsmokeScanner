"""Qt stylesheet and button helpers aligned with `.docs/DESIGN.md`."""

from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QCursor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QTableWidget,
    QWidget,
)

from src.constants import THEME

ButtonVariant = str  # "primary" | "secondary" | "featured" | "ghost" | "danger"

# Solid red for destructive actions (THEME["danger"] is a light text tint).
_DANGER_BG = "#B91C1C"
_DANGER_HOVER = "#DC2626"
_DANGER_PRESSED = "#991B1B"


def build_stylesheet(font_family: str = "Segoe UI") -> str:
    """Application-wide QSS from THEME tokens."""
    t = THEME
    return f"""
    QWidget {{
        background-color: {t["bg_canvas"]};
        color: {t["text_primary"]};
        font-family: "{font_family}";
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{
        background-color: {t["bg_canvas"]};
    }}
    QLabel {{
        background: transparent;
        color: {t["text_primary"]};
    }}
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {t["bg_surface"]};
        color: {t["text_input"]};
        border: 1px solid {t["border_strong"]};
        border-radius: 4px;
        padding: 4px 6px;
        selection-background-color: {t["bg_hover"]};
        selection-color: {t["accent_orange"]};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {t["focus"]};
    }}
    QComboBox {{
        background-color: {t["bg_surface"]};
        color: {t["text_input"]};
        border: 1px solid {t["border_strong"]};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 24px;
    }}
    QComboBox:hover {{
        background-color: {t["bg_hover"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t["bg_surface"]};
        color: {t["text_input"]};
        border: 1px solid {t["border"]};
        selection-background-color: {t["bg_hover"]};
        selection-color: {t["accent_orange"]};
    }}
    QCheckBox {{
        background: transparent;
        color: {t["text_primary"]};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {t["border_strong"]};
        border-radius: 3px;
        background: {t["bg_raised"]};
    }}
    QCheckBox::indicator:checked {{
        background: {t["cta_dark"]};
        border-color: {t["cta_dark"]};
    }}
    QRadioButton {{
        background: transparent;
        color: {t["text_primary"]};
        spacing: 6px;
    }}
    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {t["border_strong"]};
        border-radius: 7px;
        background: {t["bg_raised"]};
    }}
    QRadioButton::indicator:checked {{
        background: {t["cta_dark"]};
        border-color: {t["cta_dark"]};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: {t["bg_surface"]};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t["bg_raised"]};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {t["bg_surface"]};
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t["bg_raised"]};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QTableView, QTreeView, QListView {{
        background-color: {t["bg_canvas"]};
        alternate-background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        border: 1px solid {t["border"]};
        gridline-color: {t["border"]};
        selection-background-color: {t["bg_hover"]};
        selection-color: {t["accent_orange"]};
        outline: none;
    }}
    QHeaderView::section {{
        background-color: {t["bg_surface"]};
        color: {t["text_strong"]};
        border: none;
        border-right: 1px solid {t["border"]};
        border-bottom: 1px solid {t["border"]};
        padding: 4px 6px;
        font-weight: 600;
    }}
    QHeaderView::section:hover {{
        background-color: {t["bg_raised"]};
        color: {t["accent_orange"]};
    }}
    QGroupBox {{
        background-color: transparent;
        border: none;
        border-top: 1px solid {t["border"]};
        margin-top: 12px;
        padding-top: 8px;
        font-weight: 600;
        color: {t["text_strong"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 0;
        padding: 0 4px 0 0;
    }}
    QFrame#Toolbar {{
        background-color: {t["bg_surface"]};
        border: none;
        border-bottom: 1px solid {t["border"]};
    }}
    QFrame#Section {{
        background-color: transparent;
        border: none;
    }}
    QFrame#Card {{
        background-color: transparent;
        border: 1px solid {t["border"]};
    }}
    QFrame#StatStrip {{
        background-color: transparent;
        border: none;
        border-top: 1px solid {t["border"]};
        border-bottom: 1px solid {t["border"]};
    }}
    QToolTip {{
        background-color: {t["bg_raised"]};
        color: {t["text_strong"]};
        border: 1px solid {t["border"]};
        padding: 4px;
    }}
    QMenu {{
        background-color: {t["bg_surface"]};
        color: {t["text_input"]};
        border: 1px solid {t["border"]};
    }}
    QMenu::item:selected {{
        background-color: {t["bg_hover"]};
        color: {t["accent_orange"]};
    }}
    QProgressBar {{
        background-color: {t["bg_surface"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        text-align: center;
        color: {t["text_strong"]};
    }}
    QProgressBar::chunk {{
        background-color: {t["cta_dark"]};
    }}
    QSplitter::handle {{
        background-color: {t["border"]};
    }}
    """


def toolbar_frame(parent: Optional[QWidget] = None) -> QFrame:
    """Thin chrome strip for page toolbars (single bottom edge, no box)."""
    frame = QFrame(parent)
    frame.setObjectName("Toolbar")
    frame.setStyleSheet(
        f"QFrame#Toolbar {{ background-color: {THEME['bg_surface']};"
        f" border: none; border-bottom: 1px solid {THEME['border']}; }}"
    )
    return frame


def section_frame(parent: Optional[QWidget] = None) -> QFrame:
    """Flat content section - no fill, no border (avoids nested boxes)."""
    frame = QFrame(parent)
    frame.setObjectName("Section")
    frame.setStyleSheet("QFrame#Section { background: transparent; border: none; }")
    return frame


def card_frame(parent: Optional[QWidget] = None, *, accent: Optional[str] = None) -> QFrame:
    """Single-border card on canvas (no raised fill)."""
    frame = QFrame(parent)
    frame.setObjectName("Card")
    border = accent or THEME["border"]
    frame.setStyleSheet(
        f"QFrame#Card {{ background-color: transparent;"
        f" border: 1px solid {border}; }}"
    )
    return frame


def stat_strip(parent: Optional[QWidget] = None) -> QFrame:
    """Hairline-bounded status/stats row without a filled background."""
    frame = QFrame(parent)
    frame.setObjectName("StatStrip")
    frame.setStyleSheet(
        f"QFrame#StatStrip {{ background: transparent; border: none;"
        f" border-top: 1px solid {THEME['border']};"
        f" border-bottom: 1px solid {THEME['border']}; }}"
    )
    return frame


def configure_stretch_table(
    table: Union[QTableWidget, QTableView],
    *,
    stretch: Union[int, Sequence[int]],
    min_widths: Optional[Sequence[int]] = None,
) -> None:
    """Interactive columns that grow with the window; stretch named columns."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)
    cols = table.columnCount() if isinstance(table, QTableWidget) else table.model().columnCount()
    stretch_set = {stretch} if isinstance(stretch, int) else set(stretch)
    for i in range(cols):
        if min_widths is not None and i < len(min_widths) and min_widths[i]:
            table.setColumnWidth(i, min_widths[i])
        mode = (
            QHeaderView.ResizeMode.Stretch
            if i in stretch_set
            else QHeaderView.ResizeMode.Interactive
        )
        header.setSectionResizeMode(i, mode)


_BUTTON_STYLES = {
    "primary": (
        f"QPushButton {{"
        f" background-color: {THEME['cta_dark']};"
        f" color: {THEME['cta_dark_text']};"
        f" border: none; border-radius: 6px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #d94400; }}"
        f"QPushButton:pressed {{ background-color: #c03d00; }}"
        f"QPushButton:disabled {{ background-color: {THEME['bg_raised']};"
        f" color: {THEME['text_muted']}; }}"
    ),
    "secondary": (
        f"QPushButton {{"
        f" background-color: {THEME['bg_raised']};"
        f" color: {THEME['text_primary']};"
        f" border: none; border-radius: 4px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
        f"QPushButton:pressed {{ background-color: {THEME['bg_surface']}; }}"
        f"QPushButton:disabled {{ color: {THEME['text_muted']}; }}"
    ),
    "featured": (
        f"QPushButton {{"
        f" background-color: {THEME['bg_featured']};"
        f" color: {THEME['text_strong']};"
        f" border: 1px solid #b17816; border-radius: 6px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
    ),
    "ghost": (
        f"QPushButton {{"
        f" background-color: transparent;"
        f" color: {THEME['text_primary']};"
        f" border: 1px solid {THEME['border']}; border-radius: 4px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
    ),
    "danger": (
        f"QPushButton {{"
        f" background-color: {_DANGER_BG};"
        f" color: #ffffff;"
        f" border: none; border-radius: 6px; padding: 6px 14px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {_DANGER_HOVER}; }}"
        f"QPushButton:pressed {{ background-color: {_DANGER_PRESSED}; }}"
        f"QPushButton:disabled {{ background-color: {THEME['bg_raised']};"
        f" color: {THEME['text_muted']}; }}"
    ),
}


class _HoverFlashFilter(QObject):
    def __init__(self, widget: QWidget, idle: str, hover: str):
        super().__init__(widget)
        self._widget = widget
        self._idle = idle
        self._hover = hover

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is not self._widget:
            return False
        if event.type() == QEvent.Type.Enter:
            _set_text_color(self._widget, self._hover)
        elif event.type() == QEvent.Type.Leave:
            _set_text_color(self._widget, self._idle)
        return False


def create_button(
    parent: Optional[QWidget],
    text: str,
    command: Optional[Callable] = None,
    variant: ButtonVariant = "primary",
    font=None,
    **_overrides,
) -> QPushButton:
    """Build a QPushButton in one of the DESIGN.md variants.

    Variants:
      primary  - orange CTA (Scan, Save, Capture, Upload)
      secondary - muted raised (Refresh, Apply, secondary actions)
      featured - gold-border accent (Save CSV, Distribute Y)
      ghost    - outlined quiet action
      danger   - red destructive (Clear History, Delete, Clear All)
    """
    btn = QPushButton(text, parent)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(_BUTTON_STYLES.get(variant, _BUTTON_STYLES["primary"]))
    if font is not None:
        btn.setFont(font)
    if command is not None:
        btn.clicked.connect(command)

    if variant == "primary":
        idle, hover = THEME["cta_dark_text"], THEME["accent_amber"]
    elif variant == "danger":
        idle, hover = "#ffffff", THEME["accent_amber"]
    elif variant == "featured":
        idle, hover = THEME["text_strong"], THEME["accent_orange"]
    else:
        idle, hover = THEME["text_primary"], THEME["accent_orange"]
    attach_hover_flash(btn, idle, hover)
    return btn


def attach_hover_flash(widget: QWidget, idle_color: str, hover_color: str | None = None):
    """Flash text color on hover for labels/buttons."""
    if hover_color is None:
        hover_color = THEME["accent_orange"]
    filt = _HoverFlashFilter(widget, idle_color, hover_color)
    widget.installEventFilter(filt)
    widget._hover_flash_filter = filt  # type: ignore[attr-defined]
    _set_text_color(widget, idle_color)


def _set_text_color(widget: QWidget, color: str) -> None:
    pal = widget.palette()
    qc = QColor(color)
    if isinstance(widget, QLabel):
        pal.setColor(QPalette.ColorRole.WindowText, qc)
        widget.setPalette(pal)
        widget.setStyleSheet(f"color: {color}; background: transparent;")
        return
    if isinstance(widget, QPushButton):
        pal.setColor(QPalette.ColorRole.ButtonText, qc)
        widget.setPalette(pal)
