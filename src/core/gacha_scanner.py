"""Access Records multi-page OCR scanner with auto page-turn."""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pyautogui
from PIL import Image

from src.core.scanner import safe_grab
from src.data.gacha_db import GachaDB

DEBUG_LOG = os.path.join("data", "gacha_scan_debug.log")
DEBUG_CROPS = os.path.join("data", "gacha_debug")

TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
# OCR often drops one colon: 09:1646 (09:16:46) or 0916:46.
_TIME_FULL_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})")
_TIME_MISS_SEC_RE = re.compile(r"(\d{2}):(\d{2})(\d{2})")
_TIME_MISS_MIN_RE = re.compile(r"(\d{2})(\d{2}):(\d{2})")
PAGE_RE = re.compile(r"\d+")

# OCR often mangles the trailing "×1" quantity into x1 / *1 / xt / x7 / etc.
_QTY_SUFFIX_PATTERNS = (
    re.compile(r"[\s]*[×xX*+][\s]*[lI17\|!]{1,2}\s*$"),  # ×1, x1, *1, x7, xl
    re.compile(r"[\s]*[×xX][tT]?\s*$"),  # lone x / xt (e.g. Alphaxt)
    re.compile(r"[\s]*[*+]\s*$"),
)

# Populated from assets/gacha/banners.json (includes Reunion Procurement).
def _known_sources() -> tuple:
    from src.core.gacha_catalog import known_sources

    return known_sources()


