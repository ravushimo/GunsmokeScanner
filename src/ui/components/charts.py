"""Lightweight Qt charts (no matplotlib dependency)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.constants import THEME

# GFL2 type + class colors (DESIGN.md) - distinct on dark canvas
_PALETTE = (
    THEME["element_burn"],
    THEME["element_corrosion"],
    THEME["element_electric"],
    THEME["element_freeze"],
    THEME["element_hydro"],
    THEME["element_omni"],
    THEME["class_vanguard"],
    THEME["class_bulwark"],
    THEME["class_support"],
    THEME["class_sentinel"],
    THEME["element_physical"],
)

# Support (lucky) -> Electric -> Omni (worst-case V6)
_LUCK_GREEN = (75, 126, 91)       # class_support
_LUCK_YELLOW = (255, 215, 0)      # element_electric
_LUCK_RED = (224, 49, 49)         # element_omni

_SURFACE_STYLE = (
    f"QFrame#ChartSurface {{ background-color: {THEME['bg_surface']}; "
    f"border: 1px solid {THEME['border']}; }}"
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def luck_color(ratio: float) -> str:
    """Map 0..1 (pulls / worst V6) to green -> yellow -> red."""
    t = max(0.0, min(1.0, float(ratio)))
    if t <= 0.5:
        u = t / 0.5
        rgb = tuple(_lerp(_LUCK_GREEN[i], _LUCK_YELLOW[i], u) for i in range(3))
    else:
        u = (t - 0.5) / 0.5
        rgb = tuple(_lerp(_LUCK_YELLOW[i], _LUCK_RED[i], u) for i in range(3))
    return _rgb_to_hex(rgb)


def _shade(hex_color: str, factor: float) -> str:
    """Lighten (factor>1) or darken (factor<1) a #rrggbb color."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _chart_font(size: int, *, bold: bool = False, fonts=None) -> QFont:
    family = fonts.family if fonts else "Segoe UI"
    font = QFont(family, size)
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    return font


def _title_font(fonts=None) -> QFont:
    if fonts:
        return fonts.subheading
    font = QFont("Segoe UI", 16)
    font.setWeight(QFont.Weight.Bold)
    return font


def _draw_text(
    painter: QPainter,
    x: float,
    y: float,
    text: str,
    *,
    anchor: str = "w",
    color: str = THEME["text_primary"],
    font: Optional[QFont] = None,
) -> None:
    painter.setPen(QColor(color))
    if font is not None:
        painter.setFont(font)
    metrics = QFontMetrics(painter.font())
    tw = metrics.horizontalAdvance(text)
    th = metrics.height()
    if anchor == "e":
        tx, ty = x - tw, y - th / 2
    elif anchor == "center":
        tx, ty = x - tw / 2, y - th / 2
    elif anchor == "s":
        tx, ty = x - tw / 2, y - th
    elif anchor == "n":
        tx, ty = x - tw / 2, y
    else:
        tx, ty = x, y - th / 2
    painter.drawText(int(tx), int(ty + metrics.ascent()), text)


def _heat_color(count: int, peak: int) -> str:
    if count <= 0 or peak <= 0:
        return THEME["bg_raised"]
    t = min(1.0, count / peak)
    # Neutral intensity ramp - easy day-to-day contrast on dark UI
    cold = (55, 58, 52)
    mid = (247, 165, 1)     # amber
    hot = (245, 78, 0)      # CTA orange
    if t < 0.5:
        u = t / 0.5
        rgb = tuple(_lerp(cold[i], mid[i], u) for i in range(3))
    else:
        u = (t - 0.5) / 0.5
        rgb = tuple(_lerp(mid[i], hot[i], u) for i in range(3))
    return _rgb_to_hex(rgb)


