"""Region-picker overlay windows drawn on top of the GFL2 game.

Each region is a frameless, semi-transparent PySide6 QWidget that stays
above other windows and supports click-drag plus edge resize.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from src.constants import (
    GACHA_EXTRA_REGIONS,
    GACHA_ROW_COLUMNS,
    INVENTORY_GROWTH_REGIONS,
    THEME,
)

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
    "grid": THEME["class_bulwark"],
    "icon": THEME["class_vanguard"],
    "perks": THEME["class_support"],
    "lock_btn": THEME["accent_orange"],
    "own_count": THEME["warning"],
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
    "grid": "Grid",
    "icon": "Icon",
    "perks": "Perks",
    "lock_btn": "Lock",
    "own_count": "Own",
}

EDGE_PX = 10
MIN_W = 16
MIN_H = 12
ALPHA_NORMAL = 0.20
ALPHA_SELECTED = 0.40

_RESIZE_CURSORS = {
    "e": Qt.CursorShape.SizeHorCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
}


def _event_global_xy(event) -> tuple[float, float]:
    pos = event.globalPosition()
    return pos.x(), pos.y()


class _ArrowKeyEventFilter(QObject):
    """Application-wide arrow nudge when overlays are visible."""

    def __init__(self, manager: OverlayManager):
        super().__init__()
        self._manager = manager

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if not self._manager.active:
            return False
        if self._manager._focus_is_text_input():
            return False
        if self._manager.selected is None:
            return False

        step = (
            10
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            else 1
        )
        key = event.key()
        dx = dy = 0
        if key == Qt.Key.Key_Up:
            dy = -step
        elif key == Qt.Key.Key_Down:
            dy = step
        elif key == Qt.Key.Key_Left:
            dx = -step
        elif key == Qt.Key.Key_Right:
            dx = step
        else:
            return False

        self._manager.nudge_selected(dx, dy)
        return True


class OverlayRegionWidget(QWidget):
    """Single semi-transparent scan region overlay."""

    def __init__(
        self,
        manager: OverlayManager,
        row_idx,
        col_name: str,
        x: int,
        y: int,
        w: int,
        h: int,
        color: str,
        label_text: str,
    ):
        super().__init__(None)
        self.manager = manager
        self.row_idx = row_idx
        self.col_name = col_name
        self.drag_moved = False
        self.content_frame = self

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(ALPHA_NORMAL)
        self.setStyleSheet(f"background-color: {color};")

        self.corner_label = QLabel(label_text, self)
        self.corner_label.setStyleSheet(
            f"color: #ffffff; background-color: {color}; padding: 1px 3px;"
        )
        label_font = QFont("Segoe UI", 7)
        label_font.setBold(True)
        self.corner_label.setFont(label_font)
        self.corner_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.corner_label.move(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.manager.start_drag(event, self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.manager.do_drag(event, self)
        else:
            self.manager._on_hover(event, self)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.manager.end_drag(event, self)
        super().mouseReleaseEvent(event)


class OverlayManager:
    def __init__(self, root, config_manager, fonts=None, on_update_callback=None):
        self.root = root
        self.config_manager = config_manager
        self.fonts = fonts
        self.on_update_callback = on_update_callback

        self.profile = "gunsmoke"  # "gunsmoke" | "gacha" | "inventory"
        self.move_lock = "none"  # "none" | "column" | "row"
        self.selected = None  # (row_idx|None, col_name)

        self.overlay_windows = []
        self.active = False
        self.dragging = False
        self.drag_start = None
        self.dragging_overlay = None
        self.resize_edge = None  # None | "e" | "s" | "se"
        self._keys_bound = False
        self._arrow_filter = None

    def set_profile(self, profile: str):
        if profile not in ("gunsmoke", "gacha", "inventory"):
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
                    overlay.close()
                except Exception:
                    pass
        self.overlay_windows = []
        self.active = False
        self.dragging = False
        self.resize_edge = None

    def _table_columns(self):
        if self.profile == "gacha":
            return GACHA_ROW_COLUMNS
        if self.profile == "inventory":
            return INVENTORY_GROWTH_REGIONS
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
        elif self.profile == "inventory":
            growth = self.config_manager.get_inventory_growth()
            for col_name in INVENTORY_GROWTH_REGIONS:
                if col_name in growth:
                    yield None, col_name, growth[col_name]
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

            overlay = OverlayRegionWidget(
                self, row_idx, col_name, x, y, w, h, color, label_text
            )
            overlay.show()
            self.overlay_windows.append(overlay)

        self._ensure_keys_bound()
        self._update_selection_visual()

    def _ensure_keys_bound(self):
        """Install arrow nudge filter once; handler no-ops when overlays are hidden."""
        if self._keys_bound:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._arrow_filter = _ArrowKeyEventFilter(self)
        app.installEventFilter(self._arrow_filter)
        self._keys_bound = True

    def _focus_is_text_input(self) -> bool:
        w = QApplication.focusWidget()
        if w is None:
            return False
        if isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox)):
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

    def _hit_resize_edge(self, event, overlay):
        local = overlay.mapFromGlobal(event.globalPosition().toPoint())
        w = max(overlay.width(), 1)
        h = max(overlay.height(), 1)
        local_x = local.x()
        local_y = local.y()
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
        try:
            overlay.content_frame.setCursor(
                QCursor(_RESIZE_CURSORS.get(edge, Qt.CursorShape.SizeAllCursor))
            )
        except Exception:
            pass

    def _get_bbox_ref(self, row_idx, col_name):
        if self.profile == "gacha":
            gacha = self.config_manager.get_gacha()
            if row_idx is None:
                return gacha, col_name, gacha[col_name]
            return gacha["rows"][row_idx], col_name, gacha["rows"][row_idx][col_name]

        if self.profile == "inventory":
            growth = self.config_manager.get_inventory_growth()
            return growth, col_name, growth[col_name]

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
            elif self.profile == "inventory":
                return [(row_idx, col_name)]
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
            overlay.setGeometry(x, y, w, h)
        self._update_selection_visual()

    def _update_selection_visual(self):
        for overlay in self.overlay_windows:
            is_sel = self.selected == (overlay.row_idx, overlay.col_name)
            try:
                overlay.setWindowOpacity(
                    ALPHA_SELECTED if is_sel else ALPHA_NORMAL
                )
            except Exception:
                pass

    def start_drag(self, event, overlay):
        self.dragging = True
        self.drag_start = _event_global_xy(event)
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

        gx, gy = _event_global_xy(event)
        dx = gx - self.drag_start[0]
        dy = gy - self.drag_start[1]

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
            overlay.setGeometry(new_x, new_y, new_w, new_h)
        else:
            self._apply_delta(overlay.row_idx, overlay.col_name, dx, dy)
            self.sync_geometries()

        if self.on_update_callback:
            self.on_update_callback(overlay.row_idx, overlay.col_name)

        self.drag_start = (gx, gy)

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