# Back-compat for imports that expect a tuple constant
KNOWN_SOURCES = (
    "Targeted Procurement",
    "Military Upgrade",
    "Custom Procurement - Dolls",
    "Custom Procurement - Weapons",
    "Reunion Procurement - Doll",
    "Reunion Procurement - Weapon",
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

    # Elite - gold/orange (~237, 175, 82)
    if r > 170 and g > 110 and b < 150 and (r - b) > 50 and sat_mean > 40:
        return "elite"
    # Standard quality - purple (~180, 123, 231)
    if b > 150 and r > 100 and (b - g) > 35 and sat_mean > 40:
        return "standard"
    # Retired - gray text, low saturation
    return "retired"


def _format_hms(h: str, m: str, s: str) -> Optional[str]:
    try:
        hh, mm, ss = int(h), int(m), int(s)
    except ValueError:
        return None
    if 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return None


def timestamp_is_strict(text: str) -> bool:
    """True when OCR already has YYYY-MM-DD HH:MM:SS with both clock colons."""
    if not text:
        return False
    cleaned = text.replace("/", "-").replace(".", "-")
    return TIMESTAMP_RE.search(cleaned) is not None


def clean_timestamp(text: str) -> str:
    """Normalize OCR clock text to YYYY-MM-DD HH:MM:SS.

    OCR often drops a colon: 2220:00, 06:0906, 09:1646, or 222000.
    """
    if not text:
        return ""
    cleaned = text.replace("/", "-").replace(".", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    m = TIMESTAMP_RE.search(cleaned)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    loose = re.sub(r"[^\d:\-\s]", "", cleaned).strip()
    dm = _DATE_RE.search(loose)
    if not dm:
        return ""
    date = dm.group(1)
    rest = loose[dm.end() :]
    for pat in (_TIME_FULL_RE, _TIME_MISS_SEC_RE, _TIME_MISS_MIN_RE):
        tm = pat.search(rest)
        if not tm:
            continue
        clock = _format_hms(*tm.groups())
        if clock:
            return f"{date} {clock}"
    digits = re.sub(r"\D", "", rest)
    if len(digits) >= 6:
        clock = _format_hms(digits[0:2], digits[2:4], digits[4:6])
        if clock:
            return f"{date} {clock}"
    return ""


def clean_item_name(text: str, item_type: Optional[str] = None) -> str:
    """Strip trailing ×1 quantity junk and fuzzy-match known names for item_type."""
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
    name = re.sub(r"\s+", " ", name).strip()
    from src.core.gacha_names import resolve_item_name

    return resolve_item_name(name, item_type=item_type)


def _source_key(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text).lower()


def clean_source(text: str) -> str:
    """Normalize OCR banner names to canonical Purchase Source strings."""
    if not text:
        return ""
    t = re.sub(r"[\s_]+", " ", text.strip())
    t = t.rstrip("-.,;:| ")
    key = _source_key(t)

    sources = _known_sources() or KNOWN_SOURCES
    for known in sources:
        known_key = _source_key(known)
        if key == known_key or key.startswith(known_key):
            return known

    # Reunion BEFORE Custom - both contain "procur"; Reunion must not collapse
    # into Custom Procurement.
    if "reunion" in key:
        if "weapon" in key:
            return "Reunion Procurement - Weapon"
        if "doll" in key:
            return "Reunion Procurement - Doll"

    # Fuzzy Custom Procurement - OCR often mangles "Custom"/"Procurement"
    # e.g. Custm / Custon / Procurenent, with spaces, hyphens, or underscores.
    if "reunion" not in key:
        if "weapon" in key and (key.startswith("cust") or "procur" in key):
            return "Custom Procurement - Weapons"
        if "doll" in key and (key.startswith("cust") or "procur" in key):
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

    def _dbg(self, msg: str):
        os.makedirs(os.path.dirname(DEBUG_LOG) or ".", exist_ok=True)
        line = f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}"
        try:
            with open(DEBUG_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        print(f"Gacha {msg}", flush=True)

    def _start_debug_log(self):
        os.makedirs(os.path.dirname(DEBUG_LOG) or ".", exist_ok=True)
        with open(DEBUG_LOG, "w", encoding="utf-8") as f:
            f.write(f"=== gacha scan {datetime.now().isoformat(timespec='seconds')} ===\n")

    @staticmethod
    def _img_info(img) -> str:
        if img is None or getattr(img, "size", 0) == 0:
            return "img=None"
        mean = float(img.mean()) if hasattr(img, "mean") else -1
        return f"shape={getattr(img, 'shape', '?')} mean={mean:.1f}"

    def _save_debug_img(self, filename: str, img) -> None:
        if img is None or getattr(img, "size", 0) == 0:
            return
        os.makedirs(DEBUG_CROPS, exist_ok=True)
        try:
            Image.fromarray(img).save(os.path.join(DEBUG_CROPS, filename))
        except Exception as e:
            self._dbg(f"save crop {filename} failed: {e}")

    def read_page_number(self) -> Optional[int]:
        gacha = self.config_manager.get_gacha()
        bbox = gacha["page_number"]
        img = safe_grab(bbox)
        text = self.ocr.extract_text(
            img,
            is_number=True,
            config=self._ocr_config(),
            allowlist="0123456789",
        )
        parsed = parse_page_number(text)
        self._dbg(
            f"page_ocr bbox={list(bbox)} raw={text!r} parsed={parsed} "
            f"{self._img_info(img)}"
        )
        return parsed

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

    def _ocr_purchase_time(self, bbox, cfg: dict) -> Tuple[str, str, Optional[np.ndarray]]:
        """OCR a purchase_time cell. Retry only when the clock cannot be parsed."""
        _, settle = self._delays()
        img = safe_grab(bbox)
        raw = self.ocr.extract_text(
            img, config=cfg, allowlist="0123456789-: "
        )
        parsed = clean_timestamp(raw)
        if parsed:
            if not timestamp_is_strict(raw):
                self._dbg(f"  time repaired {raw!r} -> {parsed!r}")
            return raw, parsed, img

        for attempt in range(1, 4):
            self._dbg(f"  time retry {attempt}/3 raw={raw!r}")
            time.sleep(settle)
            img = safe_grab(bbox)
            raw = self.ocr.extract_text(
                img, config=cfg, allowlist="0123456789-: "
            )
            parsed = clean_timestamp(raw)
            if parsed:
                self._dbg(
                    f"  time retry {attempt}/3 recovered {raw!r} -> {parsed!r}"
                )
                return raw, parsed, img

        self._dbg(f"  time retry exhausted raw={raw!r}")
        return raw, "", img

    def scan_current_page(
        self,
        ordinals: Optional[Dict[Tuple[str, str, str], int]] = None,
        dump_crops_prefix: Optional[str] = None,
    ) -> List[Dict]:
        """OCR all 6 rows on the current Access Records page."""
        if ordinals is None:
            ordinals = defaultdict(int)

        gacha = self.config_manager.get_gacha()
        cfg = self._ocr_config()
        pulls: List[Dict] = []
        rows = gacha.get("rows", [])
        seen = 0
        self._dbg(f"scan_current_page rows_configured={len(rows)}")

        for i, row in enumerate(rows):
            source_img = safe_grab(row["purchase_source"])
            type_img = safe_grab(row["type"])
            name_img = safe_grab(row["name"])
            raw_time, purchase_time, time_img = self._ocr_purchase_time(
                row["purchase_time"], cfg
            )
            raw_source = self.ocr.extract_text(source_img, config=cfg)
            raw_type = self.ocr.extract_text(type_img, config=cfg)
            raw_name = self.ocr.extract_text(name_img, config=cfg)
            purchase_source = clean_source(raw_source)
            item_type = clean_type(raw_type)
            item_name = clean_item_name(raw_name, item_type=item_type)

            if raw_time.strip() or raw_name.strip():
                seen += 1

            self._dbg(
                f"  row{i} time_raw={raw_time!r} -> {purchase_time!r} "
                f"{self._img_info(time_img)} | "
                f"name_raw={raw_name!r} -> {item_name!r} "
                f"{self._img_info(name_img)} | "
                f"src={raw_source!r} -> {purchase_source!r} | "
                f"type={raw_type!r} -> {item_type!r}"
            )

            if dump_crops_prefix:
                self._save_debug_img(f"{dump_crops_prefix}_r{i}_time.png", time_img)
                self._save_debug_img(f"{dump_crops_prefix}_r{i}_name.png", name_img)
                self._save_debug_img(f"{dump_crops_prefix}_r{i}_src.png", source_img)
                self._save_debug_img(f"{dump_crops_prefix}_r{i}_type.png", type_img)

            if not purchase_time or not item_name:
                self._dbg(
                    f"  row{i} SKIP missing "
                    f"{'time' if not purchase_time else ''}"
                    f"{' name' if not item_name else ''}"
                )
                continue

            key = (purchase_time, item_name, item_type or "Unknown")
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

        self._last_rows_seen = seen
        self._dbg(f"scan_current_page kept={len(pulls)}/{len(rows)} seen={seen}")
        return pulls

    def _scan_page_accepted(
        self,
        ordinals: Dict[Tuple[str, str, str], int],
        page: Optional[int],
        pages_scanned: int,
        status_cb: STATUS_CB,
    ) -> Tuple[List[Dict], str]:
        """OCR the current page; retry up to 3 times if any row fails.

        Failed attempts are discarded (no insert, ordinals unchanged).
        Returns (pulls, outcome) with outcome 'ok', 'empty', or 'incomplete'.
        """
        _, settle = self._delays()
        last_seen = 0

        for attempt in range(1, 4):
            working: Dict[Tuple[str, str, str], int] = defaultdict(int, ordinals)
            dump = None
            if attempt > 1:
                dump = f"retry_p{page if page is not None else pages_scanned}_a{attempt}"
                self._status(
                    status_cb,
                    f"Page {page if page is not None else '?'} failed - "
                    f"dropping rows, retry {attempt}/3...",
                )
                self._dbg(
                    f"discard page {page} attempt {attempt - 1}, rescan {attempt}/3"
                )
                time.sleep(settle)

            pulls = self.scan_current_page(working, dump_crops_prefix=dump)
            seen = int(getattr(self, "_last_rows_seen", 0) or 0)
            last_seen = seen

            if seen == 0:
                self._dbg(f"page {page} attempt={attempt} no row text")
                continue

            if len(pulls) == seen:
                for key, value in working.items():
                    ordinals[key] = value
                self._dbg(
                    f"page {page} accepted attempt={attempt} kept={len(pulls)}/{seen}"
                )
                return pulls, "ok"

            self._dbg(
                f"page {page} incomplete attempt={attempt} "
                f"kept={len(pulls)}/{seen} - drop all"
            )

        if last_seen == 0:
            return [], "empty"
        self._dbg(
            f"page {page} still incomplete after 3 attempts - drop all, do not insert"
        )
        return [], "incomplete"

    def _turn_next(
        self,
        prev_page: Optional[int],
        click_delay: float,
        settle: float,
    ) -> Tuple[Optional[int], Optional[str]]:
        self._dbg("click btn_next")
        self.click_bbox("btn_next")
        time.sleep(click_delay)
        time.sleep(settle)
        new_page = self.read_page_number()
        self._dbg(f"after next prev={prev_page} new={new_page}")
        if new_page is not None and prev_page is not None and new_page == prev_page:
            return new_page, "page_unchanged"
        if new_page is not None and prev_page is not None and new_page < prev_page:
            return new_page, "page_did_not_advance"
        return new_page, None

    def scan_all_pages(
        self,
        status_cb: STATUS_CB = None,
        on_pull: PULL_CB = None,
        max_pages: int = 500,
    ) -> Dict:
        """
        Scan from the current Access Records page toward older pages until
        stuck/empty, or until a page of pulls is already in the DB.

        Returns summary dict with inserted/skipped/pages/pulls/caught_up.
        """
        self._stop = False
        click_delay, settle = self._delays()
        ordinals: Dict[Tuple[str, str, str], int] = defaultdict(int)
        session_pulls: List[Dict] = []
        inserted_total = 0
        skipped_total = 0
        caught_up = False
        stop_reason = None
        last_new_page: Optional[int] = None

        self._start_debug_log()
        gacha = self.config_manager.get_gacha()
        self._dbg(
            f"start click_delay={click_delay:.3f}s settle={settle:.3f}s "
            f"rows={len(gacha.get('rows') or [])} "
            f"page_bbox={list(gacha.get('page_number') or [])} "
            f"next_bbox={list(gacha.get('btn_next') or [])}"
        )

        # Click the page indicator so the game is focused before OCR,
        # without turning the page.
        self._dbg("click page_number (focus)")
        self.click_bbox("page_number")
        time.sleep(click_delay)
        time.sleep(settle)
        self._save_debug_img(
            "focus_page_number.png", safe_grab(gacha["page_number"])
        )

        page = self.read_page_number()
        self._status(
            status_cb,
            f"Starting from page {page if page is not None else '?'}...",
        )

        pages_scanned = 0
        prev_page: Optional[int] = None

        while pages_scanned < max_pages:
            if self._stop:
                stop_reason = "user_stop"
                self._dbg("stop_reason=user_stop")
                self._status(status_cb, "Scan stopped.")
                break

            page = self.read_page_number()
            self._status(
                status_cb,
                f"Scanning page {page if page is not None else pages_scanned + 1}...",
            )
            self._dbg(f"loop pages_scanned={pages_scanned} page={page}")

            page_pulls, outcome = self._scan_page_accepted(
                ordinals, page, pages_scanned, status_cb
            )
            if outcome == "empty":
                stop_reason = "empty_page"
                self._dbg("stop_reason=empty_page (no row text after retries)")
                try:
                    self._save_debug_img(
                        f"empty_p{page}_page_number.png",
                        safe_grab(gacha["page_number"]),
                    )
                except Exception:
                    pass
                self._status(status_cb, "Empty page - finished.")
                break
            if outcome == "incomplete":
                self._dbg(
                    f"page {page} dropped after retries, turning page without insert"
                )
                pages_scanned += 1
                prev_page = page
                if self._stop:
                    stop_reason = "user_stop"
                    break
                new_page, turn_reason = self._turn_next(
                    prev_page, click_delay, settle
                )
                last_new_page = new_page
                if turn_reason == "page_unchanged":
                    stop_reason = turn_reason
                    self._status(status_cb, "Next page unchanged - finished.")
                    break
                if turn_reason == "page_did_not_advance":
                    stop_reason = turn_reason
                    self._status(status_cb, "Page did not advance - finished.")
                    break
                continue

            ins, known = self.db.insert_pulls(page_pulls)
            inserted_total += ins
            skipped_total += known
            self._dbg(f"insert new={ins} known={known}")
            for p in page_pulls:
                session_pulls.append(p)
                if on_pull:
                    on_pull(p)

            pages_scanned += 1
            prev_page = page

            # A 10-pull can repeat the same name in one second (ordinal 0, 1, ...).
            # A doll and a weapon can also share a name at that second. Those are
            # not "already known". Stop only when this page inserted nothing
            # because every row was already in the DB.
            if known > 0 and ins == 0:
                caught_up = True
                stop_reason = "caught_up"
                self._dbg(f"stop_reason=caught_up known={known} new=0")
                self._status(
                    status_cb,
                    f"Caught up - all {known} pull(s) on this page already in history. "
                    f"New this run: {inserted_total}.",
                )
                break

            if self._stop:
                stop_reason = "user_stop"
                break

            new_page, turn_reason = self._turn_next(prev_page, click_delay, settle)
            last_new_page = new_page
            if turn_reason == "page_unchanged":
                stop_reason = turn_reason
                self._dbg("stop_reason=page_unchanged")
                self._status(status_cb, "Next page unchanged - finished.")
                break
            if turn_reason == "page_did_not_advance":
                stop_reason = turn_reason
                self._dbg("stop_reason=page_did_not_advance")
                self._status(status_cb, "Page did not advance - finished.")
                break

        if stop_reason is None:
            if pages_scanned >= max_pages:
                stop_reason = "max_pages"
            else:
                stop_reason = "complete"
            self._status(
                status_cb,
                f"Done. Pages {pages_scanned}, "
                f"saved {inserted_total}, known {skipped_total}.",
            )
        self._dbg(
            f"end reason={stop_reason} pages={pages_scanned} "
            f"new={inserted_total} known={skipped_total} "
            f"last_page={prev_page} after_next={last_new_page}"
        )
        return {
            "pages": pages_scanned,
            "inserted": inserted_total,
            "skipped": skipped_total,
            "caught_up": caught_up,
            "stopped": self._stop,
            "stop_reason": stop_reason,
            "prev_page": prev_page,
            "new_page": last_new_page,
            "pulls": session_pulls,
        }
