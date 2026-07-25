"""Small Qt helpers shared across the UI."""

from __future__ import annotations

from typing import Callable, Sequence

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication


class _CallSoonBridge(QObject):
    """Marshal callables onto the Qt GUI thread from any thread.

    QTimer.singleShot from a non-Qt thread (e.g. `keyboard` hotkeys) is
    unreliable; a queued Signal always lands on the receiver's thread.
    """

    requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.requested.connect(self._run)

    @Slot(object)
    def _run(self, fn: object) -> None:
        if callable(fn):
            fn()


_bridge: _CallSoonBridge | None = None


def warm_call_soon() -> None:
    """Create the bridge on the GUI thread (call once after QApplication exists)."""
    _get_bridge()


def _get_bridge() -> _CallSoonBridge:
    global _bridge
    if _bridge is None:
        _bridge = _CallSoonBridge()
        app = QCoreApplication.instance()
        if app is not None:
            _bridge.moveToThread(app.thread())
    return _bridge


def call_soon(fn: Callable) -> None:
    """Marshal a callable onto the Qt GUI thread (safe from hotkey threads)."""
    _get_bridge().requested.emit(fn)


def call_later(ms: int, fn: Callable) -> None:
    """Schedule a callable after `ms` milliseconds on the GUI thread."""
    # Create the QTimer on the GUI thread.
    call_soon(lambda: QTimer.singleShot(int(ms), fn))


def screen_pixel_scale() -> float:
    """Physical pixels per Qt logical pixel (1.0 when display scaling is 100%).

    Config / ImageGrab / layout templates use physical pixels. Qt widget
    geometry and mouse events use logical pixels. At 125% Windows scale this
    is 1.25 - without conversion overlays look correct while OCR grabs wrong.
    """
    app = QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    dpr = float(screen.devicePixelRatio())
    return dpr if dpr > 0 else 1.0


def physical_to_logical_bbox(bbox: Sequence[float]) -> tuple[int, int, int, int]:
    """Convert a physical [x, y, w, h] bbox to Qt logical geometry."""
    scale = screen_pixel_scale()
    x, y, w, h = (float(v) for v in bbox[:4])
    return (
        int(round(x / scale)),
        int(round(y / scale)),
        max(1, int(round(w / scale))),
        max(1, int(round(h / scale))),
    )


def logical_delta_to_physical(dx: float, dy: float) -> tuple[int, int]:
    """Convert a Qt mouse/keyboard delta from logical to physical pixels."""
    scale = screen_pixel_scale()
    return int(round(dx * scale)), int(round(dy * scale))
