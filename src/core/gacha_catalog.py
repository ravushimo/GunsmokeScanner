"""Load gacha name / banner catalogs from assets/gacha/*.json."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _gacha_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "gacha"
    return Path(__file__).resolve().parents[2] / "assets" / "gacha"


def _read_json(name: str) -> dict:
    path = _gacha_dir() / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def load_banners() -> Tuple[Dict[str, Any], ...]:
    data = _read_json("banners.json")
    rows = data.get("banners") or []
    return tuple(dict(r) for r in rows if r.get("source"))


@lru_cache(maxsize=1)
def load_dolls() -> Dict[str, Tuple[str, ...]]:
    data = _read_json("dolls.json")
    return {
        "standard": tuple(data.get("standard") or ()),
        "elite": tuple(data.get("elite") or ()),
        "standard_elite": tuple(data.get("standard_elite") or ()),
    }


@lru_cache(maxsize=1)
def load_weapons() -> Dict[str, Tuple[str, ...]]:
    data = _read_json("weapons.json")
    return {
        "standard": tuple(data.get("standard") or ()),
        "elite": tuple(data.get("elite") or ()),
        "retired": tuple(data.get("retired") or ()),
        "standard_elite": tuple(data.get("standard_elite") or ()),
        "named": tuple(data.get("named") or ()),
    }


@lru_cache(maxsize=1)
def known_sources() -> Tuple[str, ...]:
    return tuple(b["source"] for b in load_banners())


@lru_cache(maxsize=1)
def banner_labels() -> Dict[str, str]:
    return {b["source"]: b.get("label") or b["source"] for b in load_banners()}


@lru_cache(maxsize=1)
def doll_pity_sources() -> frozenset:
    return frozenset(b["source"] for b in load_banners() if b.get("pity") == "doll")


@lru_cache(maxsize=1)
def weapon_pity_sources() -> frozenset:
    return frozenset(b["source"] for b in load_banners() if b.get("pity") == "weapon")


@lru_cache(maxsize=1)
def fifty_fifty_sources() -> frozenset:
    return frozenset(b["source"] for b in load_banners() if b.get("fifty_fifty"))


@lru_cache(maxsize=1)
def standard_source() -> str:
    for b in load_banners():
        if b.get("pity") == "standard":
            return b["source"]
    return "Standard Procurement"


def banner_filter_order() -> List[Tuple[str, Optional[str]]]:
    """UI filter: All, then each banner label -> source."""
    out: List[Tuple[str, Optional[str]]] = [("All", None)]
    for b in load_banners():
        out.append((b.get("label") or b["source"], b["source"]))
    return out


def pity_summary_keys() -> List[Tuple[str, str, str]]:
    """(label, summary_key, source) for pity meters."""
    key_map = {
        "Targeted Procurement": "pity_doll",
        "Military Upgrade": "pity_weapon",
        "Custom Procurement - Dolls": "pity_custom_doll",
        "Custom Procurement - Weapons": "pity_custom_weapon",
        "Reunion Procurement - Doll": "pity_reunion_doll",
        "Reunion Procurement - Weapon": "pity_reunion_weapon",
        "Standard Procurement": "pity_standard",
    }
    out: List[Tuple[str, str, str]] = []
    for b in load_banners():
        src = b["source"]
        label = b.get("label") or src
        out.append((label, key_map.get(src, f"pity_{src}"), src))
    return out
