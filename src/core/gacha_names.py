"""Canonical gacha item names + type-aware fuzzy OCR repair.

Dolls and weapons can share stems (Lewis vs Lewis Gun, OTs-14 doll vs
OTs-14 weapon). Always pass item_type so catalogs never cross-match.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# --- Standard (purple) dolls that appear on Access Records ---
STANDARD_DOLLS: Tuple[str, ...] = (
    "Ksenia",
    "Littara",
    "Colphne",
    "Krolik",
    "Nemesis",
    "Cheeta",
    "Sharkry",
    "Nagant",
    "Groza",
)

# --- Standard (purple) weapons ---
STANDARD_WEAPONS: Tuple[str, ...] = (
    "Stechkin",
    "Model ARM",
    ".380 Curva",
    "Hare",
    ".50 Nemesis",
    "MP7H1",
    "Robinson Modular Rifle",
    "Nagant M1895",
    "OTs-14",
    "Vepr-12",
    "Pecheneg-SP",
    "Model Alpha",
    "Model 100",
    "QBZ-191",
    "Sportivo Calibro 12",
    "Three-Line Rifle M1891",
    "CZ75",
    "TMP",
    "UMP40",
    "UMP45",
)

RETIRED_WEAPONS: Tuple[str, ...] = tuple(f"Retired {w}" for w in STANDARD_WEAPONS)

# Permanent Elite (gold) pool — keep in sync with gacha_pool keys, display form
STANDARD_ELITE_DOLL_NAMES: Tuple[str, ...] = (
    "Vepley",
    "Peritya",
    "Tololo",
    "Qiongjiu",
    "Sabrina",
    "Mosin-Nagant",
    "Faye",
    "Harpsy",
)

STANDARD_ELITE_WEAPON_NAMES: Tuple[str, ...] = (
    "Heart Seeker",
    "Optical Illusion",
    "Planeta",
    "Golden Melody",
    "Mezzaluna",
    "Samosek",
    "Hestia",
    "Antimony",
)

# Premium / unique weapons whose names collide with doll stems if matched globally.
# Extend as new shared-name weapons appear (Lewis Gun, future signature arms, …).
NAMED_WEAPONS: Tuple[str, ...] = (
    "Lewis Gun",
)

RETIRED_NAMED_WEAPONS: Tuple[str, ...] = tuple(
    f"Retired {w}" for w in NAMED_WEAPONS
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Letter-only OCR confusables. Do NOT map digits (0↔o, 1↔i) — that collapses
# Model 100 / UMP40 into Model Alpha / TMP-like keys.
_OCR_CONFUSABLES = str.maketrans(
    {
        "l": "i",
        "|": "i",
        "!": "i",
        "€": "e",
        "£": "e",
    }
)


def _assets_dolls_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "dolls"
    return Path(__file__).resolve().parents[2] / "assets" / "dolls"


def doll_portrait_names() -> Tuple[str, ...]:
    """Display names from assets/dolls/*.webp (underscore → space)."""
    root = _assets_dolls_dir()
    if not root.is_dir():
        return ()
    names: List[str] = []
    for p in sorted(root.glob("*.webp")):
        names.append(p.stem.replace("_", " "))
    return tuple(names)


def portrait_path_for_doll(name: str) -> Optional[Path]:
    """Resolve portrait file for a doll display name."""
    root = _assets_dolls_dir()
    if not root.is_dir() or not name:
        return None
    stem = name.strip().replace(" ", "_")
    direct = root / f"{stem}.webp"
    if direct.is_file():
        return direct
    key = _compact(name)
    for p in root.glob("*.webp"):
        if _compact(p.stem.replace("_", " ")) == key:
            return p
    return None


def _normalize_item_type(item_type: Optional[str]) -> str:
    t = (item_type or "").strip().lower()
    if t.startswith("weapon"):
        return "Weapons"
    if t.startswith("doll"):
        return "Doll"
    return ""


@lru_cache(maxsize=2)
def canonical_names_for_type(item_type: str) -> Tuple[str, ...]:
    """Known names for Doll or Weapons only (never mixed)."""
    kind = _normalize_item_type(item_type)
    seen = set()
    out: List[str] = []

    if kind == "Weapons":
        groups: Sequence[Sequence[str]] = (
            RETIRED_NAMED_WEAPONS,
            RETIRED_WEAPONS,
            NAMED_WEAPONS,
            STANDARD_WEAPONS,
            STANDARD_ELITE_WEAPON_NAMES,
        )
    elif kind == "Doll":
        groups = (
            STANDARD_ELITE_DOLL_NAMES,
            STANDARD_DOLLS,
            doll_portrait_names(),
        )
    else:
        return ()

    for group in groups:
        for n in group:
            if n not in seen:
                seen.add(n)
                out.append(n)
    return tuple(out)


@lru_cache(maxsize=1)
def all_canonical_names() -> Tuple[str, ...]:
    """Union of doll + weapon catalogs (tests / tooling only — prefer typed API)."""
    seen = set()
    out: List[str] = []
    for n in canonical_names_for_type("Doll") + canonical_names_for_type("Weapons"):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return tuple(out)


def _compact(text: str) -> str:
    s = (text or "").strip().lower().replace("×", "x")
    s = s.translate(_OCR_CONFUSABLES)
    return _NON_ALNUM.sub("", s)


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Prefer longer weapon titles over short doll stems (lewis vs lewisgun)
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if len(shorter) >= 4:
            coverage = len(shorter) / len(longer)
            if coverage >= 0.85:
                return max(0.82, coverage)
            return coverage * 0.9
    ratio = SequenceMatcher(None, a, b).ratio()
    # Penalize large length gaps so Model 100 ≉ Model Alpha, UMP40 ≉ TMP
    len_pen = min(len(a), len(b)) / max(len(a), len(b))
    return ratio * (0.55 + 0.45 * len_pen)


def resolve_item_name(
    raw: str,
    *,
    item_type: Optional[str] = None,
    known: Optional[Sequence[str]] = None,
    min_ratio: float = 0.78,
) -> str:
    """Map OCR text to a canonical name within the given item_type catalog."""
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", raw.strip())

    if known is not None:
        catalog = tuple(known)
    else:
        kind = _normalize_item_type(item_type)
        if not kind:
            # Without a type, refuse fuzzy cross-catalog matches — only exact
            # case-insensitive hit against the union.
            lower_map = {n.lower(): n for n in all_canonical_names()}
            return lower_map.get(text.lower(), text)
        catalog = canonical_names_for_type(kind)

    if not catalog:
        return text

    lower_map = {n.lower(): n for n in catalog}
    if text.lower() in lower_map:
        return lower_map[text.lower()]

    compact_raw = _compact(text)
    if not compact_raw:
        return text

    compact_map: Dict[str, str] = {}
    for n in catalog:
        c = _compact(n)
        compact_map.setdefault(c, n)

    if compact_raw in compact_map:
        return compact_map[compact_raw]

    best_name = text
    best_score = 0.0
    for c, n in compact_map.items():
        score = _similarity(compact_raw, c)
        adj = score + min(0.02, len(c) * 0.0005)
        if adj > best_score:
            best_score = adj
            best_name = n

    if best_score >= min_ratio and best_name != text:
        return best_name
    return text


def propose_name_fixes(
    name_type_pairs: Iterable[Tuple[str, str]],
    *,
    min_ratio: float = 0.78,
) -> List[Dict[str, str]]:
    """Return [{raw, fixed, item_type}] for (name, type) pairs that would change."""
    proposals: List[Dict[str, str]] = []
    seen = set()
    for raw, item_type in name_type_pairs:
        if not raw:
            continue
        kind = _normalize_item_type(item_type) or (item_type or "")
        key = (raw, kind)
        if key in seen:
            continue
        seen.add(key)
        fixed = resolve_item_name(raw, item_type=kind, min_ratio=min_ratio)
        if fixed and fixed != raw:
            proposals.append(
                {"raw": raw, "fixed": fixed, "item_type": kind or item_type or ""}
            )
    proposals.sort(key=lambda p: (p.get("item_type", ""), p["raw"].lower()))
    return proposals