class _ChartCanvas(QWidget):
    """Drawing surface for ChartFrame."""

    def __init__(self, chart: "ChartFrame", height: int):
        super().__init__(chart)
        self._chart = chart
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(THEME["bg_canvas"]))
        w = max(self.width(), 40)
        h = max(self.height(), 40)
        self._chart._paint(painter, w, h)
        painter.end()


class ChartFrame(QFrame):
    """Pie, bar, or stacked campaign-luck bar chart."""

    def __init__(
        self,
        parent,
        title: str,
        *,
        kind: str = "bar",
        height: int = 220,
        fonts=None,
    ):
        super().__init__(parent)
        self.setObjectName("ChartSurface")
        self.setStyleSheet(_SURFACE_STYLE)

        self.kind = kind
        self._fonts = fonts
        self._data: Any = {}
        # Color scale only (worst-case V6); bar width uses dataset max
        self._luck_max: float = 1120.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 3)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(_title_font(fonts))
        title_label.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        title_label.setFixedHeight(22)
        layout.addWidget(title_label)

        canvas_wrap = QWidget()
        canvas_wrap.setStyleSheet("background: transparent;")
        canvas_layout = QVBoxLayout(canvas_wrap)
        canvas_layout.setContentsMargins(3, 1, 3, 0)
        canvas_layout.setSpacing(0)
        self._canvas = _ChartCanvas(self, height)
        canvas_layout.addWidget(self._canvas)
        layout.addWidget(canvas_wrap, 1)

    def set_data(
        self,
        data: Optional[Union[Dict[str, float], List[Dict[str, Any]]]],
        *,
        luck_max: Optional[float] = None,
    ) -> None:
        if luck_max is not None:
            self._luck_max = float(luck_max)
        if self.kind == "campaign":
            self._data = list(data or [])
        else:
            self._data = {k: float(v) for k, v in (data or {}).items() if v}
        self._canvas.update()

    def _paint(self, painter: QPainter, w: int, h: int) -> None:
        if self.kind == "campaign":
            rows = list(self._data or [])
            if not rows:
                self._empty(painter, w, h)
                return
            self._draw_campaign_bars(painter, rows, w, h)
            return

        items = sorted(self._data.items(), key=lambda kv: -kv[1])
        if not items:
            self._empty(painter, w, h)
            return
        if self.kind == "pie":
            self._draw_pie(painter, items, w, h)
        else:
            self._draw_bar(painter, items, w, h)

    def _empty(self, painter: QPainter, w: int, h: int) -> None:
        _draw_text(
            painter,
            w / 2,
            h / 2,
            "No data",
            anchor="center",
            color=THEME["text_muted"],
            font=_chart_font(11, fonts=self._fonts),
        )

    def _draw_pie(
        self,
        painter: QPainter,
        items: Sequence[Tuple[str, float]],
        w: int,
        h: int,
    ) -> None:
        total = sum(v for _, v in items) or 1.0
        size = min(w * 0.42, h - 20)
        cx, cy = w * 0.28, h / 2
        x0, y0 = cx - size / 2, cy - size / 2
        pie_rect = QRectF(x0, y0, size, size)
        start = 90.0
        legend_x = w * 0.55
        legend_y = 12
        body_font = _chart_font(9, fonts=self._fonts)
        painter.setPen(QPen(QColor(THEME["bg_canvas"]), 2))

        for i, (label, value) in enumerate(items):
            extent = -360.0 * (value / total)
            color = _PALETTE[i % len(_PALETTE)]
            if abs(extent) < 0.5:
                continue
            painter.setBrush(QColor(color))
            painter.drawPie(pie_rect, int(start * 16), int(extent * 16))
            start += extent
            pct = 100.0 * value / total
            painter.fillRect(QRectF(legend_x, legend_y, 10, 10), QColor(color))
            _draw_text(
                painter,
                legend_x + 16,
                legend_y + 5,
                f"{label}  {int(value)} ({pct:.0f}%)",
                anchor="w",
                color=THEME["text_primary"],
                font=body_font,
            )
            legend_y += 18

    def _draw_bar(
        self,
        painter: QPainter,
        items: Sequence[Tuple[str, float]],
        w: int,
        h: int,
    ) -> None:
        items = list(items)[:12]
        max_v = max(v for _, v in items) or 1.0
        pad_l, pad_r, pad_t = 6, 8, 4
        row_h = max(16, (h - pad_t - 4) / max(len(items), 1))
        label_w = min(110, w * 0.32)
        value_w = 40
        bar_x0 = pad_l + label_w + 6
        bar_x1 = w - pad_r - value_w
        body_font = _chart_font(9, fonts=self._fonts)

        for i, (label, value) in enumerate(items):
            y = pad_t + i * row_h
            cy = y + row_h / 2
            short = label if len(label) <= 16 else label[:14] + "\u2026"
            _draw_text(
                painter,
                pad_l + label_w,
                cy,
                short,
                anchor="e",
                color=THEME["text_muted"],
                font=body_font,
            )
            bw = max(bar_x1 - bar_x0, 4) * (value / max_v)
            color = _PALETTE[i % len(_PALETTE)]
            painter.fillRect(
                QRectF(bar_x0, cy - 5, max(bw, 2), 10),
                QColor(color),
            )
            _draw_text(
                painter,
                w - pad_r,
                cy,
                str(int(value)),
                anchor="e",
                color=THEME["text_strong"],
                font=body_font,
            )

    def _draw_campaign_bars(
        self,
        painter: QPainter,
        rows: List[Dict[str, Any]],
        w: int,
        h: int,
    ) -> None:
        """Stacked per-copy segments; bar width vs dataset max; color vs luck max."""
        rows = rows[:12]
        bar_scale = max((float(r.get("total") or 0) for r in rows), default=1.0) or 1.0
        luck_scale = max(float(self._luck_max), 1.0)

        pad_l, pad_r, pad_t = 6, 6, 4
        row_h = max(16, (h - pad_t - 4) / max(len(rows), 1))
        label_w = min(96, w * 0.26)
        # Reserved column so "1120 (100%)" never clips
        value_w = 78
        bar_x0 = pad_l + label_w + 6
        bar_x1 = w - pad_r - value_w
        full_w = max(bar_x1 - bar_x0, 4)
        bar_half = min(6, max(4, row_h * 0.30))
        body_font = _chart_font(9, fonts=self._fonts)
        seg_font = _chart_font(7, bold=True, fonts=self._fonts)

        for i, row in enumerate(rows):
            name = str(row.get("name") or "")
            total = float(row.get("total") or 0)
            segments = [float(s) for s in (row.get("segments") or []) if s]
            if not segments and total:
                segments = [total]

            y = pad_t + i * row_h
            cy = y + row_h / 2
            short = name if len(name) <= 14 else name[:12] + "\u2026"
            _draw_text(
                painter,
                pad_l + label_w,
                cy,
                short,
                anchor="e",
                color=THEME["text_muted"],
                font=body_font,
            )

            # Track = relative scale (dataset max fills the track)
            painter.fillRect(
                QRectF(bar_x0, cy - bar_half, full_w, bar_half * 2),
                QColor(THEME["bg_raised"]),
            )

            luck_ratio = total / luck_scale
            base = luck_color(luck_ratio)
            x = bar_x0
            seg_total = sum(segments) or 1.0
            campaign_w = full_w * min(1.0, total / bar_scale)
            for si, seg in enumerate(segments):
                sw = campaign_w * (seg / seg_total)
                if sw < 0.5:
                    continue
                shade_f = 1.08 if si % 2 == 0 else 0.82
                color = _shade(base, shade_f)
                seg_rect = QRectF(x, cy - bar_half, sw, bar_half * 2)
                painter.fillRect(seg_rect, QColor(color))
                painter.setPen(QPen(QColor(THEME["bg_canvas"]), 1))
                painter.drawRect(seg_rect)
                painter.setPen(Qt.PenStyle.NoPen)
                if sw >= 26:
                    _draw_text(
                        painter,
                        x + sw / 2,
                        cy,
                        f"V{si}",
                        anchor="center",
                        color="#1c1d1a",
                        font=seg_font,
                    )
                x += sw

            pct_luck = 100.0 * min(1.0, luck_ratio)
            _draw_text(
                painter,
                w - pad_r,
                cy,
                f"{int(total)} ({pct_luck:.0f}%)",
                anchor="e",
                color=base,
                font=_chart_font(9, bold=True, fonts=self._fonts),
            )


