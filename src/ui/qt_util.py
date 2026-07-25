"""Small Qt helpers shared across the UI."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, Slot


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
