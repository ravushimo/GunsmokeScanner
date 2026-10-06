"""Fetch doll / weapon / event-banner names from Dandegate and merge into assets/gacha.

Uses the public JSON API behind https://dandegate.net/dolls and
https://dandegate.net/weapons (see https://api.dandegate.net/api).

Preserves curated `standard_elite` pools (50/50 loss roster) and Purchase Source
entries in banners.json. Event banners are written to event_banners.json.

Usage:
  python scripts/sync_gacha_catalog.py
  python scripts/sync_gacha_catalog.py --dry-run
  python scripts/sync_gacha_catalog.py --en-only
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
GACHA_DIR = ROOT / "assets" / "gacha"
API_BASE = "https://api.dandegate.net/api"
UA = {
    "User-Agent": "GunsmokeScanner-catalog-sync/1.0 (+https://github.com/ravushimo/GunsmokeScanner)",
    "Accept": "application/json",
}


def _get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e}") from e


def fetch_all(path: str, *, limit: int = 500) -> List[Dict[str, Any]]:
    """Fetch paginated `{success,data,pagination}` lists."""
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        payload = _get_json(path, {"page": page, "limit": limit})
        if isinstance(payload, list):
            return payload
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"Unexpected payload for {path}: {type(payload)}")
        out.extend(rows)
        pag = payload.get("pagination") or {}
        if not pag.get("hasNext"):
            break
        page += 1
        if page > 50:
            break
    return out


def _sorted_unique(names: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for n in names:
        name = (n or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    out.sort(key=lambda s: s.casefold())
    return out


def _keep_row(row: Dict[str, Any], *, en_only: bool) -> bool:
    if row.get("preview"):
        return False
    if en_only and (row.get("regionTag") or "en").lower() != "en":
        return False
    return True


def split_by_rarity(
    rows: Sequence[Dict[str, Any]], *, en_only: bool
) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {
        "Elite": [],
        "Standard": [],
        "Retired": [],
    }
    for row in rows:
        if not _keep_row(row, en_only=en_only):
            continue
        rarity = (row.get("rarity") or "").strip()
        name = (row.get("name") or "").strip()
        if rarity in buckets and name:
            buckets[rarity].append(name)
    return {k: _sorted_unique(v) for k, v in buckets.items()}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any], *, dry_run: bool) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"[dry-run] would write {path} ({len(text)} bytes)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}")


def diff_lists(old: Sequence[str], new: Sequence[str]) -> Tuple[List[str], List[str]]:
    old_set, new_set = set(old), set(new)
    added = sorted(new_set - old_set, key=str.casefold)
    removed = sorted(old_set - new_set, key=str.casefold)
    return added, removed


def merge_preserve(
    existing: Sequence[str], incoming: Sequence[str]
) -> Tuple[List[str], List[str]]:
    """Union existing + incoming (sorted). Returns (merged, newly_added)."""
    merged = _sorted_unique(list(existing) + list(incoming))
    added = sorted(set(merged) - set(existing), key=str.casefold)
    return merged, added


def sync_dolls(rows: List[Dict[str, Any]], *, en_only: bool, dry_run: bool) -> None:
    path = GACHA_DIR / "dolls.json"
    prev = load_json(path)
    by_r = split_by_rarity(rows, en_only=en_only)

    standard, add_std = merge_preserve(prev.get("standard") or [], by_r["Standard"])
    elite, add_elite = merge_preserve(prev.get("elite") or [], by_r["Elite"])
    # Curated 50/50 loss pool - never auto-replaced
    standard_elite = list(prev.get("standard_elite") or [])

    print(
        f"Dolls: standard {len(standard)} (+{len(add_std)}), "
        f"elite {len(elite)} (+{len(add_elite)}), "
        f"standard_elite kept {len(standard_elite)}"
    )
    if add_std:
        print("  +standard:", ", ".join(add_std))
    if add_elite:
        print("  +elite:", ", ".join(add_elite))

    data = {
        "version": int(prev.get("version") or 1),
        "description": (
            "Canonical doll names for OCR validation. "
            "`standard_elite` is the permanent 50/50-loss pool (manual). "
            "`elite` / `standard` are synced from Dandegate; portraits under "
            "assets/dolls/ are also merged at runtime."
        ),
        "source": "https://dandegate.net/dolls via https://api.dandegate.net/api/dolls",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "standard": standard,
        "elite": elite,
        "standard_elite": standard_elite,
    }
    write_json(path, data, dry_run=dry_run)


def sync_weapons(rows: List[Dict[str, Any]], *, en_only: bool, dry_run: bool) -> None:
    path = GACHA_DIR / "weapons.json"
    prev = load_json(path)
    by_r = split_by_rarity(rows, en_only=en_only)

    standard, add_std = merge_preserve(prev.get("standard") or [], by_r["Standard"])
    elite, add_elite = merge_preserve(prev.get("elite") or [], by_r["Elite"])
    retired, add_ret = merge_preserve(prev.get("retired") or [], by_r["Retired"])
    # Also ensure Retired {standard} aliases exist for OCR
    retired_aliases = [f"Retired {n}" for n in standard]
    retired, add_alias = merge_preserve(retired, retired_aliases)
    add_ret = _sorted_unique(add_ret + add_alias)

    standard_elite = list(prev.get("standard_elite") or [])
    named = list(prev.get("named") or [])

    print(
        f"Weapons: standard {len(standard)} (+{len(add_std)}), "
        f"elite {len(elite)} (+{len(add_elite)}), "
        f"retired {len(retired)} (+{len(add_ret)}), "
        f"standard_elite kept {len(standard_elite)}, named kept {len(named)}"
    )
    if add_std:
        print("  +standard:", ", ".join(add_std))
    if add_elite:
        shown = ", ".join(add_elite[:40])
        if len(add_elite) > 40:
            shown += f" ... (+{len(add_elite) - 40} more)"
        print("  +elite:", shown)
    if add_ret:
        print(f"  +retired: {len(add_ret)} names")

    data = {
        "version": int(prev.get("version") or 1),
        "description": (
            "Canonical weapon names for OCR validation (type-aware). "
            "`standard_elite` is the permanent 50/50-loss pool (manual). "
            "`elite` / `standard` / `retired` are synced from Dandegate."
        ),
        "source": "https://dandegate.net/weapons via https://api.dandegate.net/api/weapons",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "standard": standard,
        "elite": elite,
        "retired": retired,
        "standard_elite": standard_elite,
        "named": named,
    }
    write_json(path, data, dry_run=dry_run)


def sync_event_banners(rows: List[Dict[str, Any]], *, dry_run: bool) -> List[str]:
    """Write Dandegate event banners (not Access Records Purchase Sources)."""
    path = GACHA_DIR / "event_banners.json"
    featured: List[str] = []
    slim = []
    for row in rows:
        dolls = row.get("dolls") or []
        weapons = row.get("weapons") or []
        doll_names = [d.get("name") for d in dolls if d.get("name")]
        weapon_names = [w.get("name") for w in weapons if w.get("name")]
        featured.extend(doll_names)
        featured.extend(weapon_names)
        slim.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "startDate": row.get("startDate"),
                "endDate": row.get("endDate"),
                "dolls": doll_names,
                "weapons": weapon_names,
            }
        )
    data = {
        "version": 1,
        "description": (
            "Dandegate event banners (rate-up schedules). "
            "Not Access Records Purchase Source strings - those live in banners.json."
        ),
        "source": "https://dandegate.net via https://api.dandegate.net/api/banners",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "banners": slim,
    }
    write_json(path, data, dry_run=dry_run)
    return _sorted_unique(featured)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report diffs without writing files",
    )
    parser.add_argument(
        "--en-only",
        action="store_true",
        help="Skip CN-region / non-EN rows",
    )
    args = parser.parse_args(argv)

    print(f"Fetching from {API_BASE} …")
    dolls = fetch_all("/dolls")
    weapons = fetch_all("/weapons")
    banners = fetch_all("/banners", limit=100)
    print(f"Fetched dolls={len(dolls)} weapons={len(weapons)} event_banners={len(banners)}")

    sync_dolls(dolls, en_only=args.en_only, dry_run=args.dry_run)
    sync_weapons(weapons, en_only=args.en_only, dry_run=args.dry_run)
    featured = sync_event_banners(banners, dry_run=args.dry_run)

    # Fold featured event names into elite catalogs (OCR coverage for rate-ups)
    if featured and not args.dry_run:
        dolls_path = GACHA_DIR / "dolls.json"
        weapons_path = GACHA_DIR / "weapons.json"
        ddata = load_json(dolls_path)
        wdata = load_json(weapons_path)
        doll_names = set(ddata.get("elite") or []) | set(ddata.get("standard") or [])
        weapon_names = (
            set(wdata.get("elite") or [])
            | set(wdata.get("standard") or [])
            | set(wdata.get("retired") or [])
        )
        # Featured names that look like known dolls go to dolls elite; unknown stay out
        # (event payload separates dolls vs weapons fields already)
        # Re-read event file for typed lists
        edata = load_json(GACHA_DIR / "event_banners.json")
        feat_dolls: List[str] = []
        feat_weapons: List[str] = []
        for b in edata.get("banners") or []:
            feat_dolls.extend(b.get("dolls") or [])
            feat_weapons.extend(b.get("weapons") or [])
        d_elite, d_add = merge_preserve(ddata.get("elite") or [], feat_dolls)
        w_elite, w_add = merge_preserve(wdata.get("elite") or [], feat_weapons)
        if d_add or w_add:
            ddata["elite"] = d_elite
            wdata["elite"] = w_elite
            write_json(dolls_path, ddata, dry_run=False)
            write_json(weapons_path, wdata, dry_run=False)
            if d_add:
                print("  +elite from event dolls:", ", ".join(d_add))
            if w_add:
                print("  +elite from event weapons:", ", ".join(w_add))
        else:
            print("Event featured names already present in catalogs.")

    # Smoke-test: catalogs still load
    sys.path.insert(0, str(ROOT))
    from src.core.gacha_catalog import load_dolls, load_weapons
    from src.core.gacha_names import canonical_names_for_type

    load_dolls.cache_clear()
    load_weapons.cache_clear()
    canonical_names_for_type.cache_clear()
    d = load_dolls()
    w = load_weapons()
    print(
        "Load OK:",
        f"dolls standard={len(d.get('standard', ()))} elite={len(d.get('elite', ()))} "
        f"std_elite={len(d.get('standard_elite', ()))}; "
        f"weapons standard={len(w.get('standard', ()))} elite={len(w.get('elite', ()))} "
        f"retired={len(w.get('retired', ()))}"
    )
    if not args.dry_run:
        print(
            "Canonical catalogs:",
            f"Doll={len(canonical_names_for_type('Doll'))}",
            f"Weapons={len(canonical_names_for_type('Weapons'))}",
        )
    print("Done. Purchase Source banners remain in assets/gacha/banners.json (manual).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
