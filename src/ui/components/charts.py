"""Lightweight Canvas charts (no matplotlib dependency)."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import customtkinter as ctk

from src.constants import THEME

# Distinct series colors on dark canvas (pie / simple bars)
_PALETTE = (
    "#F54E00",
    "#F7A501",
    "#6ee7b7",
    "#60a5fa",
    "#c084fc",
    "#f472b6",
    "#a3e635",
    "#38bdf8",
    "#fb923c",
    "#e879f9",
)

# Green (lucky) → red (worst-case V6 = 1120 pulls)
_LUCK_GREEN = (34, 197, 94)
_LUCK_YELLOW = (247, 165, 1)
_LUCK_RED = (239, 68, 68)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def luck_color(ratio: float) -> str:
    """Map 0..1 (pulls / worst V6) to green → yellow → red."""
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


class ChartFrame(ctk.CTkFrame):
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
        super().__init__(
            parent,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        self.kind = kind
        self._fonts = fonts
        self._data: Any = {}
        # Color scale only (worst-case V6); bar width uses dataset max
        self._luck_max: float = 1120.0

        title_font = fonts.subheading if fonts else ("Segoe UI", 16, "bold")
        # Keep title band short — CTkLabel default height adds a lot of top air
        ctk.CTkLabel(
            self,
            text=title,
            font=title_font,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
            height=20,
        ).pack(fill=tk.X, padx=6, pady=(2, 0))

        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=THEME["bg_canvas"],
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=(1, 3))
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

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
        self._redraw()

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 40)
        h = max(c.winfo_height(), 40)

        if self.kind == "campaign":
            rows = list(self._data or [])
            if not rows:
                self._empty(w, h)
                return
            self._draw_campaign_bars(rows, w, h)
            return

        items = sorted(self._data.items(), key=lambda kv: -kv[1])
        if not items:
            self._empty(w, h)
            return
        if self.kind == "pie":
            self._draw_pie(items, w, h)
        else:
            self._draw_bar(items, w, h)

    def _empty(self, w: int, h: int) -> None:
        self.canvas.create_text(
            w // 2,
            h // 2,
            text="No data",
            fill=THEME["text_muted"],
            font=("Segoe UI", 11),
        )

    def _draw_pie(self, items: Sequence[Tuple[str, float]], w: int, h: int) -> None:
        c = self.canvas
        total = sum(v for _, v in items) or 1.0
        size = min(w * 0.42, h - 20)
        cx, cy = w * 0.28, h / 2
        x0, y0 = cx - size / 2, cy - size / 2
        x1, y1 = cx + size / 2, cy + size / 2
        start = 90.0
        legend_x = w * 0.55
        legend_y = 12
        for i, (label, value) in enumerate(items):
            extent = -360.0 * (value / total)
            color = _PALETTE[i % len(_PALETTE)]
            if abs(extent) < 0.5:
                continue
            c.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=start,
                extent=extent,
                fill=color,
                outline=THEME["bg_canvas"],
                width=2,
            )
            start += extent
            pct = 100.0 * value / total
            c.create_rectangle(
                legend_x,
                legend_y,
                legend_x + 10,
                legend_y + 10,
                fill=color,
                outline="",
            )
            c.create_text(
                legend_x + 16,
                legend_y + 5,
                text=f"{label}  {int(value)} ({pct:.0f}%)",
                anchor="w",
                fill=THEME["text_primary"],
                font=("Segoe UI", 9),
            )
            legend_y += 18

    def _draw_bar(self, items: Sequence[Tuple[str, float]], w: int, h: int) -> None:
        c = self.canvas
        items = list(items)[:12]
        max_v = max(v for _, v in items) or 1.0
        pad_l, pad_r, pad_t = 6, 8, 4
        row_h = max(16, (h - pad_t - 4) / max(len(items), 1))
        label_w = min(110, w * 0.32)
        value_w = 40
        bar_x0 = pad_l + label_w + 6
        bar_x1 = w - pad_r - value_w

        for i, (label, value) in enumerate(items):
            y = pad_t + i * row_h
            cy = y + row_h / 2
            short = label if len(label) <= 16 else label[:14] + "…"
            c.create_text(
                pad_l + label_w,
                cy,
                text=short,
                anchor="e",
                fill=THEME["text_muted"],
                font=("Segoe UI", 9),
            )
            bw = max(bar_x1 - bar_x0, 4) * (value / max_v)
            color = _PALETTE[i % len(_PALETTE)]
            c.create_rectangle(
                bar_x0,
                cy - 5,
                bar_x0 + max(bw, 2),
                cy + 5,
                fill=color,
                outline="",
            )
            c.create_text(
                w - pad_r,
                cy,
                text=str(int(value)),
                anchor="e",
                fill=THEME["text_strong"],
                font=("Segoe UI", 9),
            )

    def _draw_campaign_bars(self, rows: List[Dict[str, Any]], w: int, h: int) -> None:
        """Stacked per-copy segments; bar width vs dataset max; color vs luck max."""
        c = self.canvas
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

        for i, row in enumerate(rows):
            name = str(row.get("name") or "")
            total = float(row.get("total") or 0)
            segments = [float(s) for s in (row.get("segments") or []) if s]
            if not segments and total:
                segments = [total]

            y = pad_t + i * row_h
            cy = y + row_h / 2
            short = name if len(name) <= 14 else name[:12] + "…"
            c.create_text(
                pad_l + label_w,
                cy,
                text=short,
                anchor="e",
                fill=THEME["text_muted"],
                font=("Segoe UI", 9),
            )

            # Track = relative scale (dataset max fills the track)
            c.create_rectangle(
                bar_x0,
                cy - bar_half,
                bar_x0 + full_w,
                cy + bar_half,
                fill=THEME["bg_raised"],
                outline="",
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
                c.create_rectangle(
                    x,
                    cy - bar_half,
                    x + sw,
                    cy + bar_half,
                    fill=color,
                    outline=THEME["bg_canvas"],
                    width=1,
                )
                if sw >= 26:
                    c.create_text(
                        x + sw / 2,
                        cy,
                        text=f"V{si}",
                        fill="#1c1d1a",
                        font=("Segoe UI", 7, "bold"),
                    )
                x += sw

            pct_luck = 100.0 * min(1.0, luck_ratio)
            c.create_text(
                w - pad_r,
                cy,
                text=f"{int(total)} ({pct_luck:.0f}%)",
                anchor="e",
                fill=base,
                font=("Segoe UI", 9, "bold"),
            )


def _heat_color(count: int, peak: int) -> str:
    if count <= 0 or peak <= 0:
        return THEME["bg_raised"]
    t = min(1.0, count / peak)
    # muted → amber → CTA orange
    cold = (55, 58, 52)
    mid = (247, 165, 1)
    hot = (245, 78, 0)
    if t < 0.5:
        u = t / 0.5
        rgb = tuple(_lerp(cold[i], mid[i], u) for i in range(3))
    else:
        u = (t - 0.5) / 0.5
        rgb = tuple(_lerp(mid[i], hot[i], u) for i in range(3))
    return _rgb_to_hex(rgb)


class ActivityHeatmap(ctk.CTkFrame):
    """GitHub-style calendar heatmap of pulls per day."""

    def __init__(self, parent, fonts=None, height: int = 140):
        super().__init__(
            parent,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["border"],
        )
        self.fonts = fonts
        title = ctk.CTkLabel(
            self,
            text="Pull activity",
            font=fonts.ui if fonts else ("Segoe UI", 12),
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
        )
        title.pack(fill=tk.X, padx=10, pady=(8, 0))
        self._meta = ctk.CTkLabel(
            self,
            text="",
            font=fonts.body if fonts else ("Segoe UI", 11),
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="w",
        )
        self._meta.pack(fill=tk.X, padx=10, pady=(0, 2))
        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=THEME["bg_surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self._counts: Dict[str, int] = {}

    def set_data(self, activity_by_day: Optional[Dict[str, int]]) -> None:
        self._counts = dict(activity_by_day or {})
        total = sum(self._counts.values())
        days = len(self._counts)
        peak = max(self._counts.values()) if self._counts else 0
        self._meta.configure(
            text=f"{total} pulls across {days} days  ·  peak {peak}/day"
            if days
            else "No dated pulls"
        )
        self._redraw()

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 200)
        h = max(c.winfo_height(), 80)
        if not self._counts:
            c.create_text(
                w // 2,
                h // 2,
                text="—",
                fill=THEME["text_muted"],
                font=("Segoe UI", 12),
            )
            return

        from datetime import date, datetime, timedelta

        days_sorted = sorted(self._counts)
        try:
            start = datetime.strptime(days_sorted[0], "%Y-%m-%d").date()
            end = datetime.strptime(days_sorted[-1], "%Y-%m-%d").date()
        except ValueError:
            return

        # Align start to Monday
        start = start - timedelta(days=start.weekday())
        end = end + timedelta(days=(6 - end.weekday()))
        peak = max(self._counts.values()) or 1

        cell = 11
        gap = 2
        pad_l = 28
        pad_t = 4
        weeks = ((end - start).days // 7) + 1
        # Shrink if too wide
        avail = w - pad_l - 8
        need = weeks * (cell + gap)
        if need > avail and weeks > 0:
            cell = max(6, int((avail / weeks) - gap))

        weekday_labels = ("Mon", "", "Wed", "", "Fri", "", "")
        for i, lab in enumerate(weekday_labels):
            if lab:
                c.create_text(
                    4,
                    pad_t + i * (cell + gap) + cell / 2,
                    text=lab,
                    anchor="w",
                    fill=THEME["text_muted"],
                    font=("Segoe UI", 7),
                )

        d = start
        while d <= end:
            week = (d - start).days // 7
            wd = d.weekday()
            key = d.isoformat()
            count = self._counts.get(key, 0)
            x0 = pad_l + week * (cell + gap)
            y0 = pad_t + wd * (cell + gap)
            color = _heat_color(count, peak)
            c.create_rectangle(
                x0,
                y0,
                x0 + cell,
                y0 + cell,
                fill=color,
                outline=THEME["bg_canvas"],
                width=1,
            )
            d += timedelta(days=1)
