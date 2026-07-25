"""Gacha Collection — doll gallery with editable V-ranks."""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from PIL import Image

from src.constants import THEME
from src.core.gacha_names import doll_portrait_names, portrait_path_for_doll
from src.core.gacha_stats import MAX_COPIES
from src.data.gacha_db import GachaDB
from src.ui.styles import create_button

_PORTRAIT_SIZE = (72, 72)
_CARD_W = 108
_CARD_H = 148
_CARD_PADX = 4
_CARD_PADY = 4
# Allow card width to flex so N columns fit the viewport without clipping
_CARD_FLEX = 0.10
# Stats "complete" accent — V6 done
_V6_BORDER = THEME["class_support"]


class GachaCollectionTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: GachaDB = None, on_change=None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_change = on_change
        self._edit = tk.BooleanVar(value=False)
        self._img_owned: Dict[str, ctk.CTkImage] = {}
        self._img_dim: Dict[str, ctk.CTkImage] = {}
        self._cards: Dict[Tuple[str, str], dict] = {}
        self._doll_order: List[str] = []
        self._built = False
        self._scanned: Dict[Tuple[str, str], int] = {}
        self._overrides: Dict[Tuple[str, str], int] = {}
        self._notify_after = None
        self._cols = 0
        self._card_w = _CARD_W
        self._layout_after = None
        self._portrait_queue: List[str] = []
        self._portrait_job = None
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        toolbar = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        toolbar.pack(fill=tk.X, padx=8, pady=(6, 4))

        row = ctk.CTkFrame(toolbar, fg_color="transparent")
        row.pack(fill=tk.X, padx=8, pady=6)

        ctk.CTkLabel(
            row,
            text="Collection",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            row,
            text="Elite doll copies from scans (max V6). Edit to correct ranks outside Access Records.",
            font=self.fonts.body,
            text_color=THEME["text_muted"],
            fg_color="transparent",
        ).pack(side=tk.LEFT, padx=(12, 0))

        create_button(
            row,
            text="Refresh",
            variant="secondary",
            font=self.fonts.ui,
            command=self.refresh,
            width=90,
            height=28,
        ).pack(side=tk.RIGHT, padx=(8, 0))

        ctk.CTkSwitch(
            row,
            text="Edit ranks",
            variable=self._edit,
            font=self.fonts.ui,
            command=self._on_edit_toggle,
            progress_color=THEME["cta_dark"],
        ).pack(side=tk.RIGHT, padx=(8, 0))

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=THEME["bg_canvas"],
            corner_radius=0,
        )
        self.scroll.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        self.section = ctk.CTkFrame(
            self.scroll,
            fg_color=THEME["bg_surface"],
            corner_radius=0,
            border_width=1,
            border_color=THEME["border"],
        )
        self.section.pack(fill=tk.X, padx=2, pady=2)

        ctk.CTkLabel(
            self.section,
            text="Dolls",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="center",
        ).pack(fill=tk.X, padx=12, pady=(10, 4))

        self.dolls_grid = ctk.CTkFrame(self.section, fg_color="transparent")
        self.dolls_grid.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Viewport resize — must use add="+" so we don't replace CTk's scrollregion bind
        self.scroll.bind("<Configure>", self._on_grid_configure, add="+")
        self.bind("<Configure>", self._on_grid_configure, add="+")

    def _viewport_width_logical(self) -> float:
        """Visible scroll canvas width in CTk logical (unscaled) units."""
        scale = max(float(self._get_widget_scaling()), 0.01)
        canvas = getattr(self.scroll, "_parent_canvas", None)
        px = 0
        if canvas is not None:
            try:
                px = int(canvas.winfo_width())
            except tk.TclError:
                px = 0
        if px < 40:
            try:
                px = int(self.scroll.winfo_width())
            except tk.TclError:
                px = 0
        if px < 40:
            try:
                px = max(0, int(self.winfo_width()) - 16)
            except tk.TclError:
                px = 0
        # Inner paddings: section 2+2, grid 8+8, border ~2; leave room for scrollbar
        usable_px = max(0, px - 28)
        return usable_px / scale

    def _fit_columns(self, usable: float) -> Tuple[int, int]:
        """Pick column count + card width; card may flex ±10% to avoid clipping."""
        pad = 2 * _CARD_PADX
        min_w = _CARD_W * (1.0 - _CARD_FLEX)
        max_w = _CARD_W * (1.0 + _CARD_FLEX)
        if usable < min_w + pad:
            return 1, int(round(min_w))

        # Max columns that fit if cards shrink to the floor
        cols = max(1, int(usable // (min_w + pad)))
        # Ideal width to fill the row evenly
        card_w = usable / cols - pad
        card_w = max(min_w, min(max_w, card_w))

        # If even min width overflows (float noise / scrollbar), drop a column
        while cols > 1 and cols * (min_w + pad) > usable + 0.5:
            cols -= 1
            card_w = usable / cols - pad
            card_w = max(min_w, min(max_w, card_w))

        # Final safety: if still too wide at this card_w, force shrink to fit
        if cols * (card_w + pad) > usable + 0.5:
            card_w = max(min_w, usable / cols - pad)

        return cols, max(1, int(round(card_w)))

    def _on_grid_configure(self, _event=None):
        if self._layout_after is not None:
            try:
                self.after_cancel(self._layout_after)
            except Exception:
                pass
        # Slightly longer debounce — resize floods Configure events
        self._layout_after = self.after(60, self._relayout_grid)

    def _refresh_scrollregion(self):
        """Keep CTkScrollableFrame's canvas in sync after grid height changes."""
        canvas = getattr(self.scroll, "_parent_canvas", None)
        if canvas is None:
            return
        try:
            self.scroll.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        except tk.TclError:
            pass

    def _relayout_grid(self):
        self._layout_after = None
        if not self._built or not self._doll_order:
            return
        usable = self._viewport_width_logical()
        if usable < 40:
            return
        cols, card_w = self._fit_columns(usable)
        if cols == self._cols and card_w == self._card_w:
            self._refresh_scrollregion()
            return
        self._cols = cols
        self._card_w = card_w
        wrap = max(48, card_w - 12)
        for i, name in enumerate(self._doll_order):
            meta = self._cards.get((name, "Doll"))
            if not meta:
                continue
            meta["card"].configure(width=card_w)
            meta["name_lbl"].configure(wraplength=wrap)
            meta["card"].grid(
                row=i // cols,
                column=i % cols,
                padx=_CARD_PADX,
                pady=_CARD_PADY,
                sticky="n",
            )
        self._refresh_scrollregion()
        # Second pass after geometry settles (more rows → taller content)
        self.after_idle(self._refresh_scrollregion)

    def _portrait_images(
        self, name: str
    ) -> Tuple[Optional[ctk.CTkImage], Optional[ctk.CTkImage]]:
        if name in self._img_owned:
            return self._img_owned[name], self._img_dim.get(name)
        path = portrait_path_for_doll(name)
        if not path or not path.is_file():
            return None, None
        try:
            base = Image.open(path).convert("RGBA")
            base = base.resize(_PORTRAIT_SIZE, Image.Resampling.LANCZOS)
            owned = ctk.CTkImage(
                light_image=base, dark_image=base, size=_PORTRAIT_SIZE
            )
            dim_img = base.copy()
            alpha = dim_img.split()[-1].point(lambda a: int(a * 0.45))
            dim_img.putalpha(alpha)
            dim = ctk.CTkImage(
                light_image=dim_img, dark_image=dim_img, size=_PORTRAIT_SIZE
            )
            self._img_owned[name] = owned
            self._img_dim[name] = dim
            return owned, dim
        except OSError:
            return None, None

    def _queue_portraits(self, names: List[str]):
        """Load portrait images in small idle chunks so first paint stays snappy."""
        self._portrait_queue = [n for n in names if n not in self._img_owned]
        if self._portrait_job is not None:
            try:
                self.after_cancel(self._portrait_job)
            except Exception:
                pass
            self._portrait_job = None
        if self._portrait_queue:
            self._portrait_job = self.after(1, self._drain_portraits)

    def _drain_portraits(self):
        self._portrait_job = None
        batch = self._portrait_queue[:6]
        self._portrait_queue = self._portrait_queue[6:]
        for name in batch:
            self._portrait_images(name)
            meta = self._cards.get((name, "Doll"))
            if meta and meta.get("img_lbl") is not None:
                copies, _, _ = self._effective_copies(name, "Doll")
                owned_img = self._img_owned.get(name)
                dim_img = self._img_dim.get(name)
                img = owned_img if copies > 0 else dim_img
                if img is not None:
                    meta["img_lbl"].configure(image=img)
        if self._portrait_queue:
            self._portrait_job = self.after(8, self._drain_portraits)

    def _effective_copies(self, name: str, item_type: str) -> Tuple[int, bool, int]:
        key = (name, item_type)
        scanned = int(self._scanned.get(key, 0))
        if key in self._overrides:
            return int(self._overrides[key]), True, scanned
        return min(scanned, MAX_COPIES), False, scanned

    def _border_for(self, copies: int) -> str:
        # V6 = 7 copies (V0..V6); match Stats "complete" support green
        if copies >= MAX_COPIES:
            return _V6_BORDER
        return THEME["border"]

    def _schedule_notify(self):
        if not self.on_change:
            return
        if self._notify_after is not None:
            try:
                self.after_cancel(self._notify_after)
            except Exception:
                pass
        self._notify_after = self.after(400, self._fire_notify)

    def _fire_notify(self):
        self._notify_after = None
        if self.on_change:
            self.on_change()

    def _bump(self, name: str, item_type: str, delta: int):
        key = (name, item_type)
        copies, _ov, scanned = self._effective_copies(name, item_type)
        new = max(0, min(MAX_COPIES, copies + delta))
        natural = min(scanned, MAX_COPIES)
        if new == natural:
            self.db.clear_collection_override(name, item_type)
            self._overrides.pop(key, None)
        else:
            self.db.set_collection_override(name, item_type, new)
            self._overrides[key] = new
        self._paint_card(name, item_type)
        self._schedule_notify()

    def _on_edit_toggle(self):
        edit = self._edit.get()
        for meta in self._cards.values():
            row = meta["rank_row"]
            for w in row.winfo_children():
                w.pack_forget()
            if edit:
                meta["btn_minus"].pack(side=tk.LEFT, padx=2)
            meta["rank_lbl"].pack(side=tk.LEFT)
            if edit:
                meta["btn_plus"].pack(side=tk.LEFT, padx=2)

    def _paint_card(self, name: str, item_type: str):
        key = (name, item_type)
        meta = self._cards.get(key)
        if not meta:
            return
        copies, overridden, _ = self._effective_copies(name, item_type)
        owned = copies > 0
        rank = f"V{copies - 1}" if copies > 0 else "—"
        meta["rank_lbl"].configure(
            text=rank,
            text_color=THEME["accent_amber"] if overridden else THEME["text_primary"],
        )
        meta["name_lbl"].configure(
            text_color=THEME["text_strong"] if owned else THEME["text_muted"],
        )
        meta["card"].configure(
            fg_color=THEME["bg_canvas"] if owned else THEME["bg_raised"],
            border_color=self._border_for(copies),
        )
        img_lbl = meta.get("img_lbl")
        if img_lbl is not None and name in self._img_owned:
            owned_img, dim_img = self._img_owned[name], self._img_dim.get(name)
            img = owned_img if owned else dim_img
            if img is not None:
                img_lbl.configure(image=img)

    def _make_card(self, name: str, *, grid_row: int, grid_col: int) -> dict:
        item_type = "Doll"
        copies, overridden, _ = self._effective_copies(name, item_type)
        owned = copies > 0
        edit = self._edit.get()

        card = ctk.CTkFrame(
            self.dolls_grid,
            fg_color=THEME["bg_canvas"] if owned else THEME["bg_raised"],
            corner_radius=0,
            border_width=1,
            border_color=self._border_for(copies),
            width=self._card_w,
            height=_CARD_H,
        )
        card.pack_propagate(False)
        card.grid(
            row=grid_row,
            column=grid_col,
            padx=_CARD_PADX,
            pady=_CARD_PADY,
            sticky="n",
        )

        # Placeholder until idle portrait drain fills images
        img_lbl = ctk.CTkLabel(
            card, text="", fg_color="transparent", width=72, height=72
        )
        img_lbl.pack(pady=(8, 2))
        if name in self._img_owned:
            owned_img, dim_img = self._img_owned[name], self._img_dim.get(name)
            img = owned_img if owned else dim_img
            if img is not None:
                img_lbl.configure(image=img)

        name_lbl = ctk.CTkLabel(
            card,
            text=name,
            font=self.fonts.body,
            text_color=THEME["text_strong"] if owned else THEME["text_muted"],
            fg_color="transparent",
            wraplength=max(48, self._card_w - 12),
        )
        name_lbl.pack(padx=4)

        rank_row = ctk.CTkFrame(card, fg_color="transparent")
        rank_row.pack(pady=(2, 6))

        btn_minus = ctk.CTkButton(
            rank_row,
            text="−",
            width=24,
            height=24,
            font=self.fonts.ui,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_strong"],
            command=lambda n=name, t=item_type: self._bump(n, t, -1),
        )
        rank_lbl = ctk.CTkLabel(
            rank_row,
            text=f"V{copies - 1}" if copies > 0 else "—",
            font=self.fonts.body_medium,
            text_color=THEME["accent_amber"] if overridden else THEME["text_primary"],
            fg_color="transparent",
            width=36,
        )
        btn_plus = ctk.CTkButton(
            rank_row,
            text="+",
            width=24,
            height=24,
            font=self.fonts.ui,
            fg_color=THEME["bg_raised"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_strong"],
            command=lambda n=name, t=item_type: self._bump(n, t, 1),
        )
        if edit:
            btn_minus.pack(side=tk.LEFT, padx=2)
        rank_lbl.pack(side=tk.LEFT)
        if edit:
            btn_plus.pack(side=tk.LEFT, padx=2)

        meta = {
            "key": (name, item_type),
            "card": card,
            "img_lbl": img_lbl,
            "name_lbl": name_lbl,
            "rank_row": rank_row,
            "rank_lbl": rank_lbl,
            "btn_minus": btn_minus,
            "btn_plus": btn_plus,
        }
        self._cards[(name, item_type)] = meta
        return meta

    def _load_counts(self):
        self._overrides = {
            k: v
            for k, v in self.db.get_collection_overrides().items()
            if k[1] == "Doll"
        }
        # Fast SQL aggregate — avoids annotate_pulls over the full timeline
        self._scanned = self.db.count_elite_copies(item_type="Doll")

    def refresh(self):
        """Rebuild gallery once; later updates paint in place."""
        self._load_counts()

        if self._built:
            for key in list(self._cards):
                self._paint_card(*key)
            self._on_edit_toggle()
            self._on_grid_configure()
            return

        for child in self.dolls_grid.winfo_children():
            child.destroy()
        self._cards.clear()
        self._doll_order = list(doll_portrait_names())
        self._cols = 0

        # Initial guess; Configure will correct to viewport width
        usable = self._viewport_width_logical()
        if usable < 40:
            usable = 720
        guess, card_w = self._fit_columns(usable)
        self._card_w = card_w
        for i, name in enumerate(self._doll_order):
            self._make_card(name, grid_row=i // guess, grid_col=i % guess)

        self._built = True
        self._cols = guess
        self._queue_portraits(self._doll_order)
        self.after_idle(self._relayout_grid)
