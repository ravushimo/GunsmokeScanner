"""Gunsmoke | Gacha | Inventory | Settings mode switch + underline tab strip."""

from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME

ModeTabs = Sequence[Tuple[str, str]]

MODE_TABS: Dict[str, ModeTabs] = {
    "gunsmoke": (
        ("setup", "Setup"),
        ("capture", "Capture"),
        ("upload", "Upload"),
    ),
    "gacha": (
        ("setup", "Setup"),
        ("capture", "Capture"),
        ("history", "History"),
        ("stats", "Stats"),
        ("collection", "Collection"),
    ),
    "inventory": (
        ("setup", "Setup"),
        ("capture", "Capture"),
        ("list", "Inventory"),
    ),
    "settings": (
        ("main", "Settings"),
    ),
}

MODE_LABELS = ("Gunsmoke", "Gacha", "Inventory", "Settings")
MODE_IDS = ("gunsmoke", "gacha", "inventory", "settings")

_LABEL_TO_ID = {
    "Gunsmoke": "gunsmoke",
    "Gacha": "gacha",
    "Inventory": "inventory",
    "Settings": "settings",
}
_ID_TO_LABEL = {v: k for k, v in _LABEL_TO_ID.items()}


def mode_label(mode_id: str) -> str:
    return _ID_TO_LABEL.get(mode_id, "Gunsmoke")


class ModeNav(QFrame):
    """Underline tabs that share the full window width evenly."""

    def __init__(
        self,
        parent,
        fonts,
        *,
        on_tab: Callable[[str, str], None],
    ):
        super().__init__(parent)
        self.setObjectName("ModeNav")
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"QFrame#ModeNav {{ background-color: {THEME['bg_canvas']}; border: none; }}"
        )
        self.fonts = fonts
        self.on_tab = on_tab
        self._mode = "gunsmoke"
        self._tab_id = "capture"
        self._buttons: Dict[str, QPushButton] = {}
        self._underlines: Dict[str, QFrame] = {}

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(8, 0, 8, 0)
        self._row.setSpacing(2)

    def set_mode(self, mode: str, tab_id: Optional[str] = None) -> None:
        if mode not in MODE_TABS:
            mode = "gunsmoke"
        self._mode = mode
        tabs = MODE_TABS[mode]
        valid = {t[0] for t in tabs}
        if tab_id is None or tab_id not in valid:
            tab_id = tabs[0][0] if tabs else "setup"
        self._tab_id = tab_id
        # Settings is a single page - hide the underline strip.
        self.setVisible(mode != "settings")
        self._rebuild()
        self.on_tab(self._mode, self._tab_id)

    def select_tab(self, tab_id: str, *, notify: bool = True) -> None:
        valid = {t[0] for t in MODE_TABS.get(self._mode, ())}
        if tab_id not in valid:
            return
        self._tab_id = tab_id
        self._paint()
        if notify:
            self.on_tab(self._mode, self._tab_id)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def tab_id(self) -> str:
        return self._tab_id

    def _rebuild(self) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()
        self._underlines.clear()

        for tab_id, label in MODE_TABS[self._mode]:
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cell_lay = QVBoxLayout(cell)
            cell_lay.setContentsMargins(2, 6, 2, 0)
            cell_lay.setSpacing(2)

            btn = QPushButton(label)
            btn.setFont(self.fonts.ui)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked=False, t=tab_id: self.select_tab(t))
            cell_lay.addWidget(btn)

            line = QFrame()
            line.setFixedHeight(2)
            line.setStyleSheet("background: transparent; border: none;")
            cell_lay.addWidget(line)

            self._row.addWidget(cell, 1)
            self._buttons[tab_id] = btn
            self._underlines[tab_id] = line

        self._paint()

    def _paint(self) -> None:
        for tab_id, btn in self._buttons.items():
            active = tab_id == self._tab_id
            color = THEME["text_strong"] if active else THEME["text_muted"]
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none;"
                f" color: {color}; border-radius: 4px; }}"
                f"QPushButton:hover {{ background: {THEME['bg_hover']}; }}"
            )
            line = self._underlines[tab_id]
            if active:
                line.setStyleSheet(
                    f"background: {THEME['cta_dark']}; border: none;"
                )
            else:
                line.setStyleSheet("background: transparent; border: none;")


class ModeSwitch(QFrame):
    """Compact Gunsmoke | Gacha | Inventory segmented control."""

    modeChanged = Signal(str)

    def __init__(self, parent, fonts, *, initial: str = "gunsmoke"):
        super().__init__(parent)
        self.setObjectName("ModeSwitch")
        self.fonts = fonts
        self.setStyleSheet(
            "QFrame#ModeSwitch { background: transparent; border: none; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: Dict[str, QPushButton] = {}

        for label in MODE_LABELS:
            mode_id = _LABEL_TO_ID[label]
            btn = QPushButton(label)
            btn.setFont(fonts.ui)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._group.addButton(btn)
            lay.addWidget(btn, 1)
            self._buttons[mode_id] = btn
            btn.clicked.connect(lambda checked=False, m=mode_id: self._emit(m))

        self.set(mode_label(initial))
        self._paint()

    def _emit(self, mode_id: str) -> None:
        self._paint()
        self.modeChanged.emit(mode_id)

    def set(self, label: str) -> None:
        mode_id = _LABEL_TO_ID.get(label, "gunsmoke")
        btn = self._buttons.get(mode_id)
        if btn:
            btn.setChecked(True)
            self._paint()

    def _paint(self) -> None:
        for mode_id, btn in self._buttons.items():
            if btn.isChecked():
                btn.setStyleSheet(
                    f"QPushButton {{ background: {THEME['cta_dark']};"
                    f" color: {THEME['cta_dark_text']}; border: none;"
                    f" border-radius: 5px; padding: 4px 8px; font-weight: 600; }}"
                    f"QPushButton:hover {{ background: #d94400; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent;"
                    f" color: {THEME['text_muted']}; border: none;"
                    f" border-radius: 5px; padding: 4px 8px; }}"
                    f"QPushButton:hover {{ background: {THEME['bg_hover']};"
                    f" color: {THEME['text_strong']}; }}"
                )


def build_mode_switch(
    parent,
    fonts,
    *,
    initial: str,
    on_mode: Callable[[str], None],
) -> ModeSwitch:
    """Compact Gunsmoke | Gacha | Inventory | Settings control for the header."""
    seg = ModeSwitch(parent, fonts, initial=initial)
    seg.modeChanged.connect(on_mode)
    return seg
