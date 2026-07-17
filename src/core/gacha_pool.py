"""Standard Elite pool (50/50 loss) vs premium rate-up Elites."""

from __future__ import annotations

import re
from typing import FrozenSet, Optional

# Permanent / standard Elite Dolls shown on premium doll banner details.
STANDARD_ELITE_DOLLS: FrozenSet[str] = frozenset(
    {
        "vepley",
        "peritya",
        "tololo",
        "qiongjiu",
        "sabrina",
        "mosin-nagant",
        "mosin nagant",
        "faye",
        "harpsy",
    }
)

# Permanent / standard Elite Weapons on premium weapon banner details.
STANDARD_ELITE_WEAPONS: FrozenSet[str] = frozenset(
    {
        "heart seeker",
        "optical illusion",
        "planeta",
        "golden melody",
        "mezzaluna",
        "samosek",
        "hestia",
        "antimony",
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_item_key(name: Optional[str]) -> str:
    """Lowercase name for pool membership (keeps spaces/hyphens lightly)."""
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("×", "x")
    # Drop trailing "x1" / "×1" OCR leftovers if any slipped through
    s = re.sub(r"\s*x\s*1\s*$", "", s)
    return s


def _compact(name: str) -> str:
    return _NON_ALNUM.sub("", name)


def is_standard_elite_doll(name: Optional[str]) -> bool:
    key = normalize_item_key(name)
    if key in STANDARD_ELITE_DOLLS:
        return True
    compact = _compact(key)
    return any(_compact(s) == compact for s in STANDARD_ELITE_DOLLS)


def is_standard_elite_weapon(name: Optional[str]) -> bool:
    key = normalize_item_key(name)
    if key in STANDARD_ELITE_WEAPONS:
        return True
    compact = _compact(key)
    return any(_compact(s) == compact for s in STANDARD_ELITE_WEAPONS)