class _HeatmapCanvas(QWidget):
    """Drawing surface for ActivityHeatmap with hover tooltips."""

    def __init__(self, heatmap: "ActivityHeatmap", height: int):
        super().__init__(heatmap)
        self._heatmap = heatmap
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._tip: Optional[Tuple[str, float, float, str]] = None
        self._last_size = (0, 0)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self.update)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        if abs(w - self._last_size[0]) < 2 and abs(h - self._last_size[1]) < 2:
            return
        self._last_size = (w, h)
        self._resize_timer.start()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(THEME["bg_surface"]))
        w = max(self.width(), 200)
        h = max(self.height(), 80)
        self._heatmap._paint_grid(painter, w, h, self._tip)
        painter.end()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = event.position().x()
        y = event.position().y()
        hit = None
        for x0, y0, x1, y1, day, count in self._heatmap._hit_cells:
            if x0 <= x <= x1 and y0 <= y <= y1:
                hit = (day, count, x0, y0, x1, y1)
                break

        if hit is None:
            if self._tip is not None:
                self._tip = None
                self.update()
            return

        day, count, x0, y0, x1, y1 = hit
        label = f"{day}: {count} pull{'s' if count != 1 else ''}"
        tx = (x0 + x1) / 2
        ty = y0 - 6
        anchor = "s"
        if ty < 14:
            ty = y1 + 6
            anchor = "n"
        cw = max(self.width(), 1)
        tx = max(40, min(cw - 40, tx))
        new_tip = (label, tx, ty, anchor)
        if new_tip != self._tip:
            self._tip = new_tip
            self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802
        if self._tip is not None:
            self._tip = None
            self.update()


