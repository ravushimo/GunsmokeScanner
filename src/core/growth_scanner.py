"""Growth Data inventory scanner: grid click, lock skip, detail OCR, auto-scroll."""

from __future__ import annotations

import re
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pyautogui

from src.core.growth_names import parse_perks_from_text, parse_type_line
from src.core.scanner import safe_grab
from src.data.inventory_db import InventoryDB

StatusCB = Optional[Callable[[str], None]]
CoreCB = Optional[Callable[[Dict], None]]


def _fail_reason(core: Optional[Dict]) -> str:
    if core is None:
        return "no detail"
    if not core.get("type"):
        return "type incomplete"
    if len(core.get("perks") or []) < 2:
        return "perks incomplete"
    return "incomplete"


def _perk_summary(perks: List[Dict]) -> str:
    parts = []
    for p in perks or []:
        name = p.get("name")
        if not name:
            continue
        parts.append(f"{name} {p.get('level', '?')}")
    return ", ".join(parts)


# Orange padlock ink (HSV) — tuned for GFL2 lock badge (not the tile bottom bar)
_LOCK_HSV_LOW = np.array([5, 140, 160], dtype=np.uint8)
_LOCK_HSV_HIGH = np.array([22, 255, 255], dtype=np.uint8)


def cell_bbox(grid: List[int], cols: int, rows: int, col: int, row: int) -> List[int]:
    gx, gy, gw, gh = [int(v) for v in grid]
    cw = gw / cols
    ch = gh / rows
    x = int(gx + col * cw)
    y = int(gy + row * ch)
    return [x, y, max(1, int(round(cw))), max(1, int(round(ch)))]


def cell_center(grid: List[int], cols: int, rows: int, col: int, row: int) -> Tuple[int, int]:
    x, y, w, h = cell_bbox(grid, cols, rows, col, row)
    return x + w // 2, y + h // 2


def cell_lock_bbox(
    grid: List[int],
    cols: int,
    rows: int,
    col: int,
    row: int,
    inset: List[int],
) -> List[int]:
    cx, cy, cw, ch = cell_bbox(grid, cols, rows, col, row)
    ix, iy, iw, ih = [int(v) for v in inset]
    return [cx + ix, cy + iy, max(1, iw), max(1, ih)]


def has_orange_lock(img: Optional[np.ndarray], *, min_pixels: int = 18) -> bool:
    """True if region has a compact orange padlock blob (not a full-width rarity bar)."""
    if img is None or img.size == 0:
        return False
    rgb = img[:, :, :3] if img.ndim == 3 else img
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, _LOCK_HSV_LOW, _LOCK_HSV_HIGH)
    count = int(cv2.countNonZero(mask))
    if count < min_pixels:
        return False

    h, w = mask.shape[:2]
    area = max(1, h * w)
    # Bottom rarity bars / thick selection fill most of a sample — reject those.
    if count > area * 0.55:
        return False

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < min_pixels:
        return False
    _x, _y, bw, bh = cv2.boundingRect(largest)
    # Padlock is roughly square-ish and not spanning the whole width.
    if bw > w * 0.85:
        return False
    if bh > 0 and bw / bh > 2.8:
        return False
    return True


