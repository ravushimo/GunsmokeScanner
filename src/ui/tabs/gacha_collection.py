"""Gacha Collection - doll gallery with editable V-ranks (PySide6)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from src.constants import THEME
from src.core.gacha_names import doll_portrait_names, portrait_path_for_doll
from src.core.gacha_stats import MAX_COPIES
from src.data.gacha_db import GachaDB
from src.ui.qt_util import call_later, call_soon
from src.ui.styles import create_button, section_frame, toolbar_frame

_PORTRAIT_SIZE = 72
_CARD_W = 108
_CARD_H = 148
# Space reserved around each card so the grid has breathing room (baked into
# the delegate's sizeHint/gridSize instead of QListView spacing).
_CARD_GAP = 8
# Allow card width to flex +-10% so N columns fit the viewport without clipping.
_CARD_FLEX = 0.10
_BTN_SIZE = 22
# Stats "complete" accent - V6 done
_V6_BORDER = THEME["class_support"]


def _fit_card_width(usable_px: float) -> int:
    """Pick a card width (may flex +-10%) so whole columns fill the row evenly."""
    min_w = _CARD_W * (1.0 - _CARD_FLEX)
    max_w = _CARD_W * (1.0 + _CARD_FLEX)
    unit = min_w + _CARD_GAP
    if usable_px < unit:
        return int(round(min_w))

    cols = max(1, int(usable_px // unit))
    card_w = usable_px / cols - _CARD_GAP
    card_w = max(min_w, min(max_w, card_w))

    while cols > 1 and cols * unit > usable_px + 0.5:
        cols -= 1
        card_w = usable_px / cols - _CARD_GAP
        card_w = max(min_w, min(max_w, card_w))

    if cols * (card_w + _CARD_GAP) > usable_px + 0.5:
        card_w = max(min_w, usable_px / cols - _CARD_GAP)

    return max(1, int(round(card_w)))


def _load_portrait(name: str) -> Tuple[Optional[QPixmap], Optional[QPixmap]]:
    """Load owned + dimmed (45% alpha) portrait pixmaps for a doll name."""
    path = portrait_path_for_doll(name)
    if not path or not path.is_file():
        return None, None
    try:
        base = Image.open(path).convert("RGBA")
        base = base.resize((_PORTRAIT_SIZE, _PORTRAIT_SIZE), Image.Resampling.LANCZOS)
        owned = QPixmap.fromImage(ImageQt(base).copy())

        dim_img = base.copy()
        alpha = dim_img.split()[-1].point(lambda a: int(a * 0.45))
        dim_img.putalpha(alpha)
        dim = QPixmap.fromImage(ImageQt(dim_img).copy())
        return owned, dim
    except OSError:
        return None, None


class _DollListModel(QAbstractListModel):
    """Flat list of doll names; per-row copies/overrides/pixmaps update in place."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._names: List[str] = []
        self._rows: Dict[str, dict] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._names)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._names)):
            return None
        name = self._names[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return name
        if role == Qt.ItemDataRole.UserRole:
            row = self._rows.get(name, {})
            return {
                "name": name,
                "copies": row.get("copies", 0),
                "overridden": row.get("overridden", False),
                "pixmap_owned": row.get("pixmap_owned"),
                "pixmap_dim": row.get("pixmap_dim"),
            }
        return None

    def set_names(self, names: List[str]) -> None:
        self.beginResetModel()
        self._names = list(names)
        for name in self._names:
            self._rows.setdefault(name, {})
        self.endResetModel()

    def update_card(self, name: str, *, copies: int, overridden: bool) -> None:
        row = self._rows.setdefault(name, {})
        row["copies"] = copies
        row["overridden"] = overridden
        self._notify(name)

    def set_pixmaps(self, name: str, owned: Optional[QPixmap], dim: Optional[QPixmap]) -> None:
        row = self._rows.setdefault(name, {})
        row["pixmap_owned"] = owned
        row["pixmap_dim"] = dim
        self._notify(name)

    def _notify(self, name: str) -> None:
        try:
            row_idx = self._names.index(name)
        except ValueError:
            return
        idx = self.index(row_idx)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.UserRole])


