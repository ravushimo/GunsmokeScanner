"""Growth Data catalog + fuzzy OCR repair for prefix / suffix / perks."""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_GREEK_SUFFIX = re.compile(
    r"[\s]*[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩYy]+$"
)
# Middle-dot and common OCR stand-ins (period between words, bullet, etc.)
_MIDDLE_DOT = re.compile(r"[·•⋅·∙\u00b7]|(\s|^)\.(\s|$)")
_MIDDLE_DOT_SPLIT = re.compile(r"\s*[·•⋅·∙\u00b7]\s*")

CORE_TYPES = ("Bulwark", "Sentinel", "Vanguard", "Support")


def clean_name_ocr(raw: str) -> str:
    """Strip Storeroom chrome (INFO…//, Name label) before splitting."""
    text = raw or ""
    text = text.replace("◢", " ").replace("▶", " ").replace("►", " ")
    # INFO chrome (spaced or glued to the title)
    text = re.sub(r"(?i)\bINFO\b", " ", text)
    text = re.sub(r"(?i)INFO(?=[A-Za-z])", " ", text)
    text = re.sub(r"\.{2,}", " ", text)
    text = re.sub(r"/{1,}", " ", text)
    text = re.sub(r"(?i)\bName\b", " ", text)
    text = re.sub(r"(?i)\bLock\b", " ", text)
    text = text.replace("|", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip(" :|-.…")
    return text

def catalog_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "growth" / "catalog.json"
    return Path(__file__).resolve().parents[2] / "assets" / "growth" / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    path = catalog_path()
    if not path.is_file():
        return {"prefixes": [], "suffixes": [], "perks": [], "pairs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"prefixes": [], "suffixes": [], "perks": [], "pairs": []}


def normalize_key(text: str) -> str:
    t = (text or "").strip().lower()
    t = _GREEK_SUFFIX.sub("", t)
    t = _NON_ALNUM.sub("", t)
    return t


def _best_match(
    raw: str, candidates: Sequence[str], *, min_ratio: float = 0.72
) -> Tuple[Optional[str], float]:
    key = normalize_key(raw)
    if not key or not candidates:
        return None, 0.0

    exact = {normalize_key(c): c for c in candidates}
    if key in exact:
        return exact[key], 1.0

    best_name = None
    best_score = 0.0
    for cand in candidates:
        ck = normalize_key(cand)
        if not ck:
            continue
        if key in ck or ck in key:
            score = max(len(key), len(ck)) / max(len(key), len(ck), 1)
            score = min(0.95, 0.85 + 0.1 * score)
        else:
            score = SequenceMatcher(None, key, ck).ratio()
        if score > best_score:
            best_score = score
            best_name = cand

    if best_score >= min_ratio:
        return best_name, best_score
    return None, best_score


def split_core_name(raw: str) -> Tuple[str, str]:
    """Split OCR name into prefix / suffix on middle-dot (with fallbacks)."""
    text = clean_name_ocr(raw)
    if not text:
        return "", ""

    # Prefer a line/segment that contains a middle-dot
    candidates = [text]
    for part in re.split(r"[\n\r]+", raw or ""):
        cleaned = clean_name_ocr(part)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    best = ""
    for cand in candidates:
        if _MIDDLE_DOT_SPLIT.search(cand) or "·" in cand:
            best = cand
            break
        if len(cand) > len(best):
            best = cand
    text = best or text

    parts = _MIDDLE_DOT_SPLIT.split(text, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        left = clean_name_ocr(parts[0])
        right = _GREEK_SUFFIX.sub("", clean_name_ocr(parts[1])).strip()
        if left and right:
            return left, right

    # OCR sometimes uses a lone "." between words: "Antivenom . Sanguine Root"
    m = re.search(r"^(.+?)\s+[.\-–—]\s+(.+)$", text)
    if m:
        left, right = clean_name_ocr(m.group(1)), clean_name_ocr(m.group(2))
        right = _GREEK_SUFFIX.sub("", right).strip()
        if left and right and len(left) >= 3 and len(right) >= 3:
            return left, right

    # Fallback: longest catalog prefix match anywhere near the start
    cat = load_catalog()
    prefixes = sorted(cat.get("prefixes") or [], key=len, reverse=True)
    flat = normalize_key(text)
    for pref in prefixes:
        pk = normalize_key(pref)
        if not pk:
            continue
        idx = flat.find(pk)
        if idx == 0 or (0 <= idx <= 6):  # allow short INFO leftovers before name
            # Map back roughly via cleaned text start
            rest_key = flat[idx + len(pk) :]
            if not rest_key:
                continue
            # Prefer matching a known suffix on the remainder
            suffixes = sorted(cat.get("suffixes") or [], key=len, reverse=True)
            for suf in suffixes:
                sk = normalize_key(suf)
                if sk and sk in rest_key:
                    return pref, suf
            # Take remainder as suffix blob
            # Reconstruct from original by stripping prefix match length heuristically
            approx = text
            for junk in ("INFO", "Name", "//"):
                approx = re.sub(rf"(?i){re.escape(junk)}", "", approx)
            approx = clean_name_ocr(approx)
            if approx.lower().startswith(pref.lower()):
                rest = approx[len(pref) :].strip(" ·•.-")
            else:
                rest = approx
            rest = _GREEK_SUFFIX.sub("", rest).strip()
            if rest:
                return pref, rest
    return "", ""


def clean_name_part(raw: str) -> str:
    """Normalize a prefix/suffix for storage when catalog has no match."""
    text = " ".join((raw or "").split())
    text = _GREEK_SUFFIX.sub("", text).strip()
    return text


def resolve_prefix(raw: str) -> Tuple[Optional[str], float]:
    """Fuzzy catalog match; falls back to cleaned OCR (new prefixes allowed)."""
    matched, score = _best_match(raw, load_catalog().get("prefixes") or [])
    if matched:
        return matched, score
    cleaned = clean_name_part(raw)
    return (cleaned, 0.0) if cleaned else (None, score)


def resolve_suffix(raw: str) -> Tuple[Optional[str], float]:
    """Fuzzy catalog match; falls back to cleaned OCR (new suffixes/pairs allowed)."""
    cleaned = clean_name_part(raw)
    matched, score = _best_match(cleaned, load_catalog().get("suffixes") or [])
    if matched:
        return matched, score
    return (cleaned, 0.0) if cleaned else (None, score)


def resolve_perk(raw: str) -> Tuple[Optional[str], float, Optional[str]]:
    """Return (name, score, type)."""
    perks = load_catalog().get("perks") or []
    names = [p["name"] for p in perks if p.get("name")]
    name, score = _best_match(raw, names)
    if not name:
        return None, score, None
    ptype = next((p.get("type") for p in perks if p.get("name") == name), None)
    return name, score, ptype


def parse_type_line(raw: str) -> Optional[str]:
    text = (raw or "").strip()
    flat = normalize_key(text)
    for t in CORE_TYPES:
        if normalize_key(t) in flat:
            return t
    m = re.search(
        r"(?i)suitable\s*for\s*(bulwark|sentinel|vanguard|support)",
        text,
    )
    if m:
        word = m.group(1).lower()
        return next(t for t in CORE_TYPES if t.lower() == word)
    return None


def parse_perks_from_text(raw: str) -> List[Dict]:
    """Extract up to 3 perks as {name, level, score, type} from OCR blob."""
    text = raw or ""
    matches = list(re.finditer(r"(?i)Lv\.?\s*([123])", text))
    found: List[Dict] = []
    for i, m in enumerate(matches):
        level = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        chunk = re.sub(r"\s+", " ", chunk).strip(" :|-")
        # Trim trailing UI junk
        chunk = re.split(r"(?i)\bLv\.?\s*[123]\b", chunk)[0].strip()
        if len(chunk) > 48:
            chunk = chunk[:48]
        name, score, ptype = resolve_perk(chunk)
        if name:
            found.append(
                {"name": name, "level": level, "score": score, "type": ptype}
            )
        if len(found) >= 3:
            break
    return found
