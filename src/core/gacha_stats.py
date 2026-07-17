"""Pull stats, Elite pity, 50/50, and premium-character campaigns."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.core.gacha_pool import is_standard_elite_doll, is_standard_elite_weapon
from src.core.gacha_scanner import clean_source

# Soft/hard pity: 80th pull on a banner guarantees an Elite of that pool's type.
ELITE_HARD_PITY = 80
# First copy = V0 … seventh copy = V6 (max).
MAX_COPIES = 7
# Worst V6: lose every 50/50 then hit hard pity on loss + guarantee → 80*2*7.
WORST_PULLS_PER_COPY = ELITE_HARD_PITY * 2
WORST_PULLS_V6 = WORST_PULLS_PER_COPY * MAX_COPIES  # 1120

BANNER_LABELS = {
    "Targeted Procurement": "Premium Doll",
    "Military Upgrade": "Premium Weapon",
    "Custom Procurement - Dolls": "Custom Dolls",
    "Custom Procurement - Weapons": "Custom Weapons",
    "Standard Procurement": "Standard",
}

DOLL_PITY_SOURCES = {
    "Targeted Procurement",
    "Custom Procurement - Dolls",
}
WEAPON_PITY_SOURCES = {
    "Military Upgrade",
    "Custom Procurement - Weapons",
}
STANDARD_SOURCE = "Standard Procurement"

# Premium banners that run a featured vs standard 50/50.
FIFTY_FIFTY_SOURCES = {
    "Targeted Procurement",
    "Military Upgrade",
}


def normalize_rarity(value: Optional[str]) -> str:
    v = (value or "").lower().strip()
    if v in ("elite", "gold"):
        return "elite"
    if v in ("standard", "purple"):
        return "standard"
    return "retired"


def normalize_source(value: Optional[str]) -> str:
    """Canonical banner name (handles OCR variants)."""
    return clean_source(value or "") or (value or "").strip()


def banner_label(source: str) -> str:
    src = normalize_source(source)
    return BANNER_LABELS.get(src, src or "Unknown")


def is_elite_doll(pull: Dict[str, Any]) -> bool:
    return (
        normalize_rarity(pull.get("rarity_color")) == "elite"
        and pull.get("item_type") == "Doll"
    )


def is_elite_weapon(pull: Dict[str, Any]) -> bool:
    return (
        normalize_rarity(pull.get("rarity_color")) == "elite"
        and pull.get("item_type") == "Weapons"
    )


def is_any_elite(pull: Dict[str, Any]) -> bool:
    return normalize_rarity(pull.get("rarity_color")) == "elite"


def is_standard_pool_elite(pull: Dict[str, Any]) -> bool:
    """True if this Elite is from the permanent 50/50-loss pool."""
    if is_elite_doll(pull):
        return is_standard_elite_doll(pull.get("item_name"))
    if is_elite_weapon(pull):
        return is_standard_elite_weapon(pull.get("item_name"))
    return False


def is_premium_elite(pull: Dict[str, Any]) -> bool:
    """Elite that is not in the permanent standard pool (rate-up / featured)."""
    if not is_any_elite(pull):
        return False
    if pull.get("item_type") == "Doll":
        return not is_standard_elite_doll(pull.get("item_name"))
    if pull.get("item_type") == "Weapons":
        return not is_standard_elite_weapon(pull.get("item_name"))
    return False


def annotate_pulls(pulls_oldest_first: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add pull_index, per-source pity, source_index, and 50/50 outcome.

    Pity is consecutive pulls within one Purchase Source only.
    50/50 applies only to Targeted Procurement (dolls) and Military Upgrade
    (weapons): standard-pool Elite = loss; other Elite = win (or guaranteed).
    """
    pity_by_source: Dict[str, int] = defaultdict(int)
    source_index: Dict[str, int] = defaultdict(int)
    guarantee_doll = False
    guarantee_weapon = False
    out: List[Dict[str, Any]] = []

    for i, raw in enumerate(pulls_oldest_first, start=1):
        p = dict(raw)
        src = normalize_source(p.get("purchase_source"))
        p["purchase_source"] = src
        p["pull_index"] = i
        p["rarity"] = normalize_rarity(p.get("rarity_color"))
        p["banner"] = banner_label(src)
        source_index[src] += 1
        p["source_index"] = source_index[src]

        pity_val = None
        pity_kind = None
        fifty = None
        pool = None

        if src in DOLL_PITY_SOURCES:
            pity_by_source[src] += 1
            pity_val = pity_by_source[src]
            pity_kind = "doll"
            if is_elite_doll(p):
                if is_standard_elite_doll(p.get("item_name")):
                    pool = "standard"
                else:
                    pool = "premium"
                if src in FIFTY_FIFTY_SOURCES:
                    if pool == "standard":
                        fifty = "loss"
                        guarantee_doll = True
                    elif guarantee_doll:
                        fifty = "guaranteed"
                        guarantee_doll = False
                    else:
                        fifty = "win"
                        guarantee_doll = False
                pity_by_source[src] = 0
        elif src in WEAPON_PITY_SOURCES:
            pity_by_source[src] += 1
            pity_val = pity_by_source[src]
            pity_kind = "weapon"
            if is_elite_weapon(p):
                if is_standard_elite_weapon(p.get("item_name")):
                    pool = "standard"
                else:
                    pool = "premium"
                if src in FIFTY_FIFTY_SOURCES:
                    if pool == "standard":
                        fifty = "loss"
                        guarantee_weapon = True
                    elif guarantee_weapon:
                        fifty = "guaranteed"
                        guarantee_weapon = False
                    else:
                        fifty = "win"
                        guarantee_weapon = False
                pity_by_source[src] = 0
        elif src == STANDARD_SOURCE:
            pity_by_source[src] += 1
            pity_val = pity_by_source[src]
            pity_kind = "standard"
            if is_any_elite(p):
                pity_by_source[src] = 0

        p["pity"] = pity_val
        p["pity_kind"] = pity_kind
        p["elite_pool"] = pool
        p["fifty_fifty"] = fifty
        out.append(p)

    return out