class _CardDelegate(QStyledItemDelegate):
    """Paints a doll card (portrait, name, V-rank, edit +/-) for each list item."""

    bumpRequested = Signal(str, int)

    def __init__(self, fonts, parent=None):
        super().__init__(parent)
        self._fonts = fonts
        self._card_w = _CARD_W
        self.edit_mode = False

    def set_card_width(self, width: int) -> None:
        self._card_w = max(48, width)

    def sizeHint(self, _option, _index) -> QSize:  # noqa: N802
        return QSize(self._card_w + _CARD_GAP, _CARD_H + _CARD_GAP)

    def _geometry(self, rect: QRect):
        half = _CARD_GAP // 2
        inner = rect.adjusted(half, half, -half, -half)
        portrait_x = inner.x() + (inner.width() - _PORTRAIT_SIZE) // 2
        portrait_y = inner.y() + 8
        name_rect = QRect(inner.x() + 4, portrait_y + _PORTRAIT_SIZE + 2, inner.width() - 8, 32)
        rank_h = 26
        rank_y = inner.bottom() - rank_h - 4
        cx = inner.center().x()
        if self.edit_mode:
            minus_rect = QRect(cx - 18 - _BTN_SIZE, rank_y + (rank_h - _BTN_SIZE) // 2, _BTN_SIZE, _BTN_SIZE)
            plus_rect = QRect(cx + 18, rank_y + (rank_h - _BTN_SIZE) // 2, _BTN_SIZE, _BTN_SIZE)
            rank_rect = QRect(cx - 18, rank_y, 36, rank_h)
        else:
            minus_rect = QRect()
            plus_rect = QRect()
            rank_rect = QRect(inner.x(), rank_y, inner.width(), rank_h)
        portrait_rect = QRect(portrait_x, portrait_y, _PORTRAIT_SIZE, _PORTRAIT_SIZE)
        return inner, portrait_rect, name_rect, rank_rect, minus_rect, plus_rect

    def paint(self, painter: QPainter, option, index) -> None:
        data = index.data(Qt.ItemDataRole.UserRole) or {}
        name = data.get("name", "")
        copies = int(data.get("copies", 0))
        overridden = bool(data.get("overridden", False))
        owned = copies > 0

        inner, portrait_rect, name_rect, rank_rect, minus_rect, plus_rect = self._geometry(option.rect)

        painter.save()
        bg = THEME["bg_canvas"] if owned else THEME["bg_raised"]
        border = _V6_BORDER if copies >= MAX_COPIES else THEME["border"]
        painter.fillRect(inner, QColor(bg))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRect(inner.adjusted(0, 0, -1, -1))

        pix = data.get("pixmap_owned") if owned else data.get("pixmap_dim")
        if isinstance(pix, QPixmap) and not pix.isNull():
            painter.drawPixmap(portrait_rect, pix)

        painter.setFont(self._fonts.body)
        painter.setPen(QColor(THEME["text_strong"] if owned else THEME["text_muted"]))
        painter.drawText(
            name_rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            name,
        )

        rank_text = f"V{copies - 1}" if copies > 0 else "-"
        painter.setFont(self._fonts.body_medium)
        painter.setPen(QColor(THEME["accent_amber"] if overridden else THEME["text_primary"]))
        painter.drawText(rank_rect, int(Qt.AlignmentFlag.AlignCenter), rank_text)

        if self.edit_mode:
            self._draw_btn(painter, minus_rect, "-")
            self._draw_btn(painter, plus_rect, "+")

        painter.restore()

    def _draw_btn(self, painter: QPainter, rect: QRect, glyph: str) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(THEME["bg_raised"]))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QColor(THEME["text_strong"]))
        painter.setFont(self._fonts.ui)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), glyph)

    def editorEvent(self, event, _model, option, index) -> bool:  # noqa: N802
        if not self.edit_mode or event.type() != QEvent.Type.MouseButtonRelease:
            return False
        data = index.data(Qt.ItemDataRole.UserRole) or {}
        name = data.get("name", "")
        if not name:
            return False
        _inner, _portrait, _name_rect, _rank, minus_rect, plus_rect = self._geometry(option.rect)
        pos = event.position().toPoint()
        if minus_rect.contains(pos):
            self.bumpRequested.emit(name, -1)
            return True
        if plus_rect.contains(pos):
            self.bumpRequested.emit(name, 1)
            return True
        return False


