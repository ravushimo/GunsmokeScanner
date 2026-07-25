"""Compact dark-themed date picker (entry + calendar popup)."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Callable, ClassVar, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME

_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


class _OutsideClickFilter(QObject):
    """Defer outside-click dismissal so day buttons receive their click first."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress:
            picker = DatePickerField._active
            if picker is not None:
                picker._schedule_dismiss_if_outside(event.globalPosition().toPoint())
        return False


class _DatePickerPopup(QDialog):
    """Frameless calendar popup positioned below the date field."""

    def __init__(self, picker: "DatePickerField"):
        super().__init__(picker, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._picker = picker
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(f"background-color: {THEME['bg_surface']};")

        outer = QFrame(self)
        outer.setStyleSheet(
            f"QFrame {{"
            f" background-color: {THEME['bg_surface']};"
            f" border: 1px solid {_blend(THEME['border'], THEME['element_freeze'], 0.45)};"
            f" border-radius: 6px;"
            f"}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        inner = QVBoxLayout(outer)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(6)

        nav = QHBoxLayout()
        nav.setSpacing(4)

        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(32, 28)
        prev_btn.setFont(picker.fonts.ui)
        prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        prev_btn.setStyleSheet(_raised_button_style())
        prev_btn.clicked.connect(lambda: picker._shift_month(-1))
        nav.addWidget(prev_btn)

        self._month_lbl = QLabel("")
        self._month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_lbl.setFont(picker.fonts.ui)
        self._month_lbl.setStyleSheet(
            f"color: {THEME['element_freeze']}; background: transparent; min-width: 140px;"
        )
        nav.addWidget(self._month_lbl, stretch=1)

        next_btn = QPushButton("›")
        next_btn.setFixedSize(32, 28)
        next_btn.setFont(picker.fonts.ui)
        next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        next_btn.setStyleSheet(_raised_button_style())
        next_btn.clicked.connect(lambda: picker._shift_month(1))
        nav.addWidget(next_btn)

        inner.addLayout(nav)

        self._grid_host = QWidget()
        self._grid_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(2)
        inner.addWidget(self._grid_host)

        foot = QHBoxLayout()
        foot.setSpacing(4)

        today_btn = QPushButton("Today")
        today_btn.setFixedSize(70, 26)
        today_btn.setFont(picker.fonts.caption)
        today_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        today_btn.setStyleSheet(
            f"QPushButton {{"
            f" background-color: {THEME['class_support']};"
            f" color: #ffffff;"
            f" border: none; border-radius: 4px;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: {_blend(THEME['class_support'], '#ffffff', 0.15)};"
            f"}}"
        )
        today_btn.clicked.connect(picker._pick_today)
        foot.addWidget(today_btn)

        foot.addStretch(1)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(70, 26)
        clear_btn.setFont(picker.fonts.caption)
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.setStyleSheet(_ghost_button_style())
        clear_btn.clicked.connect(picker.clear)
        foot.addWidget(clear_btn)

        inner.addLayout(foot)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._picker._close_popup()
            return
        super().keyPressEvent(event)


class DatePickerField(QWidget):
    """Shows YYYY-MM-DD; click opens a month calendar. Empty = no filter."""

    _active: ClassVar[Optional["DatePickerField"]] = None
    _outside_filter: ClassVar[Optional[_OutsideClickFilter]] = None

    def __init__(
        self,
        parent,
        fonts,
        *,
        width: int = 104,
        placeholder: str = "Any date",
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.fonts = fonts
        self.on_change = on_change
        self._placeholder = placeholder
        self._popup: Optional[_DatePickerPopup] = None
        self._view = date.today().replace(day=1)
        self._selected: Optional[date] = None
        self._dismiss_timer: Optional[QTimer] = None

        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        border = _blend(THEME["border"], THEME["element_freeze"], 0.35)
        self._btn = QPushButton("", self)
        self._btn.setFixedSize(width, 28)
        self._btn.setFont(fonts.mono)
        self._btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn.setStyleSheet(
            f"QPushButton {{"
            f" background-color: {THEME['bg_raised']};"
            f" color: {THEME['text_input']};"
            f" border: 1px solid {border};"
            f" border-radius: 4px;"
            f" padding: 2px 8px;"
            f" text-align: left;"
            f"}}"
            f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
        )
        self._btn.clicked.connect(self._toggle_popup)
        layout.addWidget(self._btn)

        clear = QPushButton("×", self)
        clear.setFixedSize(26, 28)
        clear.setFont(fonts.ui)
        clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear.setStyleSheet(
            f"QPushButton {{"
            f" background-color: transparent;"
            f" color: {THEME['text_muted']};"
            f" border: none; border-radius: 4px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
        )
        clear.clicked.connect(self.clear)
        layout.addWidget(clear)

        self._set_display(None)

    def get(self) -> str:
        """Return YYYY-MM-DD or empty string."""
        text = self._btn.text().strip()
        if not text or text == self._placeholder:
            return ""
        return text

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
            self._btn.setText(self._placeholder)
            self._btn.setStyleSheet(self._field_button_style(placeholder=True))
            self._selected = None
        else:
            self._btn.setText(d.isoformat())
            self._btn.setStyleSheet(self._field_button_style(placeholder=False))
            self._selected = d
            self._view = d.replace(day=1)

    def _field_button_style(self, *, placeholder: bool) -> str:
        border = _blend(THEME["border"], THEME["element_freeze"], 0.35)
        text_color = (
            THEME["text_placeholder"] if placeholder else THEME["text_input"]
        )
        return (
            f"QPushButton {{"
            f" background-color: {THEME['bg_raised']};"
            f" color: {text_color};"
            f" border: 1px solid {border};"
            f" border-radius: 4px;"
            f" padding: 2px 8px;"
            f" text-align: left;"
            f"}}"
            f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
        )

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._close_popup()
            return
        self._open_popup()

    def _close_popup(self) -> None:
        if self._popup is not None:
            self._popup.hide()
            self._popup.deleteLater()
        self._popup = None
        if DatePickerField._active is self:
            DatePickerField._active = None
        self._cancel_dismiss_timer()

    def _open_popup(self) -> None:
        if DatePickerField._active is not None and DatePickerField._active is not self:
            DatePickerField._active._close_popup()

        self._close_popup()
        pop = _DatePickerPopup(self)
        self._popup = pop
        DatePickerField._active = self

        self._render_month()
        pop.adjustSize()

        anchor = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 4))
        pop.move(anchor)
        pop.show()
        pop.raise_()
        pop.activateWindow()
        self._ensure_outside_filter()

    def _ensure_outside_filter(self) -> None:
        if DatePickerField._outside_filter is not None:
            return
        from PySide6.QtWidgets import QApplication

        filt = _OutsideClickFilter()
        QApplication.instance().installEventFilter(filt)
        DatePickerField._outside_filter = filt

    def _schedule_dismiss_if_outside(self, global_pos: QPoint) -> None:
        if DatePickerField._active is not self:
            return
        self._cancel_dismiss_timer()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._dismiss_if_outside(global_pos))
        timer.start(10)
        self._dismiss_timer = timer

    def _cancel_dismiss_timer(self) -> None:
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer.deleteLater()
            self._dismiss_timer = None

    def _dismiss_if_outside(self, global_pos: QPoint) -> None:
        self._dismiss_timer = None
        if self._popup is None or not self._popup.isVisible():
            return
        if _point_in_widget(self._popup, global_pos):
            return
        if _point_in_widget(self._btn, global_pos):
            return
        if _point_in_widget(self, global_pos):
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
        if self._popup is None:
            return

        _clear_layout(self._popup._grid)

        self._popup._month_lbl.setText(self._view.strftime("%B %Y"))
        today = date.today()
        selected = self._selected

        for i, wd in enumerate(_WEEKDAYS):
            lbl = QLabel(wd)
            lbl.setFixedSize(32, 22)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(self.fonts.caption)
            lbl.setStyleSheet(
                f"color: {THEME['text_muted']}; background: transparent;"
            )
            self._popup._grid.addWidget(lbl, 0, i)

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._view.year, self._view.month
        )
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    spacer = QWidget()
                    spacer.setFixedSize(32, 28)
                    spacer.setStyleSheet("background: transparent;")
                    self._popup._grid.addWidget(spacer, r, c)
                    continue

                d = date(self._view.year, self._view.month, day)
                is_sel = selected == d
                is_today = today == d
                btn = QPushButton(str(day))
                btn.setFixedSize(32, 28)
                btn.setFont(self.fonts.caption)
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.setStyleSheet(_day_button_style(is_sel, is_today))
                btn.clicked.connect(lambda _checked=False, dd=d: self._select(dd))
                self._popup._grid.addWidget(btn, r, c)