class ActivityHeatmap(QFrame):
    """GitHub-style calendar heatmap - section block with centered header."""

    def __init__(self, parent, fonts=None, height: int = 178):
        super().__init__(parent)
        self.setObjectName("ChartSurface")
        self.setStyleSheet(_SURFACE_STYLE)

        self.fonts = fonts
        self._counts: Dict[str, int] = {}
        # (x0, y0, x1, y1, iso_date, count)
        self._hit_cells: List[Tuple[float, float, float, float, str, int]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(2)

        title = QLabel("Pull activity")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(fonts.subheading if fonts else _chart_font(12, bold=True))
        title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        layout.addWidget(title)

        self._meta = QLabel("")
        self._meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._meta.setFont(fonts.body if fonts else _chart_font(11))
        self._meta.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        layout.addWidget(self._meta)

        self._canvas = _HeatmapCanvas(self, height)
        layout.addWidget(self._canvas, 1)

    def set_data(self, activity_by_day: Optional[Dict[str, int]]) -> None:
        self._counts = dict(activity_by_day or {})
        total = sum(self._counts.values())
        days = len(self._counts)
        peak = max(self._counts.values()) if self._counts else 0
        self._meta.setText(
            f"{total} pulls across {days} days  \u00b7  peak {peak}/day"
            if days
            else "No dated pulls"
        )
        self._canvas._tip = None
        self._canvas.update()

    def _paint_grid(
        self,
        painter: QPainter,
        w: int,
        h: int,
        tip: Optional[Tuple[str, float, float, str]],
    ) -> None:
        self._hit_cells.clear()

        if not self._counts:
            _draw_text(
                painter,
                w / 2,
                h / 2,
                "-",
                anchor="center",
                color=THEME["text_muted"],
                font=_chart_font(12, fonts=self.fonts),
            )
            return

        days_sorted = sorted(self._counts)
        try:
            start = datetime.strptime(days_sorted[0], "%Y-%m-%d").date()
            end = datetime.strptime(days_sorted[-1], "%Y-%m-%d").date()
        except ValueError:
            return

        start = start - timedelta(days=start.weekday())
        end = end + timedelta(days=(6 - end.weekday()))
        peak = max(self._counts.values()) or 1
        weeks = max(1, ((end - start).days // 7) + 1)

        pad_l = 34
        pad_r = 4
        week_band = 14  # reserved strip so week numbers are never clipped
        pad_t = week_band + 2
        pad_b = 4
        gap = 2
        avail_w = max(40, w - pad_l - pad_r)
        avail_h = max(40, h - pad_t - pad_b)

        cell_w = max(4, (avail_w - gap * (weeks - 1)) // weeks)
        cell_h = max(4, (avail_h - gap * 6) // 7)

        grid_w = weeks * cell_w + (weeks - 1) * gap
        grid_h = 7 * cell_h + 6 * gap
        ox = pad_l + max(0, (avail_w - grid_w) // 2)
        # Keep grid below the week-number band (don't vertically center into it)
        oy = pad_t + max(0, (avail_h - grid_h) // 2)

        label_font = _chart_font(7, fonts=self.fonts)
        weekday_labels = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        for i, lab in enumerate(weekday_labels):
            _draw_text(
                painter,
                ox - 4,
                oy + i * (cell_h + gap) + cell_h / 2,
                lab,
                anchor="e",
                color=THEME["text_muted"],
                font=label_font,
            )

        # Week numbers in the reserved top band (ISO week)
        for week in range(weeks):
            monday = start + timedelta(days=week * 7)
            iso_week = monday.isocalendar()[1]
            cx = ox + week * (cell_w + gap) + cell_w / 2
            if cell_w < 12 and week % 2:
                continue
            _draw_text(
                painter,
                cx,
                week_band / 2,
                str(iso_week),
                anchor="center",
                color=THEME["text_muted"],
                font=label_font,
            )

        d = start
        while d <= end:
            week = (d - start).days // 7
            wd = d.weekday()
            key = d.isoformat()
            count = self._counts.get(key, 0)
            x0 = ox + week * (cell_w + gap)
            y0 = oy + wd * (cell_h + gap)
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            color = _heat_color(count, peak)
            cell_rect = QRectF(x0, y0, cell_w, cell_h)
            painter.fillRect(cell_rect, QColor(color))
            painter.setPen(QPen(QColor(THEME["bg_canvas"]), 1))
            painter.drawRect(cell_rect)
            painter.setPen(Qt.PenStyle.NoPen)
            self._hit_cells.append((x0, y0, x1, y1, key, count))
            d += timedelta(days=1)

        if tip is not None:
            label, tx, ty, anchor = tip
            tip_font = _chart_font(8, bold=True, fonts=self.fonts)
            painter.setFont(tip_font)
            metrics = QFontMetrics(tip_font)
            tw = metrics.horizontalAdvance(label)
            th = metrics.height()
            pad = 3
            if anchor == "s":
                text_x = tx - tw / 2
                text_y = ty - th
            else:
                text_x = tx - tw / 2
                text_y = ty
            bg_rect = QRectF(
                text_x - pad,
                text_y - pad,
                tw + pad * 2,
                th + pad * 2,
            )
            painter.fillRect(bg_rect, QColor(THEME["bg_raised"]))
            painter.setPen(QPen(QColor(THEME["border"]), 1))
            painter.drawRect(bg_rect)
            _draw_text(
                painter,
                tx,
                text_y + th / 2,
                label,
                anchor="center",
                color=THEME["text_strong"],
                font=tip_font,
            )
