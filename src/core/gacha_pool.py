"""Standard Elite pool (50/50 loss) vs premium rate-up Elites."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import FrozenSet, Optional

from src.core.gacha_catalog import load_dolls, load_weapons

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@lru_cache(maxsize=1)
def _standard_elite_dolls() -> FrozenSet[str]:
    names = load_dolls()["standard_elite"]
    keys = set()
    for n in names:
        k = normalize_item_key(n)
        keys.add(k)
        keys.add(k.replace("-", " "))
    return frozenset(keys)


@lru_cache(maxsize=1)
def _standard_elite_weapons() -> FrozenSet[str]:
    return frozenset(normalize_item_key(n) for n in load_weapons()["standard_elite"])


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
    pool = _standard_elite_dolls()
    if key in pool:
        return True
    compact = _compact(key)
    return any(_compact(s) == compact for s in pool)


def is_standard_elite_weapon(name: Optional[str]) -> bool:
    key = normalize_item_key(name)
    pool = _standard_elite_weapons()
    if key in pool:
        return True
    compact = _compact(key)
    return any(_compact(s) == compact for s in pool)


# Lazy frozensets for any external imports of the old constants
def __getattr__(name: str):
    if name == "STANDARD_ELITE_DOLLS":
        return _standard_elite_dolls()
    if name == "STANDARD_ELITE_WEAPONS":
        return _standard_elite_weapons()
    raise AttributeError(name)
