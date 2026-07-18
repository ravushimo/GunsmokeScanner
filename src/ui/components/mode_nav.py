"""Gunsmoke | Gacha | Inventory mode switch + underline tab strip."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import customtkinter as ctk

from src.constants import THEME

# (tab_id, label)
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
}

MODE_LABELS = ("Gunsmoke", "Gacha", "Inventory")
MODE_IDS = ("gunsmoke", "gacha", "inventory")

_LABEL_TO_ID = {
    "Gunsmoke": "gunsmoke",
    "Gacha": "gacha",
    "Inventory": "inventory",
}
_ID_TO_LABEL = {v: k for k, v in _LABEL_TO_ID.items()}


def mode_label(mode_id: str) -> str:
    return _ID_TO_LABEL.get(mode_id, "Gunsmoke")


class ModeNav(ctk.CTkFrame):
    """Underline tabs that share the full window width evenly."""

    def __init__(
        self,
        parent,
        fonts,
        *,
        on_tab: Callable[[str, str], None],
    ):
        super().__init__(parent, fg_color=THEME["bg_surface"], corner_radius=0, height=40)
        self.pack_propagate(False)
        self.fonts = fonts
        self.on_tab = on_tab
        self._mode = "gunsmoke"
        self._tab_id = "capture"
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._underlines: Dict[str, ctk.CTkFrame] = {}
        self._cells: List[ctk.CTkFrame] = []

        self._row = ctk.CTkFrame(self, fg_color="transparent")
        self._row.pack(fill=tk.BOTH, expand=True, padx=8, pady=0)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is not self or not self._cells:
            return
        for i, (tab_id, _label) in enumerate(MODE_TABS.get(self._mode, ())):
            if i >= len(self._cells) or tab_id not in self._buttons:
                continue
            cw = self._cells[i].winfo_width()
            if cw > 20:
                self._buttons[tab_id].configure(width=max(60, cw - 8))


    def set_mode(self, mode: str, tab_id: Optional[str] = None) -> None:
        if mode not in MODE_TABS:
            mode = "gunsmoke"
        self._mode = mode
        tabs = MODE_TABS[mode]
        valid = {t[0] for t in tabs}
        if tab_id is None or tab_id not in valid:
            tab_id = tabs[0][0] if tabs else "setup"
        self._tab_id = tab_id
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
        for child in self._row.winfo_children():
            child.destroy()
        self._buttons.clear()
        self._underlines.clear()
        self._cells.clear()

        tabs = list(MODE_TABS[self._mode])
        for i in range(12):
            self._row.grid_columnconfigure(i, weight=0, uniform="")

        for i, (tab_id, label) in enumerate(tabs):
            self._row.grid_columnconfigure(i, weight=1, uniform="modetabs")

            cell = ctk.CTkFrame(self._row, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="nsew", padx=2)
            self._cells.append(cell)

            btn = ctk.CTkButton(
                cell,
                text=label,
                font=self.fonts.ui,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_muted"],
                corner_radius=4,
                height=28,
                # Let grid stretch the button; avoid fixed widths that overflow
                anchor="center",
                command=lambda t=tab_id: self.select_tab(t),
            )
            btn.pack(side=tk.TOP, fill=tk.X, padx=2, pady=(6, 0))

            line = ctk.CTkFrame(
                cell,
                fg_color="transparent",
                height=2,
                corner_radius=0,
            )
            line.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(2, 0))

            self._buttons[tab_id] = btn
            self._underlines[tab_id] = line

        self._paint()

    def _paint(self) -> None:
        for tab_id, btn in self._buttons.items():
            active = tab_id == self._tab_id
            btn.configure(
                text_color=THEME["text_strong"] if active else THEME["text_muted"],
            )
            self._underlines[tab_id].configure(
                fg_color=THEME["cta_dark"] if active else "transparent"
            )


def build_mode_switch(
    parent,
    fonts,
    *,
    initial: str,
    on_mode: Callable[[str], None],
) -> ctk.CTkSegmentedButton:
    """Compact Gunsmoke | Gacha | Inventory control for the header."""
    label = _ID_TO_LABEL.get(initial, "Gunsmoke")
    seg = ctk.CTkSegmentedButton(
        parent,
        values=list(MODE_LABELS),
        font=fonts.ui,
        selected_color=THEME["cta_dark"],
        selected_hover_color="#d94400",
        unselected_color=THEME["bg_raised"],
        unselected_hover_color=THEME["bg_hover"],
        fg_color=THEME["bg_raised"],
        text_color=THEME["text_strong"],
        height=32,
        command=lambda v: on_mode(_LABEL_TO_ID.get(v, "gunsmoke")),
    )
    seg.set(label)
    return seg
