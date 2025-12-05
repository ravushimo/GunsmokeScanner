# gunsmoke.app Theme Colors
THEME = {
    'bg_dark': '#0f1419',           # Main background
    'bg_medium': '#1a1f2e',         # Panel background
    'bg_light': '#252d3d',          # Card background
    'accent_cyan': '#00d4ff',       # Primary accent (cyan)
    'accent_hover': '#00a8cc',      # Hover state
    'text_primary': '#ffffff',      # Main text
    'text_secondary': '#94a3b8',    # Secondary text
    'text_muted': '#64748b',        # Muted text
    'success': '#10b981',           # Success green
    'warning': '#f59e0b',           # Warning orange
    'danger': '#ef4444',            # Danger red
    'border': '#334155'             # Border color
}

# Default Configuration
DEFAULT_CONFIG = {
    "ocr_languages": ["ch_sim", "en"],
    "preprocessing": {
        "threshold": 140,
        "adaptive": True,
        "kernel_size": [2, 2]
    },
    "validation": {
        "min_nickname_length": 2,
        "min_total_score": 0,
        "max_duplicate_check": 20
    }
}

# App Version
APP_VERSION = "1.2.0"
GITHUB_REPO = "ravushimo/GunsmokeScanner"