class _CardListView(QListView):
    """Flow grid of doll cards; recomputes card width on viewport resize."""

    def __init__(self, tab: "GachaCollectionTab"):
        super().__init__()
        self._tab = tab
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setStyleSheet(f"QListView {{ background-color: {THEME['bg_canvas']}; border: none; }}")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._tab._schedule_relayout()


class GachaCollectionTab(QWidget):
    def __init__(self, parent, fonts, db: GachaDB = None, on_change=None):
        super().__init__(parent)
        self.fonts = fonts
        self.db = db or GachaDB()
        self.on_change = on_change

        self._edit_mode = False
        self._built = False
        self._doll_order: List[str] = []
        self._scanned: Dict[Tuple[str, str], int] = {}
        self._overrides: Dict[Tuple[str, str], int] = {}
        self._pixmap_owned: Dict[str, QPixmap] = {}
        self._pixmap_dim: Dict[str, QPixmap] = {}
        self._card_w = _CARD_W
        self._portrait_queue: List[str] = []
        self._portrait_pending = False
        self._relayout_pending = False
        self._notify_pending = False

        self.setStyleSheet(f"background-color: {THEME['bg_canvas']};")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 4)
        root.setSpacing(4)

        toolbar = toolbar_frame()
        root.addWidget(toolbar)
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(8, 6, 8, 6)
        toolbar_row.setSpacing(12)

        title = QLabel("Collection")
        title.setFont(self.fonts.subheading)
        title.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        toolbar_row.addWidget(title)

        desc = QLabel("Elite doll copies from scans (max V6). Edit to correct ranks outside Access Records.")
        desc.setFont(self.fonts.body)
        desc.setStyleSheet(f"color: {THEME['text_muted']}; background: transparent;")
        toolbar_row.addWidget(desc)
        toolbar_row.addStretch(1)

        self.edit_check = QCheckBox("Edit ranks")
        self.edit_check.setFont(self.fonts.ui)
        self.edit_check.setStyleSheet(f"color: {THEME['text_primary']}; background: transparent;")
        self.edit_check.toggled.connect(self._on_edit_toggle)
        toolbar_row.addWidget(self.edit_check)

        refresh_btn = create_button(toolbar, "Refresh", self.refresh, variant="secondary", font=self.fonts.ui)
        refresh_btn.setFixedSize(90, 28)
        toolbar_row.addWidget(refresh_btn)

        section = section_frame()
        root.addWidget(section, 1)
        section_lay = QVBoxLayout(section)
        section_lay.setContentsMargins(0, 8, 0, 2)
        section_lay.setSpacing(4)

        heading = QLabel("Dolls")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setFont(self.fonts.subheading)
        heading.setStyleSheet(f"color: {THEME['text_strong']}; background: transparent;")
        section_lay.addWidget(heading)

        self.model = _DollListModel(self)
        self.delegate = _CardDelegate(self.fonts, self)
        self.delegate.bumpRequested.connect(self._bump)

        self.list_view = _CardListView(self)
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(self.delegate)
        section_lay.addWidget(self.list_view, 1)

    # ---- layout / sizing ---------------------------------------------------
    def _schedule_relayout(self) -> None:
        if self._relayout_pending:
            return
        self._relayout_pending = True
        call_later(60, self._relayout)

    def _relayout(self) -> None:
        self._relayout_pending = False
        if not self._built:
            return
        usable = max(0, self.list_view.viewport().width() - 4)
        if usable < 40:
            return
        card_w = _fit_card_width(usable)
        if card_w == self._card_w:
            return
        self._card_w = card_w
        self.delegate.set_card_width(card_w)
        self.list_view.setGridSize(QSize(card_w + _CARD_GAP, _CARD_H + _CARD_GAP))
        self.list_view.viewport().update()

    # ---- portrait loading ---------------------------------------------------
    def _queue_portraits(self, names: List[str]) -> None:
        """Load portrait images in small idle chunks so first paint stays snappy."""
        self._portrait_queue = [n for n in names if n not in self._pixmap_owned]
        if self._portrait_queue and not self._portrait_pending:
            self._portrait_pending = True
            call_later(1, self._drain_portraits)

    def _drain_portraits(self) -> None:
        self._portrait_pending = False
        batch, self._portrait_queue = self._portrait_queue[:6], self._portrait_queue[6:]
        for name in batch:
            owned, dim = _load_portrait(name)
            if owned is not None:
                self._pixmap_owned[name] = owned
            if dim is not None:
                self._pixmap_dim[name] = dim
            self.model.set_pixmaps(name, owned, dim)
        if self._portrait_queue:
            self._portrait_pending = True
            call_later(8, self._drain_portraits)

    # ---- data ---------------------------------------------------------------
    def _effective_copies(self, name: str, item_type: str) -> Tuple[int, bool]:
        key = (name, item_type)
        scanned = int(self._scanned.get(key, 0))
        if key in self._overrides:
            return int(self._overrides[key]), True
        return min(scanned, MAX_COPIES), False

    def _load_counts(self) -> None:
        self._overrides = {
            k: v for k, v in self.db.get_collection_overrides().items() if k[1] == "Doll"
        }
        # Fast SQL aggregate - avoids annotate_pulls over the full timeline
        self._scanned = self.db.count_elite_copies(item_type="Doll")

    def _paint_all(self) -> None:
        for name in self._doll_order:
            copies, overridden = self._effective_copies(name, "Doll")
            self.model.update_card(name, copies=copies, overridden=overridden)

    def refresh(self) -> None:
        """Rebuild gallery once; later updates paint in place."""
        self._load_counts()

        if self._built:
            self._paint_all()
            call_soon(self._relayout)
            return

        self._doll_order = list(doll_portrait_names())
        self.model.set_names(self._doll_order)
        self._paint_all()
        self._built = True
        self._queue_portraits(self._doll_order)
        call_soon(self._relayout)

    # ---- edit mode ------------------------------------------------------
    def _on_edit_toggle(self, checked: bool) -> None:
        self._edit_mode = checked
        self.delegate.edit_mode = checked
        self.list_view.viewport().update()

    def _bump(self, name: str, delta: int) -> None:
        item_type = "Doll"
        key = (name, item_type)
        copies, _overridden = self._effective_copies(name, item_type)
        new = max(0, min(MAX_COPIES, copies + delta))
        scanned = int(self._scanned.get(key, 0))
        natural = min(scanned, MAX_COPIES)
        if new == natural:
            self.db.clear_collection_override(name, item_type)
            self._overrides.pop(key, None)
        else:
            self.db.set_collection_override(name, item_type, new)
            self._overrides[key] = new
        copies2, overridden2 = self._effective_copies(name, item_type)
        self.model.update_card(name, copies=copies2, overridden=overridden2)
        self._schedule_notify()

    def _schedule_notify(self) -> None:
        if not self.on_change:
            return
        if self._notify_pending:
            return
        self._notify_pending = True
        call_later(400, self._fire_notify)

    def _fire_notify(self) -> None:
        self._notify_pending = False
        if self.on_change:
            self.on_change()
