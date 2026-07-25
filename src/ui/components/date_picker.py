"""Compact dark-themed date picker (entry + calendar popup)."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from typing import Callable, ClassVar, Optional

import customtkinter as ctk

from src.constants import THEME

_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


class DatePickerField(ctk.CTkFrame):
    """Shows YYYY-MM-DD; click opens a month calendar. Empty = no filter."""

    _active: ClassVar[Optional["DatePickerField"]] = None
    _root_bind: ClassVar[Optional[str]] = None

    def __init__(
        self,
        parent,
        fonts,
        *,
        width: int = 104,
        placeholder: str = "Any date",
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.fonts = fonts
        self.on_change = on_change
        self._placeholder = placeholder
        self._popup: Optional[ctk.CTkToplevel] = None
        self._view = date.today().replace(day=1)
        self._selected: Optional[date] = None
        self._root_press_after: Optional[str] = None

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
            border_color=_blend(THEME["border"], THEME["element_freeze"], 0.35),
            anchor="w",
            command=self._toggle_popup,
        )
        self._btn.pack(side=tk.LEFT)
        self._set_display(None)

        clear = ctk.CTkButton(
            self,
            text="×",
            width=26,
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
        if not text or text == self._placeholder:
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
            self._btn.configure(
                text=self._placeholder, text_color=THEME["text_placeholder"]
            )
            self._selected = None
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
        if DatePickerField._active is self:
            DatePickerField._active = None

    def _open_popup(self) -> None:
        if DatePickerField._active is not None and DatePickerField._active is not self:
            DatePickerField._active._close_popup()

        self._close_popup()
        pop = ctk.CTkToplevel(self)
        pop.title("Pick date")
        pop.resizable(False, False)
        pop.configure(fg_color=THEME["bg_surface"])
        pop.transient(self.winfo_toplevel())
        pop.attributes("-topmost", True)
        # Undecorated tool window feel — still closes on outside click
        try:
            pop.overrideredirect(True)
        except tk.TclError:
            pass
        self._popup = pop
        DatePickerField._active = self

        self.update_idletasks()
        x = self._btn.winfo_rootx()
        y = self._btn.winfo_rooty() + self._btn.winfo_height() + 4
        pop.geometry(f"+{x}+{y}")

        body = ctk.CTkFrame(
            pop,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=_blend(THEME["border"], THEME["element_freeze"], 0.45),
        )
        body.pack(padx=0, pady=0)

        inner = ctk.CTkFrame(body, fg_color="transparent")
        inner.pack(padx=8, pady=8)

        nav = ctk.CTkFrame(inner, fg_color="transparent")
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
            text_color=THEME["element_freeze"],
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

        self._grid = ctk.CTkFrame(inner, fg_color="transparent")
        self._grid.pack()

        foot = ctk.CTkFrame(inner, fg_color="transparent")
        foot.pack(fill=tk.X, pady=(8, 0))
        ctk.CTkButton(
            foot,
            text="Today",
            width=70,
            height=26,
            fg_color=THEME["class_support"],
            hover_color=_blend(THEME["class_support"], "#ffffff", 0.15),
            text_color="#ffffff",
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
        self._ensure_root_bind()
        # Defer so the opening click doesn't immediately dismiss
        self.after(50, lambda: None)

    def _ensure_root_bind(self) -> None:
        root = self.winfo_toplevel()
        if DatePickerField._root_bind is not None:
            return
        DatePickerField._root_bind = root.bind(
            "<ButtonPress-1>", DatePickerField._on_root_press, add="+"
        )

    @classmethod
    def _on_root_press(cls, event) -> None:
        picker = cls._active
        if picker is None or picker._popup is None:
            return
        # Defer so day-button commands run before we tear down the popup
        if picker._root_press_after:
            try:
                picker.after_cancel(picker._root_press_after)
            except (tk.TclError, ValueError):
                pass
        picker._root_press_after = picker.after(
            10, lambda e=event: picker._dismiss_if_outside(e)
        )

    def _dismiss_if_outside(self, event) -> None:
        self._root_press_after = None
        if self._popup is None or not self._popup.winfo_exists():
            return
        try:
            x, y = int(event.x_root), int(event.y_root)
        except (tk.TclError, TypeError, ValueError):
            self._close_popup()
            return

        if _point_in_widget(self._popup, x, y):
            return
        if _point_in_widget(self._btn, x, y):
            return  # toggle handles close
        if _point_in_widget(self, x, y):
            return
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
                if is_sel:
                    fg = THEME["element_burn"]
                    hover = _blend(THEME["element_burn"], "#ffffff", 0.12)
                    tc = "#ffffff"
                elif is_today:
                    fg = THEME["bg_raised"]
                    hover = THEME["bg_hover"]
                    tc = THEME["element_freeze"]
                else:
                    fg = THEME["bg_raised"]
                    hover = THEME["bg_hover"]
                    tc = THEME["text_strong"]
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


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(hex_a: str, hex_b: str, t: float) -> str:
    ar, ag, ab = _hex_rgb(hex_a)
    br, bg, bb = _hex_rgb(hex_b)
    r = int(round(ar + (br - ar) * t))
    g = int(round(ag + (bg - ag) * t))
    b = int(round(ab + (bb - ab) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def _point_in_widget(widget, x_root: int, y_root: int) -> bool:
    try:
        if not widget.winfo_exists():
            return False
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        w = widget.winfo_width()
        h = widget.winfo_height()
        return x <= x_root < x + w and y <= y_root < y + h
    except tk.TclError:
        return False
