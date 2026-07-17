"""Compact dark-themed date picker (entry + calendar popup)."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from typing import Callable, Optional

import customtkinter as ctk

from src.constants import THEME

_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


class DatePickerField(ctk.CTkFrame):
    """Shows YYYY-MM-DD; click opens a month calendar. Empty = no filter."""

    def __init__(
        self,
        parent,
        fonts,
        *,
        width: int = 130,
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.fonts = fonts
        self.on_change = on_change
        self._popup: Optional[ctk.CTkToplevel] = None
        self._view = date.today().replace(day=1)

        self._btn = ctk.CTkButton(
            self,
            text="",
            width=width,
            height=28,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_input"],
            font=fonts.mono,
            corner_radius=4,
            border_width=1,
            border_color=THEME["border"],
            anchor="w",
            command=self._toggle_popup,
        )
        self._btn.pack(side=tk.LEFT)
        self._set_display(None)

        clear = ctk.CTkButton(
            self,
            text="×",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_muted"],
            font=fonts.ui,
            corner_radius=4,
            command=self.clear,
        )
        clear.pack(side=tk.LEFT, padx=(2, 0))

    def get(self) -> str:
        """Return YYYY-MM-DD or empty string."""
        text = self._btn.cget("text")
        if not text or text == "Any date":
            return ""
        return text.strip()

    def set(self, value: Optional[str]) -> None:
        if not value:
            self._set_display(None)
            return
        try:
            d = datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            self._set_display(None)
            return
        self._set_display(d)

    def clear(self) -> None:
        self._set_display(None)
        self._close_popup()
        if self.on_change:
            self.on_change()

    def _set_display(self, d: Optional[date]) -> None:
        if d is None:
            self._btn.configure(text="Any date", text_color=THEME["text_placeholder"])
            self._selected: Optional[date] = None
        else:
            self._btn.configure(text=d.isoformat(), text_color=THEME["text_input"])
            self._selected = d
            self._view = d.replace(day=1)

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._close_popup()
            return
        self._open_popup()

    def _close_popup(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None

    def _open_popup(self) -> None:
        self._close_popup()
        pop = ctk.CTkToplevel(self)
        pop.title("Pick date")
        pop.resizable(False, False)
        pop.configure(fg_color=THEME["bg_surface"])
        pop.transient(self.winfo_toplevel())
        pop.attributes("-topmost", True)
        self._popup = pop

        # Place under the button
        self.update_idletasks()
        x = self._btn.winfo_rootx()
        y = self._btn.winfo_rooty() + self._btn.winfo_height() + 4
        pop.geometry(f"+{x}+{y}")

        body = ctk.CTkFrame(pop, fg_color=THEME["bg_surface"], corner_radius=0)
        body.pack(padx=8, pady=8)

        nav = ctk.CTkFrame(body, fg_color="transparent")
        nav.pack(fill=tk.X, pady=(0, 6))

        ctk.CTkButton(
            nav,
            text="‹",
            width=32,
            height=28,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_strong"],
            font=self.fonts.ui,
            command=lambda: self._shift_month(-1),
        ).pack(side=tk.LEFT)

        self._month_lbl = ctk.CTkLabel(
            nav,
            text="",
            font=self.fonts.ui,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            width=140,
        )
        self._month_lbl.pack(side=tk.LEFT, expand=True)

        ctk.CTkButton(
            nav,
            text="›",
            width=32,
            height=28,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_strong"],
            font=self.fonts.ui,
            command=lambda: self._shift_month(1),
        ).pack(side=tk.RIGHT)

        self._grid = ctk.CTkFrame(body, fg_color="transparent")
        self._grid.pack()

        foot = ctk.CTkFrame(body, fg_color="transparent")
        foot.pack(fill=tk.X, pady=(8, 0))
        ctk.CTkButton(
            foot,
            text="Today",
            width=70,
            height=26,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            font=self.fonts.caption,
            command=self._pick_today,
        ).pack(side=tk.LEFT)
        ctk.CTkButton(
            foot,
            text="Clear",
            width=70,
            height=26,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_muted"],
            font=self.fonts.caption,
            command=self.clear,
        ).pack(side=tk.RIGHT)

        self._render_month()
        pop.bind("<Escape>", lambda _e: self._close_popup())
        pop.focus_force()

        # Close when focus leaves (click outside)
        pop.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, _event=None) -> None:
        if self._popup is None:
            return
        try:
            focused = self._popup.focus_get()
        except tk.TclError:
            focused = None
        if focused is None:
            # Defer — clicking a day button steals focus briefly
            self.after(120, self._maybe_close_if_unfocused)

    def _maybe_close_if_unfocused(self) -> None:
        if self._popup is None or not self._popup.winfo_exists():
            return
        try:
            focused = self._popup.focus_get()
        except tk.TclError:
            focused = None
        if focused is None:
            self._close_popup()

    def _shift_month(self, delta: int) -> None:
        y, m = self._view.year, self._view.month + delta
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        self._view = date(y, m, 1)
        self._render_month()

    def _pick_today(self) -> None:
        self._select(date.today())

    def _select(self, d: date) -> None:
        self._set_display(d)
        self._close_popup()
        if self.on_change:
            self.on_change()

    def _render_month(self) -> None:
        for child in self._grid.winfo_children():
            child.destroy()

        self._month_lbl.configure(text=self._view.strftime("%B %Y"))
        today = date.today()
        selected = self._selected

        for i, wd in enumerate(_WEEKDAYS):
            ctk.CTkLabel(
                self._grid,
                text=wd,
                width=32,
                height=22,
                font=self.fonts.caption,
                text_color=THEME["text_muted"],
                fg_color="transparent",
            ).grid(row=0, column=i, padx=1, pady=1)

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._view.year, self._view.month
        )
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(
                        self._grid,
                        text="",
                        width=32,
                        height=28,
                        fg_color="transparent",
                    ).grid(row=r, column=c, padx=1, pady=1)
                    continue
                d = date(self._view.year, self._view.month, day)
                is_sel = selected == d
                is_today = today == d
                fg = THEME["cta_dark"] if is_sel else THEME["bg_raised"]
                hover = "#d94400" if is_sel else THEME["bg_hover"]
                tc = THEME["cta_dark_text"] if is_sel else THEME["text_strong"]
                if is_today and not is_sel:
                    tc = THEME["accent_amber"]
                btn = ctk.CTkButton(
                    self._grid,
                    text=str(day),
                    width=32,
                    height=28,
                    fg_color=fg,
                    hover_color=hover,
                    text_color=tc,
                    font=self.fonts.caption,
                    corner_radius=4,
                    command=lambda dd=d: self._select(dd),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)
