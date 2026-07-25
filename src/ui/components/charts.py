"""Lightweight Canvas charts (no matplotlib dependency)."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import customtkinter as ctk

from src.constants import THEME

# GFL2 type + class colors (DESIGN.md) — distinct on dark canvas
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

# Support (lucky) → Electric → Omni (worst-case V6)
_LUCK_GREEN = (75, 126, 91)       # class_support
_LUCK_YELLOW = (255, 215, 0)      # element_electric
_LUCK_RED = (224, 49, 49)         # element_omni


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
            corner_radius=0,
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
            anchor="center",
            height=22,
        ).pack(fill=tk.X, padx=8, pady=(8, 2))

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
    # Neutral intensity ramp — easy day-to-day contrast on dark UI
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


class ActivityHeatmap(ctk.CTkFrame):
    """GitHub-style calendar heatmap — section block with centered header."""

    def __init__(self, parent, fonts=None, height: int = 178):
        super().__init__(
            parent,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        self.fonts = fonts
        self._redraw_after = None
        title_font = fonts.subheading if fonts else ("Segoe UI", 12, "bold")
        title = ctk.CTkLabel(
            self,
            text="Pull activity",
            font=title_font,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        )
        title.pack(fill=tk.X, padx=12, pady=(10, 2))
        self._meta = ctk.CTkLabel(
            self,
            text="",
            font=fonts.body if fonts else ("Segoe UI", 11),
            text_color=THEME["text_muted"],
            fg_color="transparent",
            anchor="center",
        )
        self._meta.pack(fill=tk.X, padx=12, pady=(0, 2))
        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=THEME["bg_surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self._counts: Dict[str, int] = {}
        self._last_size = (0, 0)
        # (x0, y0, x1, y1, iso_date, count)
        self._hit_cells: List[Tuple[float, float, float, float, str, int]] = []
        self._tip_id = None
        self._tip_bg_id = None

    def _on_configure(self, _event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if abs(w - self._last_size[0]) < 2 and abs(h - self._last_size[1]) < 2:
            return
        if self._redraw_after is not None:
            try:
                self.after_cancel(self._redraw_after)
            except Exception:
                pass
        self._redraw_after = self.after(40, self._redraw)

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

    def _clear_tip(self):
        c = self.canvas
        if self._tip_id is not None:
            c.delete(self._tip_id)
            self._tip_id = None
        if self._tip_bg_id is not None:
            c.delete(self._tip_bg_id)
            self._tip_bg_id = None

    def _on_leave(self, _event=None):
        self._clear_tip()

    def _on_motion(self, event):
        x, y = event.x, event.y
        hit = None
        for x0, y0, x1, y1, day, count in self._hit_cells:
            if x0 <= x <= x1 and y0 <= y <= y1:
                hit = (day, count, x0, y0, x1, y1)
                break
        self._clear_tip()
        if hit is None:
            return
        day, count, x0, y0, x1, y1 = hit
        label = f"{day}: {count} pull{'s' if count != 1 else ''}"
        c = self.canvas
        # Prefer above the cell; flip below if near top
        tx = (x0 + x1) / 2
        ty = y0 - 6
        anchor = "s"
        if ty < 14:
            ty = y1 + 6
            anchor = "n"
        # Clamp horizontally inside canvas
        cw = max(c.winfo_width(), 1)
        tx = max(40, min(cw - 40, tx))
        self._tip_id = c.create_text(
            tx,
            ty,
            text=label,
            fill=THEME["text_strong"],
            font=("Segoe UI", 8, "bold"),
            anchor=anchor,
            tags=("tip",),
        )
        bbox = c.bbox(self._tip_id)
        if bbox:
            pad = 3
            self._tip_bg_id = c.create_rectangle(
                bbox[0] - pad,
                bbox[1] - pad,
                bbox[2] + pad,
                bbox[3] + pad,
                fill=THEME["bg_raised"],
                outline=THEME["border"],
                width=1,
                tags=("tip",),
            )
            c.tag_lower(self._tip_bg_id, self._tip_id)

    def _redraw(self) -> None:
        self._redraw_after = None
        c = self.canvas
        c.delete("all")
        self._hit_cells.clear()
        self._tip_id = None
        self._tip_bg_id = None
        w = max(c.winfo_width(), 200)
        h = max(c.winfo_height(), 80)
        self._last_size = (w, h)
        if not self._counts:
            c.create_text(
                w // 2,
                h // 2,
                text="—",
                fill=THEME["text_muted"],
                font=("Segoe UI", 12),
            )
            return

        from datetime import datetime, timedelta

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

        weekday_labels = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        for i, lab in enumerate(weekday_labels):
            c.create_text(
                ox - 4,
                oy + i * (cell_h + gap) + cell_h / 2,
                text=lab,
                anchor="e",
                fill=THEME["text_muted"],
                font=("Segoe UI", 7),
            )

        # Week numbers in the reserved top band (ISO week)
        for week in range(weeks):
            monday = start + timedelta(days=week * 7)
            iso_week = monday.isocalendar()[1]
            cx = ox + week * (cell_w + gap) + cell_w / 2
            if cell_w < 12 and week % 2:
                continue
            c.create_text(
                cx,
                week_band // 2,
                text=str(iso_week),
                fill=THEME["text_muted"],
                font=("Segoe UI", 7),
                anchor="center",
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
            c.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=color,
                outline=THEME["bg_canvas"],
                width=1,
            )
            self._hit_cells.append((x0, y0, x1, y1, key, count))
            d += timedelta(days=1)
