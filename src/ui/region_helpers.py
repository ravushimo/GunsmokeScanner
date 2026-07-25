"""Shared helpers for region calibration UI."""

from typing import Callable, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit

FIELD_INDEX = {"x": 0, "y": 1, "w": 2, "h": 3}


def bind_entry_arrow_nudge(entry: QLineEdit, field: str, on_nudge: Callable[[str, int], None]):
    """Arrow keys adjust the focused X/Y/W/H entry (Shift = ±10).

    Position fields use screen directions (Up decreases Y). Size fields use
    Up/Right to grow and Down/Left to shrink.
    """
    orig = entry.keyPressEvent

    def keyPressEvent(event: QKeyEvent, field_name=field):
        if event.key() not in (
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
        ):
            return orig(event)

        step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        delta = 0
        key = event.key()
        if field_name == "x":
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
                delta = -step
            elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
                delta = step
        elif field_name == "y":
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
                delta = -step
            elif key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
                delta = step
        else:
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Right):
                delta = step
            elif key in (Qt.Key.Key_Down, Qt.Key.Key_Left):
                delta = -step
        if delta == 0:
            return orig(event)
        on_nudge(field_name, delta)
        event.accept()

    entry.keyPressEvent = keyPressEvent  # type: ignore[method-assign]


def fill_field_across_rows(rows, col_name: str, field: str, value: int) -> int:
    """Copy one bbox field to every row that has `col_name`.

    Returns how many rows were updated.
    """
    idx = FIELD_INDEX[field]
    updated = 0
    for row in rows:
        if col_name not in row:
            continue
        bbox = list(row[col_name])
        bbox[idx] = value
        row[col_name] = bbox
        updated += 1
    return updated


def gap_from_first_two_rows(rows, col_name: str) -> Optional[Tuple[int, int]]:
    """Return (start_y, gap) from rows[0] and rows[1] for `col_name`, or None."""
    if len(rows) < 2:
        return None
    if col_name not in rows[0] or col_name not in rows[1]:
        return None
    y0 = int(rows[0][col_name][1])
    y1 = int(rows[1][col_name][1])
    gap = y1 - y0
    if gap == 0:
        return None
    return y0, gap


def distribute_ys_from_first_two(
    rows, col_name: str, sync_all_columns: bool = True
) -> Optional[int]:
    """Space row Y using the gap between row 1 and row 2 of `col_name`.

    When `sync_all_columns` is True, every column on a row gets the same Y
    (typical for a table). Returns the gap used, or None if it cannot run.
    """
    result = gap_from_first_two_rows(rows, col_name)
    if result is None:
        return None
    start_y, gap = result

    for i, row in enumerate(rows):
        target_y = start_y + i * gap
        cols = list(row.keys()) if sync_all_columns else [col_name]
        for key in cols:
            if key not in row:
                continue
            bbox = list(row[key])
            bbox[1] = target_y
            row[key] = bbox
    return gap
