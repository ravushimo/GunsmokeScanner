"""Lightweight finish notifications (sound)."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


def _media_candidates() -> list[Path]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    media = windir / "Media"
    names = (
        "Windows Notify.wav",
        "Windows Notify System Generic.wav",
        "Windows Background.wav",
        "chimes.wav",
        "tada.wav",
        "notify.wav",
    )
    return [media / n for n in names]


def play_scan_complete_sound() -> None:
    """Play a short happy cue when a gacha scan finishes (async, best-effort)."""
    if sys.platform != "win32":
        return

    def _play():
        try:
            import winsound
        except ImportError:
            return

        for path in _media_candidates():
            if path.is_file():
                try:
                    winsound.PlaySound(
                        str(path),
                        winsound.SND_FILENAME | winsound.SND_ASYNC,
                    )
                    return
                except Exception:
                    continue

        # Fallback: short ascending beeps
        try:
            for freq, dur in ((880, 120), (1175, 140), (1568, 180)):
                winsound.Beep(freq, dur)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()
