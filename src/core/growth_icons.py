"""Template-match Growth Data icons (IOP Wiki inventory art).

Wiki PNGs are 256×256 inventory glyphs on black/transparent backgrounds.
They match the **grid tile** art, not a random detail-panel crop of UI chrome.
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

_RARITY = {"alpha": "α", "beta": "β", "gamma": "γ"}

_FAMILY_TYPE = {
    "Root": "Bulwark",
    "Stem": "Vanguard",
    "Leaf": "Support",
    "Bloom": "Sentinel",
    "Blossom": "Sentinel",
    "Flameflower": "Sentinel",
}

# Absolute floor; a clear winner can accept slightly lower than classic 0.55
_MIN_SCORE = 0.42
_MIN_MARGIN = 0.05


def icons_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "growth" / "icons"
    return Path(__file__).resolve().parents[2] / "assets" / "growth" / "icons"


def icon_key_to_label(key: str) -> str:
    """Marrow_Root_gamma -> Marrow Root γ"""
    base = key
    if base.lower().endswith(".png"):
        base = base[:-4]
    m = re.match(r"^(.+)_(alpha|beta|gamma)$", base, re.I)
    if not m:
        return base.replace("_", " ").replace("-", " ")
    stem, rarity = m.group(1), m.group(2).lower()
    pretty = stem.replace("_", " ").replace("-", " ")
    return f"{pretty} {_RARITY.get(rarity, rarity)}"


def icon_key_to_type(key: str) -> Optional[str]:
    label = icon_key_to_label(key)
    for token, ctype in _FAMILY_TYPE.items():
        if token.lower() in label.lower() or token.lower() in key.lower():
            return ctype
    return None


def _fg_mask_bgr(bgr: np.ndarray) -> np.ndarray:
    """Foreground mask: drop near-black wiki backgrounds."""
    if bgr.ndim != 3:
        return np.ones(bgr.shape[:2], dtype=np.uint8) * 255
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Near-black / near-zero value
    black = cv2.inRange(
        hsv,
        np.array([0, 0, 0], dtype=np.uint8),
        np.array([180, 255, 28], dtype=np.uint8),
    )
    mask = cv2.bitwise_not(black)
    # Small clean-up
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def _crop_to_mask(bgr: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        return bgr, mask
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    pad = 2
    h, w = bgr.shape[:2]
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w, x1 + pad)
    y1 = min(h, y1 + pad)
    return bgr[y0:y1, x0:x1], mask[y0:y1, x0:x1]


@lru_cache(maxsize=1)
def load_icon_templates() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Return {icon_key: (BGR crop, uint8 mask)}."""
    root = icons_dir()
    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.png")):
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None or img.size == 0:
            continue
        if img.ndim == 2:
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            mask = _fg_mask_bgr(bgr)
        elif img.shape[2] == 4:
            bgr = img[:, :, :3]
            alpha = img[:, :, 3]
            mask = ((alpha > 16).astype(np.uint8)) * 255
            # Also drop residual black inside opaque area
            mask = cv2.bitwise_and(mask, _fg_mask_bgr(bgr))
        else:
            bgr = img[:, :, :3]
            mask = _fg_mask_bgr(bgr)
        bgr, mask = _crop_to_mask(bgr, mask)
        if mask.sum() < 64:
            continue
        out[path.stem] = (bgr, mask)
    return out


def _to_bgr(screen_bgr_or_rgb: np.ndarray) -> np.ndarray:
    img = screen_bgr_or_rgb
    if img.ndim == 3 and img.shape[2] >= 3:
        # safe_grab is RGB
        return cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2BGR)
    return img


def _hist_score(a_bgr: np.ndarray, b_bgr: np.ndarray, a_mask: np.ndarray) -> float:
    """HSV histogram correlation on masked template vs full screen crop."""
    a_hsv = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2HSV)
    b_hsv = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2HSV)
    # Soft mask on screen: ignore very dark UI chrome
    b_mask = _fg_mask_bgr(b_bgr)
    hist_a = cv2.calcHist([a_hsv], [0, 1], a_mask, [18, 16], [0, 180, 0, 256])
    hist_b = cv2.calcHist([b_hsv], [0, 1], b_mask, [18, 16], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    return float(max(0.0, score))


def _template_score(
    gray: np.ndarray,
    tmpl_gray: np.ndarray,
    mask: np.ndarray,
) -> float:
    th, tw = tmpl_gray.shape[:2]
    gh, gw = gray.shape[:2]
    if th >= gh or tw >= gw or th < 8 or tw < 8:
        return 0.0
    try:
        # Masked CCORR is stable for transparent/black-bg wiki glyphs
        res = cv2.matchTemplate(gray, tmpl_gray, cv2.TM_CCORR_NORMED, mask=mask)
    except cv2.error:
        res = cv2.matchTemplate(gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    _min_v, max_v, _min_l, _max_l = cv2.minMaxLoc(res)
    return float(max_v)


def rank_icons(
    screen_bgr_or_rgb: np.ndarray,
    *,
    top_n: int = 5,
) -> List[Tuple[str, float]]:
    """Return top (icon_key, score) candidates, best first."""
    templates = load_icon_templates()
    if not templates or screen_bgr_or_rgb is None or screen_bgr_or_rgb.size == 0:
        return []

    bgr = _to_bgr(screen_bgr_or_rgb)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gh, gw = gray.shape[:2]
    if gh < 16 or gw < 16:
        return []

    # Slight blur reduces specular noise from in-game lighting
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    scores: List[Tuple[str, float]] = []
    # Scales relative to fitting the template inside the crop
    scale_factors = (0.55, 0.65, 0.75, 0.85, 0.92, 1.0)

    for key, (tmpl_bgr, mask) in templates.items():
        th0, tw0 = tmpl_bgr.shape[:2]
        fit = min(gw / max(tw0, 1), gh / max(th0, 1))
        best = 0.0
        for sf in scale_factors:
            scale = fit * sf
            nw, nh = max(12, int(tw0 * scale)), max(12, int(th0 * scale))
            if nw >= gw - 1 or nh >= gh - 1:
                continue
            tmpl_r = cv2.resize(tmpl_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
            mask_r = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
            if mask_r.max() == 0:
                continue
            tgray = cv2.cvtColor(tmpl_r, cv2.COLOR_BGR2GRAY)
            tgray = cv2.GaussianBlur(tgray, (3, 3), 0)
            t_score = _template_score(gray, tgray, mask_r)
            h_score = _hist_score(tmpl_r, bgr, mask_r)
            # Template dominates; hist breaks ties / rejects wrong family colors
            combined = 0.72 * t_score + 0.28 * h_score
            if combined > best:
                best = combined
        scores.append((key, best))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]


def match_icon(
    screen_bgr_or_rgb: np.ndarray,
    *,
    min_score: float = _MIN_SCORE,
    min_margin: float = _MIN_MARGIN,
) -> Tuple[Optional[str], float]:
    """Match a captured icon crop against wiki templates.

    Accepts RGB (from safe_grab) or BGR. Returns (icon_key, score).
    Accepts a slightly lower score when the winner beats #2 by ``min_margin``.
    """
    ranked = rank_icons(screen_bgr_or_rgb, top_n=3)
    if not ranked:
        return None, 0.0
    best_key, best_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second
    if best_score >= 0.55 or (best_score >= min_score and margin >= min_margin):
        return best_key, best_score
    return None, best_score


def list_icon_labels() -> List[str]:
    return [icon_key_to_label(k) for k in sorted(load_icon_templates().keys())]