def _raised_button_style() -> str:
    return (
        f"QPushButton {{"
        f" background-color: {THEME['bg_raised']};"
        f" color: {THEME['text_strong']};"
        f" border: none; border-radius: 4px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
    )


def _ghost_button_style() -> str:
    return (
        f"QPushButton {{"
        f" background-color: transparent;"
        f" color: {THEME['text_muted']};"
        f" border: none; border-radius: 4px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; }}"
    )


def _day_button_style(is_selected: bool, is_today: bool) -> str:
    if is_selected:
        fg = THEME["element_burn"]
        hover = _blend(THEME["element_burn"], "#ffffff", 0.12)
        text = "#ffffff"
    elif is_today:
        fg = THEME["bg_raised"]
        hover = THEME["bg_hover"]
        text = THEME["element_freeze"]
    else:
        fg = THEME["bg_raised"]
        hover = THEME["bg_hover"]
        text = THEME["text_strong"]
    return (
        f"QPushButton {{"
        f" background-color: {fg};"
        f" color: {text};"
        f" border: none; border-radius: 4px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {hover}; }}"
    )


def _clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


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


def _point_in_widget(widget: QWidget, global_pos: QPoint) -> bool:
    if not widget.isVisible():
        return False
    top_left = widget.mapToGlobal(QPoint(0, 0))
    rect = widget.rect()
    return (
        top_left.x() <= global_pos.x() < top_left.x() + rect.width()
        and top_left.y() <= global_pos.y() < top_left.y() + rect.height()
    )
