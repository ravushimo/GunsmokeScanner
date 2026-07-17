"""Access Records multi-page OCR scanner with auto page-turn."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pyautogui

from src.core.scanner import safe_grab
from src.data.gacha_db import GachaDB

TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})")
PAGE_RE = re.compile(r"\d+")

# OCR often mangles the trailing "×1" quantity into x1 / *1 / xt / x / etc.
_QTY_SUFFIX_PATTERNS = (
    re.compile(r"[\s]*[×xX*+][\s]*[lI1\|!]{1,2}\s*$"),  # ×1, x1, *1, xl, xI
    re.compile(r"[\s]*[×xX][tT]?\s*$"),  # lone x / xt (e.g. Alphaxt)
    re.compile(r"[\s]*[*+]\s*$"),
)

KNOWN_SOURCES = (
    "Targeted Procurement",
    "Military Upgrade",
    "Custom Procurement - Dolls",
    "Custom Procurement - Weapons",
    "Standard Procurement",
)

STATUS_CB = Optional[Callable[[str], None]]
PULL_CB = Optional[Callable[[Dict], None]]


def classify_rarity_color(img: np.ndarray) -> str:
    """Classify Name text color → elite | standard | retired.

    Averages only ink-like pixels so the light table background does not
    wash the tint out to gray.
    """
    if img is None or img.size == 0:
        return "retired"

    rgb = img[:, :, :3] if img.ndim == 3 else img
    h, w = rgb.shape[:2]
    y0, y1 = max(0, h // 6), max(1, 5 * h // 6)
    x0, x1 = max(0, w // 8), max(1, 7 * w // 8)
    crop = rgb[y0:y1, x0:x1]
    if crop.size == 0:
        crop = rgb

    lum = crop.mean(axis=2)
    sat = crop.max(axis=2) - crop.min(axis=2)
    # Drop near-white Access Records chrome
    ink = lum < 215
    colored = ink & (sat > 35)

    if int(colored.sum()) >= 15:
        pix = crop[colored]
    elif int(ink.sum()) >= 15:
        pix = crop[ink]
    else:
        return "retired"

    r, g, b = [float(v) for v in pix.mean(axis=0)]
    sat_mean = float((pix.max(axis=1) - pix.min(axis=1)).mean())

    # Elite — gold/orange (~237, 175, 82)
    if r > 170 and g > 110 and b < 150 and (r - b) > 50 and sat_mean > 40:
        return "elite"
    # Standard quality — purple (~180, 123, 231)
    if b > 150 and r > 100 and (b - g) > 35 and sat_mean > 40:
        return "standard"
    # Retired — gray text, low saturation
    return "retired"


def clean_timestamp(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("/", "-").replace(".", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    m = TIMESTAMP_RE.search(cleaned)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    loose = re.sub(r"[^\d:\-\s]", "", cleaned).strip()
    m2 = TIMESTAMP_RE.search(loose)
    return f"{m2.group(1)} {m2.group(2)}" if m2 else ""


def clean_item_name(text: str) -> str:
    """Strip trailing ×1 quantity junk that EasyOCR often mangles."""
    if not text:
        return ""
    name = text.strip()
    name = (
        name.replace("×", "x")
        .replace("✕", "x")
        .replace("х", "x")  # Cyrillic
        .replace("Х", "x")
    )
    for _ in range(4):
        prev = name
        for pat in _QTY_SUFFIX_PATTERNS:
            name = pat.sub("", name)
        name = re.sub(r"[\s_\-.,;:|]+$", "", name)
        if name == prev:
            break
    return re.sub(r"\s+", " ", name).strip()


def _source_key(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text).lower()


def clean_source(text: str) -> str:
    """Normalize OCR banner names to canonical Purchase Source strings."""
    if not text:
        return ""
    t = re.sub(r"[\s_]+", " ", text.strip())
    t = t.rstrip("-.,;:| ")
    key = _source_key(t)

    for known in KNOWN_SOURCES:
        known_key = _source_key(known)
        if key == known_key or key.startswith(known_key):
            return known

    # Fuzzy Custom Procurement — OCR often mangles "Custom"/"Procurement"
    # e.g. Custm / Custon / Procurenent, with spaces, hyphens, or underscores.
    if "weapon" in key:
        if key.startswith("cust") or "procur" in key:
            return "Custom Procurement - Weapons"
    if "doll" in key:
        if key.startswith("cust") or "procur" in key:
            return "Custom Procurement - Dolls"

    # Soft prefixes for other banners
    if "targeted" in key or key.startswith("target"):
        return "Targeted Procurement"
    if "military" in key or "upgrade" in key:
        return "Military Upgrade"
    if "standard" in key:
        return "Standard Procurement"

    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    return spaced.rstrip("-.,;:| ").strip()


def clean_type(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text.strip())
    lower = t.lower()
    if "weapon" in lower:
        return "Weapons"
    if "doll" in lower:
        return "Doll"
    return t


def parse_page_number(text: str) -> Optional[int]:
    if not text:
        return None
    m = PAGE_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def bbox_center(bbox) -> Tuple[int, int]:
    x, y, w, h = bbox
    return x + w // 2, y + h // 2


class GachaScanner:
    def __init__(self, config_manager, ocr_processor, db: Optional[GachaDB] = None):
        self.config_manager = config_manager
        self.ocr = ocr_processor
        self.db = db or GachaDB()
        self._stop = False

    def request_stop(self):
        self._stop = True

    def _ocr_config(self) -> dict:
        gacha = self.config_manager.get_gacha()
        base = dict(self.config_manager.config)
        prep = gacha.get("preprocessing") or base.get("preprocessing") or {}
        base["preprocessing"] = prep
        return base

    def _delays(self) -> Tuple[float, float]:
        gacha = self.config_manager.get_gacha()
        click_ms = int(gacha.get("click_delay_ms", 150))
        settle_ms = int(gacha.get("ocr_settle_ms", 100))
        return click_ms / 1000.0, settle_ms / 1000.0

    def _status(self, cb: STATUS_CB, msg: str):
        if cb:
            cb(msg)

    def read_page_number(self) -> Optional[int]:
        gacha = self.config_manager.get_gacha()
        img = safe_grab(gacha["page_number"])
        text = self.ocr.extract_text(
            img,
            is_number=True,
            config=self._ocr_config(),
            allowlist="0123456789",
        )
        return parse_page_number(text)

    def click_bbox(self, key: str):
        gacha = self.config_manager.get_gacha()
        cx, cy = bbox_center(gacha[key])
        pyautogui.click(cx, cy)

    def go_to_page_one(self, status_cb: STATUS_CB = None, max_clicks: int = 200) -> bool:
        """Click Prev until page OCR reads 1. Returns False if aborted/failed."""
        click_delay, settle = self._delays()
        page = self.read_page_number()
        self._status(status_cb, f"Current page: {page if page is not None else '?'}")

        clicks = 0
        while page is not None and page != 1 and clicks < max_clicks:
            if self._stop:
                return False
            prev = page
            self.click_bbox("btn_prev")
            time.sleep(click_delay)
            time.sleep(settle)
            page = self.read_page_number()
            clicks += 1
            self._status(status_cb, f"Going to page 1… now {page}")
            if page == prev:
                break

        final = self.read_page_number()
        return final == 1 or final is None

    def scan_current_page(
        self, ordinals: Optional[Dict[Tuple[str, str], int]] = None
    ) -> List[Dict]:
        """OCR all 6 rows on the current Access Records page."""
        if ordinals is None:
            ordinals = defaultdict(int)

        gacha = self.config_manager.get_gacha()
        cfg = self._ocr_config()
        pulls: List[Dict] = []

        for row in gacha.get("rows", []):
            time_img = safe_grab(row["purchase_time"])
            source_img = safe_grab(row["purchase_source"])
            type_img = safe_grab(row["type"])
            name_img = safe_grab(row["name"])

            raw_time = self.ocr.extract_text(
                time_img,
                config=cfg,
                allowlist="0123456789-: ",
            )
            raw_source = self.ocr.extract_text(source_img, config=cfg)
            raw_type = self.ocr.extract_text(type_img, config=cfg)
            raw_name = self.ocr.extract_text(name_img, config=cfg)

            purchase_time = clean_timestamp(raw_time)
            purchase_source = clean_source(raw_source)
            item_type = clean_type(raw_type)
            item_name = clean_item_name(raw_name)

            if not purchase_time or not item_name:
                continue

            key = (purchase_time, item_name)
            ordinal = ordinals[key]
            ordinals[key] = ordinal + 1

            rarity = classify_rarity_color(name_img)
            pulls.append(
                {
                    "purchase_time": purchase_time,
                    "purchase_source": purchase_source or "Unknown",
                    "item_type": item_type or "Unknown",
                    "item_name": item_name,
                    "ordinal": ordinal,
                    "rarity_color": rarity,
                }
            )

        return pulls

    def scan_all_pages(
        self,
        status_cb: STATUS_CB = None,
        on_pull: PULL_CB = None,
        max_pages: int = 500,
    ) -> Dict:
        """
        Reset to page 1, scan each page (newest → oldest), click Next until
        stuck/empty, or until a full page of pulls is already in the DB
        (incremental catch-up after the first full history scan).

        Returns summary dict with inserted/skipped/pages/pulls/caught_up.
        """
        self._stop = False
        click_delay, settle = self._delays()
        ordinals: Dict[Tuple[str, str], int] = defaultdict(int)
        session_pulls: List[Dict] = []
        inserted_total = 0
        skipped_total = 0
        caught_up = False

        self._status(status_cb, "Resetting to page 1…")
        self.go_to_page_one(status_cb=status_cb)
        time.sleep(settle)

        pages_scanned = 0
        prev_page: Optional[int] = None

        while pages_scanned < max_pages:
            if self._stop:
                self._status(status_cb, "Scan stopped.")
                break

            page = self.read_page_number()
            self._status(
                status_cb,
                f"Scanning page {page if page is not None else pages_scanned + 1}…",
            )

            page_pulls = self.scan_current_page(ordinals)
            if not page_pulls:
                self._status(status_cb, "Empty page — finished.")
                break

            ins, known = self.db.insert_pulls(page_pulls)
            inserted_total += ins
            skipped_total += known
            for p in page_pulls:
                session_pulls.append(p)
                if on_pull:
                    on_pull(p)

            pages_scanned += 1
            prev_page = page

            # Records are newest→oldest. A 10-pull often spans pages, e.g.
            # page 1: 6 new, page 2: 4 new + 2 already known. Once we see any
            # known pull on a page (after saving that page's new ones), every
            # older page is already in the DB — stop without walking history.
            if known > 0:
                caught_up = True
                self._status(
                    status_cb,
                    f"Caught up — hit {known} known pull(s) on this page. "
                    f"New this run: {inserted_total}.",
                )
                break

            if self._stop:
                break

            self.click_bbox("btn_next")
            time.sleep(click_delay)
            time.sleep(settle)

            new_page = self.read_page_number()
            if new_page is not None and prev_page is not None and new_page == prev_page:
                self._status(status_cb, "Next page unchanged — finished.")
                break
            if new_page is not None and prev_page is not None and new_page < prev_page:
                self._status(status_cb, "Page did not advance — finished.")
                break

        if not caught_up and not self._stop:
            self._status(
                status_cb,
                f"Done. Pages {pages_scanned}, "
                f"saved {inserted_total}, known {skipped_total}.",
            )
        return {
            "pages": pages_scanned,
            "inserted": inserted_total,
            "skipped": skipped_total,
            "caught_up": caught_up,
            "stopped": self._stop,
            "pulls": session_pulls,
        }