def parse_own_count(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*/\s*\d+", text or "")
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*/", text or "")
    return int(m.group(1)) if m else None


class GrowthScanner:
    def __init__(self, config_manager, ocr_processor, db: Optional[InventoryDB] = None):
        self.config_manager = config_manager
        self.ocr = ocr_processor
        self.db = db or InventoryDB()
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def _cfg(self) -> dict:
        return self.config_manager.get_inventory_growth()

    def _sleep_ms(self, key: str, default: int) -> None:
        ms = int(self._cfg().get(key, default))
        if ms > 0:
            time.sleep(ms / 1000.0)

    def _cell_size(self) -> Tuple[float, float]:
        cfg = self._cfg()
        grid = cfg["grid"]
        cols = max(1, int(cfg.get("cols", 14)))
        rows = max(1, int(cfg.get("rows", 6)))
        return grid[2] / cols, grid[3] / rows

    def is_cell_locked(self, col: int, row: int) -> bool:
        cfg = self._cfg()
        grid = cfg["grid"]
        cols = int(cfg.get("cols", 14))
        rows = int(cfg.get("rows", 6))
        inset = cfg.get("cell_lock_inset") or [8, 40, 36, 36]
        bbox = cell_lock_bbox(grid, cols, rows, col, row, inset)
        return has_orange_lock(safe_grab(bbox), min_pixels=14)

    def is_detail_locked(self) -> bool:
        bbox = self._cfg().get("lock_btn")
        if not bbox:
            return False
        return has_orange_lock(safe_grab(bbox), min_pixels=12)

    def click_cell(self, col: int, row: int) -> None:
        cfg = self._cfg()
        x, y = cell_center(
            cfg["grid"], int(cfg.get("cols", 14)), int(cfg.get("rows", 6)), col, row
        )
        pyautogui.click(x, y)
        self._sleep_ms("click_delay_ms", 80)
        self._sleep_ms("ocr_settle_ms", 250)

    def click_detail_lock(self) -> None:
        bbox = self._cfg().get("lock_btn")
        if not bbox:
            return
        x, y, w, h = [int(v) for v in bbox]
        pyautogui.click(x + w // 2, y + h // 2)
        self._sleep_ms("lock_click_delay_ms", 120)

    def ocr_region(self, key: str) -> str:
        bbox = self._cfg().get(key)
        if not bbox:
            return ""
        img = safe_grab(bbox)
        if img is None:
            return ""
        return self.ocr.extract_text(img, config=self.config_manager.config)

    def read_own_count(self) -> Optional[int]:
        return parse_own_count(self.ocr_region("own_count"))

    def parse_detail(self) -> Optional[Dict]:
        """OCR type + perks only (no name/icon identity)."""
        type_raw = self.ocr_region("type")
        perks_raw = self.ocr_region("perks")
        perks = parse_perks_from_text(perks_raw)
        core_type = parse_type_line(type_raw)

        if not core_type or len(perks) < 2:
            return {
                "ok": False,
                "type": core_type,
                "perks": perks,
                "raw": {"type": type_raw, "perks": perks_raw},
            }

        return {
            "ok": True,
            "type": core_type,
            "perks": perks,
            "raw": {"type": type_raw, "perks": perks_raw},
        }

    def persist_and_lock(self, core: Dict) -> Tuple[bool, int]:
        is_new, qty = self.db.upsert_core(core["type"], core["perks"])
        self.click_detail_lock()
        return is_new, qty

    def scroll_page(self, *, status: StatusCB = None) -> int:
        """Drag upward by ~scroll_rows cell heights (default rows-1) + extra px.

        Returns pixel distance dragged. Prefer overlapping one row instead of a
        full-grid drag (full-grid overshoots after the first page).
        """
        cfg = self._cfg()
        gx, gy, gw, gh = [int(v) for v in cfg["grid"]]
        _cw, ch = self._cell_size()
        rows = max(1, int(cfg.get("rows", 6)))
        scroll_rows = float(cfg.get("scroll_rows", max(1, rows - 1)))
        extra = int(cfg.get("scroll_extra_px", 0))
        distance = int(round(scroll_rows * ch + extra))
        distance = max(40, min(distance, gh - 40))

        # Drag near left side of grid, from lower third upward by `distance`.
        drag_x = gx + max(24, gw // 10)
        start_y = gy + gh - 30
        end_y = max(gy + 20, start_y - distance)

        duration = max(0.25, int(cfg.get("scroll_duration_ms", 700)) / 1000.0)
        if status:
            status(
                f"Scroll drag {distance}px "
                f"({scroll_rows:g} rows × {ch:.0f}px + {extra}px)…"
            )
        pyautogui.moveTo(drag_x, start_y)
        time.sleep(0.05)
        pyautogui.mouseDown()
        pyautogui.moveTo(drag_x, end_y, duration=duration)
        time.sleep(0.2)
        pyautogui.mouseUp()
        self._sleep_ms("scroll_settle_ms", 500)
        return distance

    def scan_single(
        self,
        *,
        status: StatusCB = None,
        on_core: CoreCB = None,
    ) -> Optional[Dict]:
        """F8: OCR type/perks on current detail; lock if successful."""
        self._stop = False
        if self.is_detail_locked():
            if status:
                status("Already locked — skipped.")
            return None
        core = self.parse_detail()
        if not core or not core.get("ok"):
            if status:
                status(f"Could not parse detail ({_fail_reason(core)}) — left unlocked.")
            return core
        is_new, qty = self.persist_and_lock(core)
        core["quantity"] = qty
        core["is_new"] = is_new
        if status:
            status(
                f"Saved [{core['type']}] {_perk_summary(core['perks'])} qty={qty}"
            )
        if on_core:
            on_core(core)
        return core

    def _parse_detail_with_retry(self) -> Optional[Dict]:
        core = self.parse_detail()
        if core is not None and core.get("ok"):
            return core
        if core is not None and not core.get("ok"):
            # Type/perks incomplete — retry once in case UI was still settling
            time.sleep(0.25)
            return self.parse_detail()
        time.sleep(0.25)
        return self.parse_detail()

    def _walk_cells(
        self,
        cells: List[Tuple[int, int]],
        *,
        status: StatusCB,
        on_core: CoreCB,
    ) -> Tuple[int, int, int]:
        """Returns (scanned, skipped_locked, unlocked_seen)."""
        scanned = 0
        skipped = 0
        unlocked_seen = 0
        for col, row in cells:
            if self._stop:
                break
            label = f"R{row + 1}C{col + 1}"
            if self.is_cell_locked(col, row):
                skipped += 1
                if status:
                    status(f"{label}: skip — grid lock badge")
                continue
            self.click_cell(col, row)
            if self._stop:
                break
            if self.is_detail_locked():
                skipped += 1
                if status:
                    status(f"{label}: skip — detail already locked")
                continue
            core = self._parse_detail_with_retry()
            if core is None:
                if status:
                    status(f"{label}: skip — no detail")
                continue
            unlocked_seen += 1
            if not core.get("ok"):
                if status:
                    raw = core.get("raw") or {}
                    status(
                        f"{label}: parse failed ({_fail_reason(core)}) — left unlocked "
                        f"[type={raw.get('type', '')!r}]"
                    )
                continue
            is_new, qty = self.persist_and_lock(core)
            scanned += 1
            core["quantity"] = qty
            core["is_new"] = is_new
            if status:
                status(
                    f"{label}: [{core['type']}] {_perk_summary(core['perks'])} "
                    f"qty={qty}"
                )
            if on_core:
                on_core(core)
        return scanned, skipped, unlocked_seen

    def scan_last_row(
        self,
        *,
        status: StatusCB = None,
        on_core: CoreCB = None,
    ) -> Dict[str, int]:
        """F7: bottom row only."""
        self._stop = False
        cfg = self._cfg()
        cols = int(cfg.get("cols", 14))
        rows = int(cfg.get("rows", 6))
        cells = [(c, rows - 1) for c in range(cols)]
        if status:
            status("Scanning last row…")
        scanned, skipped, unlocked = self._walk_cells(
            cells, status=status, on_core=on_core
        )
        if status:
            status(
                f"Last row done — scanned {scanned}, skipped locked {skipped}, "
                f"unlocked seen {unlocked}"
            )
        return {
            "scanned": scanned,
            "skipped_locked": skipped,
            "unlocked_seen": unlocked,
        }

    def scan_full(
        self,
        *,
        status: StatusCB = None,
        on_core: CoreCB = None,
        max_pages: int = 80,
    ) -> Dict[str, int]:
        """F9: walk pages with auto-scroll; stop when a page is all locked."""
        self._stop = False
        cfg = self._cfg()
        cols = int(cfg.get("cols", 14))
        rows = int(cfg.get("rows", 6))
        skip_top = max(0, int(cfg.get("skip_rows_after_scroll", 1)))
        own = self.read_own_count()
        session_id = self.db.start_session(own)
        if status:
            own_txt = str(own) if own is not None else "?"
            status(
                f"Full scan started (Own {own_txt}). "
                f"After each scroll, skip top {skip_top} row(s)."
            )

        total_scanned = 0
        total_skipped = 0
        pages = 0
        after_scroll = False

        while not self._stop and pages < max_pages:
            pages += 1
            start_row = skip_top if after_scroll else 0
            cells = [
                (c, r) for r in range(start_row, rows) for c in range(cols)
            ]
            if status:
                if start_row:
                    status(
                        f"Page {pages}: walking rows {start_row + 1}–{rows} "
                        f"({cols} cols; skipped top {start_row})…"
                    )
                else:
                    status(f"Page {pages}: walking {cols}×{rows}…")
            scanned, skipped, unlocked = self._walk_cells(
                cells, status=status, on_core=on_core
            )
            total_scanned += scanned
            total_skipped += skipped
            if self._stop:
                break
            if unlocked == 0 and scanned == 0:
                if status:
                    status(
                        f"Stop — page {pages} fully locked/empty "
                        f"(session scanned {total_scanned})."
                    )
                break
            if status:
                status(f"Page {pages} done — scrolling…")
            self.scroll_page(status=status)
            after_scroll = True

        self.db.end_session(
            session_id,
            slots_scanned=total_scanned,
            slots_skipped_locked=total_skipped,
        )
        return {
            "scanned": total_scanned,
            "skipped_locked": total_skipped,
            "pages": pages,
            "own_count": own or 0,
        }
