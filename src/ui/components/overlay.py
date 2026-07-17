"""Region-picker overlay windows drawn on top of the GFL2 game.

Implementation note: we deliberately keep the raw `tk.Toplevel` mechanism
here rather than using `CTkToplevel`. CTk's wrapper does not play well with
`overrideredirect(True)` + `-alpha` + `-topmost`, and the overlays need to
be borderless, semi-transparent, and click-draggable above any other window.
"""

import tkinter as tk

from src.constants import GACHA_EXTRA_REGIONS, GACHA_ROW_COLUMNS, THEME

GUNSMOKE_COLUMNS = ("nickname", "single_high", "total_score")

COLUMN_COLORS = {
    "nickname": THEME["class_bulwark"],
    "single_high": THEME["class_support"],
    "total_score": THEME["class_sentinel"],
    "purchase_time": THEME["class_bulwark"],
    "purchase_source": THEME["class_support"],
    "type": THEME["class_vanguard"],
    "name": THEME["class_sentinel"],
    "page_number": THEME["warning"],
    "btn_prev": THEME["text_muted"],
    "btn_next": THEME["text_muted"],
}

COLUMN_LABEL = {
    "nickname": "Nick",
    "single_high": "Single",
    "total_score": "Total",
    "purchase_time": "Time",
    "purchase_source": "Source",
    "type": "Type",
    "name": "Name",
    "page_number": "Page",
    "btn_prev": "Prev",
    "btn_next": "Next",
}

EDGE_PX = 10
MIN_W = 16
MIN_H = 12
ALPHA_NORMAL = 0.20
ALPHA_SELECTED = 0.40


