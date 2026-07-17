"""Gacha Collection — doll gallery with editable V-ranks."""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from PIL import Image

from src.constants import THEME
from src.core.gacha_names import (
    NAMED_WEAPONS,
    STANDARD_ELITE_WEAPON_NAMES,
    STANDARD_WEAPONS,
    doll_portrait_names,
    portrait_path_for_doll,
)
from src.core.gacha_stats import MAX_COPIES, annotate_pulls
from src.data.gacha_db import GachaDB
from src.ui.styles import create_button

_PORTRAIT_SIZE = (72, 72)


class GachaCollectionTab(ctk.CTkFrame):
    def __init__(self, parent, fonts, db: GachaDB = None, on_change=None):
        super().__init__(parent, fg_color=THEME["bg_canvas"], corner_radius=0)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_change = on_change
        self._edit = tk.BooleanVar(value=False)
        # name -> CTkImage (owned / dimmed)
        self._img_owned: Dict[str, ctk.CTkImage] = {}
        self._img_dim: Dict[str, ctk.CTkImage] = {}
        # (name, type) -> card widgets
        self._cards: Dict[Tuple[str, str], dict] = {}
        self._built = False
        self._scanned: Dict[Tuple[str, str], int] = {}
        self._overrides: Dict[Tuple[str, str], int] = {}
        self._notify_after = None
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        toolbar = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_surface"],
            corner_radius=6,
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
            text="Elite copies from scans (max V6). Edit to correct ranks outside Access Records.",
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

        ctk.CTkLabel(
            self.scroll,
            text="Dolls",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill=tk.X, padx=4, pady=(4, 2))

        self.dolls_grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.dolls_grid.pack(fill=tk.X, padx=2, pady=2)

        ctk.CTkLabel(
            self.scroll,
            text="Weapons",
            font=self.fonts.subheading,
            text_color=THEME["text_strong"],
            fg_color="transparent",
            anchor="w",
        ).pack(fill=tk.X, padx=4, pady=(12, 2))

        self.weapons_grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.weapons_grid.pack(fill=tk.X, padx=2, pady=2)

    def _portrait_images(self, name: str) -> Tuple[Optional[ctk.CTkImage], Optional[ctk.CTkImage]]:
        if name in self._img_owned:
            return self._img_owned[name], self._img_dim.get(name)
        path = portrait_path_for_doll(name)
        if not path or not path.is_file():
            return None, None
        try:
            base = Image.open(path).convert("RGBA")
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

    def _effective_copies(self, name: str, item_type: str) -> Tuple[int, bool, int]:
        key = (name, item_type)
        scanned = int(self._scanned.get(key, 0))
        if key in self._overrides:
            return int(self._overrides[key]), True, scanned
        return min(scanned, MAX_COPIES), False, scanned

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
        # Toggle +/- visibility without rebuilding the gallery
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

            key = meta["key"]
            copies, _, _ = self._effective_copies(*key)
            if key[1] == "Weapons" and copies <= 0 and key not in self._overrides:
                if edit:
                    meta["card"].grid()
                else:
                    meta["card"].grid_remove()

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
            fg_color=THEME["bg_surface"] if owned else THEME["bg_raised"],
            border_color=THEME["accent_amber"] if overridden else THEME["border"],
        )
        img_lbl = meta.get("img_lbl")
        if img_lbl is not None:
            owned_img, dim_img = self._portrait_images(name)
            img = owned_img if owned else dim_img
            if img is not None:
                img_lbl.configure(image=img)

    def _make_card(
        self,
        parent,
        name: str,
        item_type: str,
        *,
        with_portrait: bool,
        grid_row: int,
        grid_col: int,
    ) -> dict:
        copies, overridden, _ = self._effective_copies(name, item_type)
        owned = copies > 0
        edit = self._edit.get()

        card = ctk.CTkFrame(
            parent,
            fg_color=THEME["bg_surface"] if owned else THEME["bg_raised"],
            corner_radius=6,
            border_width=1,
            border_color=THEME["accent_amber"] if overridden else THEME["border"],
            width=108,
            height=148 if with_portrait else 72,
        )
        card.pack_propagate(False)
        card.grid(row=grid_row, column=grid_col, padx=4, pady=4, sticky="n")

        img_lbl = None
        if with_portrait:
            owned_img, dim_img = self._portrait_images(name)
            img = owned_img if owned else dim_img
            img_lbl = ctk.CTkLabel(card, image=img, text="", fg_color="transparent")
            img_lbl.pack(pady=(8, 2))

        name_lbl = ctk.CTkLabel(
            card,
            text=name,
            font=self.fonts.body,
            text_color=THEME["text_strong"] if owned else THEME["text_muted"],
            fg_color="transparent",
            wraplength=96,
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

        if (
            item_type == "Weapons"
            and copies <= 0
            and (name, item_type) not in self._overrides
            and not edit
        ):
            card.grid_remove()

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
        self._overrides = self.db.get_collection_overrides()
        timeline = annotate_pulls(self.db.list_all_oldest_first())
        self._scanned = {}
        for p in timeline:
            if p.get("rarity") != "elite":
                continue
            name = (p.get("item_name") or "").strip()
            itype = p.get("item_type") or ""
            if not name or itype not in ("Doll", "Weapons"):
                continue
            key = (name, itype)
            self._scanned[key] = self._scanned.get(key, 0) + 1

    def refresh(self):
        """Rebuild gallery once; later updates paint in place."""
        self._load_counts()

        if self._built:
            for key in list(self._cards):
                self._paint_card(*key)
            self._on_edit_toggle()
            return

        for child in self.dolls_grid.winfo_children():
            child.destroy()
        for child in self.weapons_grid.winfo_children():
            child.destroy()
        self._cards.clear()

        cols = 8
        dolls = list(doll_portrait_names())
        for i, name in enumerate(dolls):
            self._make_card(
                self.dolls_grid,
                name,
                "Doll",
                with_portrait=True,
                grid_row=i // cols,
                grid_col=i % cols,
            )

        weapon_names = (
            list(STANDARD_WEAPONS)
            + list(STANDARD_ELITE_WEAPON_NAMES)
            + list(NAMED_WEAPONS)
        )
        seen = set(weapon_names)
        for (name, itype), copies in {**self._scanned, **self._overrides}.items():
            if itype == "Weapons" and name not in seen:
                weapon_names.append(name)
                seen.add(name)

        for i, name in enumerate(weapon_names):
            self._make_card(
                self.weapons_grid,
                name,
                "Weapons",
                with_portrait=False,
                grid_row=i // cols,
                grid_col=i % cols,
            )

        self._built = True
