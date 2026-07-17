"""Design tokens, default config, and version metadata.

Color palette matches gunsmoke.app dark UI (`:root` in site CSS) — the same
semantic names as `.docs/DESIGN.md`, remapped for the dark default theme.
PostHog Orange / Amber Gold remain hover accents.
"""

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
    # GFL2 class colors - overlay color coding
    "class_sentinel": "#BD5849",
    "class_vanguard": "#8A55C6",
    "class_bulwark": "#4572C9",
    "class_support": "#4B7E5B",
}

SITE_URL = "https://gunsmoke.app/frontpage"
GITHUB_REPO = "ravushimo/GunsmokeScanner"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"

DEFAULT_UI = {
    "mode": "gunsmoke",
    "last_tab": {
        "gunsmoke": "capture",
        "gacha": "capture",
    },
}

DEFAULT_CONFIG = {
    "ocr_languages": ["ch_sim", "en"],
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


APP_VERSION = "1.3.0"