def current_pity_by_source(
    annotated_oldest_first: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Current pity remaining on each source after the newest pull."""
    pity_by_source: Dict[str, int] = defaultdict(int)
    for p in annotated_oldest_first:
        src = normalize_source(p.get("purchase_source"))
        if src in DOLL_PITY_SOURCES:
            pity_by_source[src] += 1
            if is_elite_doll(p):
                pity_by_source[src] = 0
        elif src in WEAPON_PITY_SOURCES:
            pity_by_source[src] += 1
            if is_elite_weapon(p):
                pity_by_source[src] = 0
        elif src == STANDARD_SOURCE:
            pity_by_source[src] += 1
            if is_any_elite(p):
                pity_by_source[src] = 0
    return dict(pity_by_source)


def compute_summary(annotated: List[Dict[str, Any]]) -> Dict[str, Any]:
    rarity_counts = Counter(p["rarity"] for p in annotated)
    elite_dolls = sum(1 for p in annotated if is_elite_doll(p))
    elite_weapons = sum(1 for p in annotated if is_elite_weapon(p))

    banner_counts = Counter(p["banner"] for p in annotated)
    pity_now = current_pity_by_source(annotated)

    doll_gaps: List[int] = []
    gap = 0
    for p in annotated:
        src = normalize_source(p.get("purchase_source"))
        if src != "Targeted Procurement":
            continue
        gap += 1
        if is_elite_doll(p):
            doll_gaps.append(gap)
            gap = 0

    avg_doll_gap = round(sum(doll_gaps) / len(doll_gaps), 1) if doll_gaps else None

    return {
        "total": len(annotated),
        "elite_dolls": elite_dolls,
        "elite_weapons": elite_weapons,
        "standard": rarity_counts.get("standard", 0),
        "retired": rarity_counts.get("retired", 0),
        "banners": dict(banner_counts),
        "pity_by_source": pity_now,
        "pity_doll": pity_now.get("Targeted Procurement", 0),
        "pity_weapon": pity_now.get("Military Upgrade", 0),
        "pity_custom_doll": pity_now.get("Custom Procurement - Dolls", 0),
        "pity_custom_weapon": pity_now.get("Custom Procurement - Weapons", 0),
        "pity_standard": pity_now.get(STANDARD_SOURCE, 0),
        "hard_pity": ELITE_HARD_PITY,
        "avg_elite_doll_gap": avg_doll_gap,
    }


def build_history(
    pulls_oldest_first: List[Dict[str, Any]],
    *,
    purchase_source: Optional[str] = None,
    item_type: Optional[str] = None,
    rarity: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Annotate full chronology with per-source pity, then filter for display."""
    annotated = annotate_pulls(list(pulls_oldest_first))

    pity_scope = annotated
    if purchase_source:
        want = normalize_source(purchase_source)
        pity_scope = [
            p for p in annotated if normalize_source(p.get("purchase_source")) == want
        ]
    summary = compute_summary(pity_scope)

    display = annotated
    if purchase_source:
        want = normalize_source(purchase_source)
        display = [
            p for p in display if normalize_source(p.get("purchase_source")) == want
        ]
    if item_type:
        display = [p for p in display if p.get("item_type") == item_type]
    if rarity:
        want_r = normalize_rarity(rarity)
        display = [p for p in display if p.get("rarity") == want_r]

    if item_type or rarity or purchase_source:
        vis = compute_summary(display)
        summary["total"] = vis["total"]
        summary["elite_dolls"] = vis["elite_dolls"]
        summary["elite_weapons"] = vis["elite_weapons"]
        summary["standard"] = vis["standard"]
        summary["retired"] = vis["retired"]
        summary["banners"] = vis["banners"]

    return list(reversed(display)), summary


def _campaign_for_name(
    source_pulls: List[Dict[str, Any]],
    name: str,
    *,
    item_type: str,
    source: str,
) -> Optional[Dict[str, Any]]:
    """Spend from first copy (including its pity) through last copy (≤ V6)."""
    copies = [
        p
        for p in source_pulls
        if p.get("item_name") == name
        and p.get("item_type") == item_type
        and p.get("rarity") == "elite"
        and p.get("elite_pool") == "premium"
    ]
    if not copies:
        return None

    first = copies[0]
    # Campaign completes at 7th copy (V6); extras beyond that are noted separately
    end_idx = min(len(copies), MAX_COPIES) - 1
    last = copies[end_idx]
    extras = max(0, len(copies) - MAX_COPIES)

    first_si = int(first["source_index"])
    last_si = int(last["source_index"])
    first_pity = int(first.get("pity") or 1)
    # pulls = (last - first) + pity_on_first  (includes pre-first pity pulls)
    pulls_spent = last_si - first_si + first_pity

    window_start = first_si - first_pity + 1
    window_end = last_si
    # Pulls attributed to each copy (V0…): includes 50/50 losses on the way
    copy_segments: List[int] = []
    prev_end = window_start - 1
    for c in copies[: end_idx + 1]:
        si = int(c["source_index"])
        copy_segments.append(si - prev_end)
        prev_end = si

    losses = 0
    wins = 0
    guaranteed = 0
    for p in source_pulls:
        si = int(p["source_index"])
        if si < window_start or si > window_end:
            continue
        ff = p.get("fifty_fifty")
        if ff == "loss":
            losses += 1
        elif ff == "win":
            wins += 1
        elif ff == "guaranteed":
            guaranteed += 1

    n = end_idx + 1
    return {
        "name": name,
        "item_type": item_type,
        "banner": banner_label(source),
        "purchase_source": source,
        "copies": n,
        "extras": extras,
        "potential": f"V{n - 1}" if n else "—",
        "complete": n >= MAX_COPIES,
        "pulls_spent": pulls_spent,
        "copy_segments": copy_segments,
        "first_pity": first_pity,
        "fifty_losses": losses,
        "fifty_wins": wins,
        "fifty_guaranteed": guaranteed,
        "luck_ratio": round(pulls_spent / WORST_PULLS_V6, 3),
        "first_time": first.get("purchase_time"),
        "last_time": last.get("purchase_time"),
        "first_index": first.get("pull_index"),
        "last_index": last.get("pull_index"),
    }


def compute_campaigns(annotated_oldest_first: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Premium character/weapon campaigns on Targeted / Military Upgrade."""
    campaigns: List[Dict[str, Any]] = []
    for source, item_type in (
        ("Targeted Procurement", "Doll"),
        ("Military Upgrade", "Weapons"),
    ):
        source_pulls = [
            p
            for p in annotated_oldest_first
            if normalize_source(p.get("purchase_source")) == source
        ]
        names: List[str] = []
        seen = set()
        for p in source_pulls:
            if (
                p.get("item_type") == item_type
                and p.get("rarity") == "elite"
                and p.get("elite_pool") == "premium"
            ):
                n = p.get("item_name") or ""
                if n and n not in seen:
                    seen.add(n)
                    names.append(n)
        for name in names:
            c = _campaign_for_name(
                source_pulls, name, item_type=item_type, source=source
            )
            if c:
                campaigns.append(c)

    campaigns.sort(key=lambda c: (-c["pulls_spent"], c["name"]))
    return campaigns


def compute_fifty_fifty_summary(
    annotated_oldest_first: List[Dict[str, Any]],
) -> Dict[str, Any]:
    by_banner: Dict[str, Dict[str, int]] = {}
    for src in FIFTY_FIFTY_SOURCES:
        label = banner_label(src)
        wins = losses = guaranteed = 0
        for p in annotated_oldest_first:
            if normalize_source(p.get("purchase_source")) != src:
                continue
            ff = p.get("fifty_fifty")
            if ff == "win":
                wins += 1
            elif ff == "loss":
                losses += 1
            elif ff == "guaranteed":
                guaranteed += 1
        decided = wins + losses
        by_banner[label] = {
            "wins": wins,
            "losses": losses,
            "guaranteed": guaranteed,
            "decided": decided,
            "win_rate": round(100.0 * wins / decided, 1) if decided else None,
        }

    # Guarantee status from newest pull backward is already in last state —
    # recompute quickly from full walk
    g_doll = False
    g_weap = False
    for p in annotated_oldest_first:
        src = normalize_source(p.get("purchase_source"))
        if src == "Targeted Procurement" and p.get("fifty_fifty"):
            g_doll = p["fifty_fifty"] == "loss"
        elif src == "Military Upgrade" and p.get("fifty_fifty"):
            g_weap = p["fifty_fifty"] == "loss"

    return {
        "by_banner": by_banner,
        "guarantee_premium_doll": g_doll,
        "guarantee_premium_weapon": g_weap,
    }


def build_stats_report(
    pulls_oldest_first: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Full stats payload for the Gacha Stats tab."""
    annotated = annotate_pulls(list(pulls_oldest_first))
    summary = compute_summary(annotated)
    campaigns = compute_campaigns(annotated)
    fifty = compute_fifty_fifty_summary(annotated)

    rarity = {
        "Elite": summary["elite_dolls"] + summary["elite_weapons"],
        "Standard": summary["standard"],
        "Retired": summary["retired"],
    }
    # Elite split for chart clarity
    elite_split = {
        "Elite Dolls": summary["elite_dolls"],
        "Elite Weapons": summary["elite_weapons"],
    }

    def _campaign_chart_rows(item_type: str) -> List[Dict[str, Any]]:
        rows = []
        for c in campaigns:
            if c["item_type"] != item_type:
                continue
            rows.append(
                {
                    "name": c["name"],
                    "total": c["pulls_spent"],
                    "segments": list(c.get("copy_segments") or []),
                    "copies": c["copies"],
                }
            )
        rows.sort(key=lambda r: -r["total"])
        return rows

    return {
        "summary": summary,
        "campaigns": campaigns,
        "fifty_fifty": fifty,
        "charts": {
            "by_banner": dict(summary.get("banners") or {}),
            "by_rarity": rarity,
            "elite_split": elite_split,
            "doll_campaigns": _campaign_chart_rows("Doll"),
            "weapon_campaigns": _campaign_chart_rows("Weapons"),
            "worst_pulls_v6": WORST_PULLS_V6,
        },
    }
