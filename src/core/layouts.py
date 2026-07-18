"""Bundled per-resolution capture layouts (F4 apply / Setup export)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.constants import (
    GACHA_EXTRA_REGIONS,
    GACHA_ROW_COLUMNS,
    INVENTORY_GROWTH_REGIONS,
)

Layout = Dict[str, Any]


def layouts_dir() -> Path:
    """Directory of shipped layout JSON files (dev + PyInstaller)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "layouts"
    return Path(__file__).resolve().parents[2] / "assets" / "layouts"


def writable_layouts_dir() -> Path:
    """Where Setup 'Save template' writes (project assets in dev)."""
    return layouts_dir()


def _layout_path(mode: str, width: int, height: int) -> Path:
    return layouts_dir() / f"{mode}_{width}x{height}.json"


def list_layouts(mode: str) -> List[Layout]:
    """Load all layouts for mode (gacha | gunsmoke)."""
    root = layouts_dir()
    if not root.is_dir():
        return []
    out: List[Layout] = []
    for path in sorted(root.glob(f"{mode}_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("mode") and data.get("mode") != mode:
            continue
        data.setdefault("mode", mode)
        data["_path"] = str(path)
        out.append(data)
    return out


def find_layout(
    mode: str, width: int, height: int
) -> Tuple[Optional[Layout], str]:
    """Pick best layout for screen size.

    Returns (layout_or_None, reason) where reason is
    'exact' | 'nearest_aspect' | 'none'.
    """
    layouts = list_layouts(mode)
    if not layouts:
        return None, "none"

    exact = None
    for lay in layouts:
        res = lay.get("resolution") or [0, 0]
        if int(res[0]) == width and int(res[1]) == height:
            exact = lay
            break
    if exact:
        return exact, "exact"

    # Nearest same aspect ratio (within 2%), else overall nearest by size delta
    target_ar = width / max(height, 1)
    same_ar: List[Tuple[float, Layout]] = []
    any_dist: List[Tuple[float, Layout]] = []
    for lay in layouts:
        res = lay.get("resolution") or [0, 0]
        rw, rh = int(res[0]), int(res[1])
        if rw <= 0 or rh <= 0:
            continue
        ar = rw / rh
        dist = abs(rw - width) + abs(rh - height)
        any_dist.append((dist, lay))
        if abs(ar - target_ar) / target_ar <= 0.02:
            same_ar.append((dist, lay))

    pool = same_ar or any_dist
    if not pool:
        return None, "none"
    pool.sort(key=lambda t: t[0])
    reason = "nearest_aspect" if same_ar else "nearest"
    return pool[0][1], reason


def layout_from_gacha_config(gacha: Dict[str, Any], width: int, height: int) -> Layout:
    """Build a gacha layout dict from live config geometry."""
    rows = []
    for row in gacha.get("rows") or []:
        rows.append({col: list(row[col]) for col in GACHA_ROW_COLUMNS if col in row})
    out: Layout = {
        "mode": "gacha",
        "resolution": [width, height],
        "rows": rows,
    }
    for key in GACHA_EXTRA_REGIONS:
        if key in gacha:
            out[key] = list(gacha[key])
    return out


def layout_from_gunsmoke_rows(
    rows: List[Dict[str, Any]], width: int, height: int
) -> Layout:
    return {
        "mode": "gunsmoke",
        "resolution": [width, height],
        "rows": [
            {k: list(v) for k, v in row.items()}
            for row in rows
        ],
    }


def save_layout(layout: Layout) -> Path:
    """Write layout JSON beside bundled assets. Returns path written."""
    mode = layout.get("mode") or "gacha"
    res = layout.get("resolution") or [0, 0]
    width, height = int(res[0]), int(res[1])
    root = writable_layouts_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{mode}_{width}x{height}.json"
    payload = {k: v for k, v in layout.items() if not str(k).startswith("_")}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def apply_gacha_layout(config: Dict[str, Any], layout: Layout) -> None:
    """Copy region geometry from layout into config['gacha'] (mutates)."""
    gacha = config.setdefault("gacha", {})
    gacha["rows"] = [
        {k: list(v) for k, v in row.items()}
        for row in layout.get("rows") or []
    ]
    for key in GACHA_EXTRA_REGIONS:
        if key in layout:
            gacha[key] = list(layout[key])
    res = layout.get("resolution")
    if res:
        config["screen_resolution"] = [int(res[0]), int(res[1])]


def apply_gunsmoke_layout(config: Dict[str, Any], layout: Layout) -> None:
    config["rows"] = [
        {k: list(v) for k, v in row.items()}
        for row in layout.get("rows") or []
    ]
    res = layout.get("resolution")
    if res:
        config["screen_resolution"] = [int(res[0]), int(res[1])]


def layout_from_inventory_growth(
    growth: Dict[str, Any], width: int, height: int
) -> Layout:
    out: Layout = {
        "mode": "inventory",
        "resolution": [width, height],
        "cols": int(growth.get("cols", 14)),
        "rows": int(growth.get("rows", 6)),
        "cell_lock_inset": list(growth.get("cell_lock_inset") or [10, 48, 40, 40]),
    }
    for key in INVENTORY_GROWTH_REGIONS:
        if key in growth:
            out[key] = list(growth[key])
    for key in (
        "click_delay_ms",
        "ocr_settle_ms",
        "lock_click_delay_ms",
        "scroll_rows",
        "scroll_extra_px",
        "skip_rows_after_scroll",
        "scroll_duration_ms",
        "scroll_settle_ms",
    ):
        if key in growth:
            out[key] = growth[key]
    return out


def apply_inventory_layout(config: Dict[str, Any], layout: Layout) -> None:
    growth = config.setdefault("inventory", {}).setdefault("growth", {})
    for key in INVENTORY_GROWTH_REGIONS:
        if key in layout:
            growth[key] = list(layout[key])
    if "cols" in layout:
        growth["cols"] = int(layout["cols"])
    if "rows" in layout:
        growth["rows"] = int(layout["rows"])
    if "cell_lock_inset" in layout:
        growth["cell_lock_inset"] = list(layout["cell_lock_inset"])
    for key in (
        "click_delay_ms",
        "ocr_settle_ms",
        "lock_click_delay_ms",
        "scroll_rows",
        "scroll_extra_px",
        "skip_rows_after_scroll",
        "scroll_duration_ms",
        "scroll_settle_ms",
    ):
        if key in layout:
            growth[key] = layout[key]
    res = layout.get("resolution")
    if res:
        config["screen_resolution"] = [int(res[0]), int(res[1])]