class OverlayManager:
    def __init__(self, root, config_manager, fonts=None, on_update_callback=None):
        self.root = root
        self.config_manager = config_manager
        self.fonts = fonts
        self.on_update_callback = on_update_callback

        self.profile = "gunsmoke"  # "gunsmoke" | "gacha"
        self.move_lock = "none"  # "none" | "column" | "row"
        self.selected = None  # (row_idx|None, col_name)

        self.overlay_windows = []
        self.active = False
        self.dragging = False
        self.drag_start = None
        self.dragging_overlay = None
        self.resize_edge = None  # None | "e" | "s" | "se"
        self._keys_bound = False

    def set_profile(self, profile: str):
        if profile not in ("gunsmoke", "gacha"):
            return
        was_active = self.active
        self.profile = profile
        if was_active:
            self.show()

    def set_move_lock(self, mode: str):
        if mode in ("none", "column", "row"):
            self.move_lock = mode

    def set_selected(self, row_idx, col_name):
        self.selected = (row_idx, col_name)
        self._update_selection_visual()

    def toggle(self):
        if self.active:
            self.hide()
        else:
            self.show()

    def hide(self):
        for overlay in self.overlay_windows:
            if overlay:
                try:
                    overlay.destroy()
                except Exception:
                    pass
        self.overlay_windows = []
        self.active = False
        self.dragging = False
        self.resize_edge = None

    def _table_columns(self):
        if self.profile == "gacha":
            return GACHA_ROW_COLUMNS
        return GUNSMOKE_COLUMNS

    def _iter_regions(self):
        """Yield (row_idx_or_None, col_name, bbox) for the active profile."""
        if self.profile == "gacha":
            gacha = self.config_manager.get_gacha()
            for row_idx, row_data in enumerate(gacha.get("rows", [])):
                for col_name in GACHA_ROW_COLUMNS:
                    if col_name in row_data:
                        yield row_idx, col_name, row_data[col_name]
            for col_name in GACHA_EXTRA_REGIONS:
                if col_name in gacha:
                    yield None, col_name, gacha[col_name]
        else:
            rows = self.config_manager.get("rows", [])
            for row_idx, row_data in enumerate(rows):
                for col_name in GUNSMOKE_COLUMNS:
                    if col_name in row_data:
                        yield row_idx, col_name, row_data[col_name]

    def show(self):
        prev_selected = self.selected
        self.hide()
        self.active = True
        self.selected = prev_selected

        for row_idx, col_name, bbox in self._iter_regions():
            x, y, w, h = bbox
            color = COLUMN_COLORS.get(col_name, THEME["text_strong"])

            if row_idx is None:
                label_text = COLUMN_LABEL.get(col_name, col_name)
            else:
                label_text = f"R{row_idx + 1} {COLUMN_LABEL.get(col_name, col_name)}"

            overlay = tk.Toplevel(self.root)
            overlay.geometry(f"{w}x{h}+{x}+{y}")
            overlay.overrideredirect(True)
            overlay.attributes("-alpha", ALPHA_NORMAL)
            overlay.attributes("-topmost", True)

            # Full-zone tint; label sits in the top-left of the scan area
            # (no separate floating label window above the region).
            frame = tk.Frame(overlay, bg=color, width=w, height=h, cursor="fleur")
            frame.pack(fill=tk.BOTH, expand=True)
            frame.pack_propagate(False)

            corner = tk.Label(
                frame,
                text=label_text,
                bg=color,
                fg="#ffffff",
                font=("Segoe UI", 7, "bold"),
                padx=3,
                pady=1,
                anchor=tk.NW,
            )
            corner.place(x=0, y=0, anchor=tk.NW)

            overlay.row_idx = row_idx
            overlay.col_name = col_name
            overlay.content_frame = frame
            overlay.corner_label = corner

            for widget in (frame, corner):
                widget.bind("<Button-1>", lambda e, o=overlay: self.start_drag(e, o))
                widget.bind("<B1-Motion>", lambda e, o=overlay: self.do_drag(e, o))
                widget.bind(
                    "<ButtonRelease-1>", lambda e, o=overlay: self.end_drag(e, o)
                )
            frame.bind("<Motion>", lambda e, o=overlay: self._on_hover(e, o))

            self.overlay_windows.append(overlay)

        self._ensure_keys_bound()
        self._update_selection_visual()

    def _ensure_keys_bound(self):
        """Bind arrow nudges once; handler no-ops when overlays are hidden."""
        if self._keys_bound:
            return
        for key in ("<Up>", "<Down>", "<Left>", "<Right>"):
            self.root.bind_all(key, self._on_arrow_key, add="+")
        self._keys_bound = True

    def _focus_is_text_input(self) -> bool:
        w = self.root.focus_get()
        if w is None:
            return False
        cls = w.winfo_class()
        if cls in ("Entry", "Text", "TEntry", "Spinbox"):
            return True
        name = type(w).__name__.lower()
        return "entry" in name or "text" in name

    def nudge_selected(self, dx: int, dy: int) -> bool:
        """Nudge the selected region (respects move lock). Returns True if applied."""
        if not self.active or self.selected is None:
            return False
        row_idx, col_name = self.selected
        self._apply_delta(row_idx, col_name, dx, dy)
        self.sync_geometries()
        if self.on_update_callback:
            self.on_update_callback(row_idx, col_name)
        return True

    def _on_arrow_key(self, event):
        # Entries handle their own arrows (nudge X/Y/W/H). Overlay nudge runs
        # only when focus is elsewhere and overlays are visible.
        if not self.active or self._focus_is_text_input():
            return
        if self.selected is None:
            return

        step = 10 if (event.state & 0x0001) else 1  # Shift = coarse
        dx = dy = 0
        if event.keysym == "Up":
            dy = -step
        elif event.keysym == "Down":
            dy = step
        elif event.keysym == "Left":
            dx = -step
        elif event.keysym == "Right":
            dx = step
        else:
            return

        self.nudge_selected(dx, dy)
        return "break"

    def _hit_resize_edge(self, event, overlay):
        # Use screen coords so hits work from the corner label too.
        w = max(overlay.winfo_width(), 1)
        h = max(overlay.winfo_height(), 1)
        local_x = event.x_root - overlay.winfo_rootx()
        local_y = event.y_root - overlay.winfo_rooty()
        near_e = local_x >= w - EDGE_PX
        near_s = local_y >= h - EDGE_PX
        if near_e and near_s:
            return "se"
        if near_e:
            return "e"
        if near_s:
            return "s"
        return None

    def _on_hover(self, event, overlay):
        if self.dragging:
            return
        edge = self._hit_resize_edge(event, overlay)
        cursors = {
            "e": "sb_h_double_arrow",
            "s": "sb_v_double_arrow",
            "se": "bottom_right_corner",
        }
        try:
            overlay.content_frame.configure(cursor=cursors.get(edge, "fleur"))
        except Exception:
            pass

    def _get_bbox_ref(self, row_idx, col_name):
        if self.profile == "gacha":
            gacha = self.config_manager.get_gacha()
            if row_idx is None:
                return gacha, col_name, gacha[col_name]
            return gacha["rows"][row_idx], col_name, gacha["rows"][row_idx][col_name]

        rows = self.config_manager.get("rows")
        return rows[row_idx], col_name, rows[row_idx][col_name]

    def _set_bbox(self, row_idx, col_name, bbox):
        container, key, _ = self._get_bbox_ref(row_idx, col_name)
        container[key] = bbox

    def _targets_for_move(self, row_idx, col_name):
        """Regions that should move together under the current lock mode."""
        if self.move_lock == "column" and row_idx is not None:
            if self.profile == "gacha":
                n = len(self.config_manager.get_gacha().get("rows", []))
            else:
                n = len(self.config_manager.get("rows", []))
            return [(i, col_name) for i in range(n)]

        if self.move_lock == "row" and row_idx is not None:
            return [(row_idx, c) for c in self._table_columns()]

        return [(row_idx, col_name)]

    def _apply_delta(self, row_idx, col_name, dx, dy):
        for r, c in self._targets_for_move(row_idx, col_name):
            _, _, bbox = self._get_bbox_ref(r, c)
            self._set_bbox(r, c, [bbox[0] + dx, bbox[1] + dy, bbox[2], bbox[3]])

    def sync_geometries(self):
        """Push current config bboxes into existing overlay windows."""
        for overlay in self.overlay_windows:
            try:
                _, _, bbox = self._get_bbox_ref(overlay.row_idx, overlay.col_name)
            except Exception:
                continue
            x, y, w, h = bbox
            overlay.geometry(f"{w}x{h}+{x}+{y}")
        self._update_selection_visual()

    def _update_selection_visual(self):
        for overlay in self.overlay_windows:
            is_sel = self.selected == (overlay.row_idx, overlay.col_name)
            try:
                overlay.attributes(
                    "-alpha", ALPHA_SELECTED if is_sel else ALPHA_NORMAL
                )
            except Exception:
                pass

    def start_drag(self, event, overlay):
        self.dragging = True
        self.drag_start = (event.x_root, event.y_root)
        self.dragging_overlay = overlay
        overlay.drag_moved = False
        self.resize_edge = self._hit_resize_edge(event, overlay)
        self.selected = (overlay.row_idx, overlay.col_name)
        self._update_selection_visual()
        if self.on_update_callback:
            self.on_update_callback(
                overlay.row_idx, overlay.col_name, select=True
            )

    def do_drag(self, event, overlay):
        if not self.dragging or self.dragging_overlay != overlay:
            return

        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]

        if abs(dx) > 2 or abs(dy) > 2:
            overlay.drag_moved = True

        _, _, bbox = self._get_bbox_ref(overlay.row_idx, overlay.col_name)
        x, y, w, h = bbox

        if self.resize_edge:
            new_x, new_y, new_w, new_h = x, y, w, h
            if "e" in self.resize_edge:
                new_w = max(MIN_W, w + dx)
            if "s" in self.resize_edge:
                new_h = max(MIN_H, h + dy)
            self._set_bbox(
                overlay.row_idx, overlay.col_name, [new_x, new_y, new_w, new_h]
            )
            # Resize applies to the active region only (use Fill others for W/H)
            overlay.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
        else:
            self._apply_delta(overlay.row_idx, overlay.col_name, dx, dy)
            self.sync_geometries()

        if self.on_update_callback:
            self.on_update_callback(overlay.row_idx, overlay.col_name)

        self.drag_start = (event.x_root, event.y_root)

    def end_drag(self, event, overlay):
        if self.dragging and self.dragging_overlay == overlay:
            if not getattr(overlay, "drag_moved", False):
                if self.on_update_callback:
                    self.on_update_callback(
                        overlay.row_idx, overlay.col_name, select=True
                    )
        self.dragging = False
        self.resize_edge = None
        self.dragging_overlay = None
