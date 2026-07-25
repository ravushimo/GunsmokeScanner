"""Design tokens, default config, and version metadata.

Color palette matches gunsmoke.app dark UI (`:root` in site CSS) — the same
semantic names as `.docs/DESIGN.md`, remapped for the dark default theme.
PostHog Orange / Amber Gold remain hover accents.
"""

from __future__ import annotations

from typing import Optional

THEME = {
    # Surfaces (gunsmoke.app dark)
    "bg_canvas": "#1c1d1a",
    "bg_surface": "#252621",
    "bg_raised": "#2e2f2a",
    "bg_hover": "#32332e",
    "bg_featured": "#4a4438",
    # Primary CTA — orange accent (readable on dark surfaces)
    "cta_dark": "#F54E00",
    "cta_dark_text": "#ffffff",
    # Text
    "text_primary": "#c8c9c2",
    "text_strong": "#f2f3ef",
    "text_muted": "#9b9c94",
    "text_placeholder": "#7a7b74",
    "text_input": "#e8e9e4",
    # Borders / focus
    "border": "#3a3b36",
    "border_strong": "#3a3b36",
    "focus": "#3b82f6",
    # Hover-only accents
    "accent_orange": "#F54E00",
    "accent_amber": "#F7A501",
    # Semantic
    "success": "#6ee7b7",
    "warning": "#fbbf24",
    "danger": "#fca5a5",
    # GFL2 class colors (DESIGN.md — class / growth / perk fills)
    "class_sentinel": "#BD5849",
    "class_vanguard": "#8A55C6",
    "class_bulwark": "#4572C9",
    "class_support": "#4B7E5B",
    # GFL2 type / affinity colors (DESIGN.md — element badges)
    "element_burn": "#FF6600",
    "element_corrosion": "#8E66D1",
    "element_electric": "#FFD700",
    "element_freeze": "#4AC9E3",
    "element_hydro": "#0088CC",
    "element_physical": "#A0A0A0",
    "element_omni": "#E03131",
}

# DESIGN.md § GFL2 Specific Colors — class / growth / perk types
CLASS_COLORS = {
    "Sentinel": THEME["class_sentinel"],
    "Vanguard": THEME["class_vanguard"],
    "Bulwark": THEME["class_bulwark"],
    "Support": THEME["class_support"],
}


def class_color(core_type: Optional[str]) -> str:
    """Hex for a Growth Data / perk class type, or primary text if unknown."""
    if not core_type:
        return THEME["text_primary"]
    return CLASS_COLORS.get(str(core_type).strip(), THEME["text_primary"])


def class_tag(core_type: Optional[str]) -> str:
    """Treeview / Text tag name for a class type (e.g. class_Bulwark)."""
    key = str(core_type or "").strip()
    return f"class_{key}" if key in CLASS_COLORS else ""


def configure_class_tags(widget) -> None:
    """Apply GFL2 class foreground colors on a QTableWidget / QTreeWidget / TextEdit.

    For Qt tables, stores colors on the widget as `class_colors` dict used by
    callers when setting item foregrounds. For TextEdit-like widgets with
    `setTextColor` / document tags, no-ops unless a `tag_configure` exists.
    """
    colors = {f"class_{name}": color for name, color in CLASS_COLORS.items()}
    try:
        widget.setProperty("class_colors", colors)
    except Exception:
        pass
    if hasattr(widget, "tag_configure"):
        for tag, color in colors.items():
            widget.tag_configure(tag, foreground=color)
    elif hasattr(widget, "tag_config"):
        for tag, color in colors.items():
            widget.tag_config(tag, foreground=color)


SITE_URL = "https://gunsmoke.app/frontpage"
GITHUB_REPO = "ravushimo/GunsmokeScanner"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"

DEFAULT_UI = {
    "mode": "gunsmoke",
    "last_tab": {
        "gunsmoke": "capture",
        "gacha": "capture",
        "inventory": "capture",
        "settings": "main",
    },
    "always_on_top": True,
}

# EasyOCR language codes. English is always included; Asian extras are optional.
OCR_LANG_EN = "en"
OCR_LANG_PRESETS = (
    ("CN", "ch_sim", "Chinese (Simplified)"),
    ("KR", "ko", "Korean"),
    ("JP", "ja", "Japanese"),
)
# Extra codes for the custom picker (excluding en + preset codes).
OCR_LANG_CUSTOM_CHOICES = (
    ("ch_tra", "Chinese (Traditional)"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("pl", "Polish"),
    ("tr", "Turkish"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
)

DEFAULT_CONFIG = {
    "ocr_languages": [OCR_LANG_EN],
    "preprocessing": {
        "threshold": 140,
        "adaptive": True,
        "kernel_size": [2, 2],
    },
    "validation": {
        "min_nickname_length": 2,
        "min_total_score": 0,
        "max_duplicate_check": 20,
    },
    "ui": dict(DEFAULT_UI),
}

# Access Records table: 6 data rows, 4 columns + pagination controls.
GACHA_ROW_COLUMNS = (
    "purchase_time",
    "purchase_source",
    "type",
    "name",
)
GACHA_EXTRA_REGIONS = ("page_number", "btn_prev", "btn_next")

GACHA_DEFAULT_PREPROCESSING = {
    "threshold": 160,
    "adaptive": True,
    "kernel_size": [2, 2],
}

# Growth Data (Inventory) calibratable screen regions (flat under inventory.growth).
INVENTORY_GROWTH_REGIONS = (
    "grid",
    "type",
    "perks",
    "lock_btn",
    "own_count",
)

APP_VERSION = "1.4.1"
