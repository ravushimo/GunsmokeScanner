# Gunsmoke Scanner

![Version](https://img.shields.io/badge/version-1.4.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

OCR desktop app for Girls' Frontline 2: Exilium (GLOBAL). Three modes:

- **Gunsmoke** - scan Gunsmoke leaderboard rows for [gunsmoke.app](https://gunsmoke.app)
- **Gacha** - scan Access Records history, store pulls locally, and compute pity / 50/50 / campaign stats
- **Inventory** - scan Remolding Cores (Growth Data), store locally, export CSV

## Features

### Shared
- Visual region overlays (drag, nudge, resize) with profiles per mode
- EasyOCR default **English only**; optional CN / KR / JP (+ custom) in Settings
- Dark UI aligned with gunsmoke.app (PySide6)
- Settings: keep on top, overlay, OCR languages, keybind list, manual update check
- Hotkeys: F9 start, F5 stop, F8/F7 inventory actions, F10 overlay, F4 layout template
- Remembers last mode and tab in `config.json`

### Gunsmoke mode
- Setup / Capture / Upload tabs
- Season auto-calculation with manual override
- F9 capture, inline table edit, CSV export, upload to gunsmoke.app

### Gacha mode
- Setup / Capture / History / Stats / Collection tabs
- Multi-page Access Records scan (F9 start, F5 stop); stops at first known pull
- Resolution layout templates
- Name fixer and Collection tab
- Local SQLite history (`./data/gacha.db`) with rarity, pity, filters, date picker
- Per-source pity, 50/50, premium campaigns, charts

### Inventory mode
- Setup / Capture / List tabs for Remolding Cores
- Full scan / last row / single core (F9 / F7 / F8)
- Type + perks OCR (name OCR removed as unreliable)
- CSV export (gunsmoke.app import coming soon)

## Libraries

| Library | Purpose |
|---------|---------|
| EasyOCR / PyTorch | OCR |
| OpenCV, NumPy, Pillow | Image capture and preprocessing |
| Pandas | CSV export |
| PyAutoGUI | Resolution / clicks |
| keyboard | Global hotkeys |
| PySide6 (Qt) | UI |
| cryptography | Upload credential encryption |

Fonts: IBM Plex Sans bundled under `assets/fonts/`.

## Installation (dev)

```bash
setup.bat
```

Choose **1) Install dependencies** (recommended / default), or run `setup.bat setup`. You will be asked:

- **CPU** (~1 GB torch stack) - default; works everywhere
- **CUDA** (~4-5 GB) - NVIDIA GPU OCR

Then:

```bash
start.bat
```

Or: `.venv\Scripts\python.exe main.py`

At runtime EasyOCR uses GPU automatically when the installed torch build has CUDA and a GPU is visible. **Card model does not matter** for the CUDA wheel (any recent RTX/GTX with drivers).

Python 3.9+ recommended.

## End users

1. Download the **CPU** release build from GitHub Releases
2. Run `GunsmokeScanner-CPU.exe`
3. Pick **Gunsmoke**, **Gacha**, **Inventory**, or **Settings** in the header
4. Calibrate regions in **Setup**, then use **Capture**

Official releases ship the CPU build only (works with or without an NVIDIA GPU; OCR stays on CPU). A CUDA/GPU build is not published because the CUDA libraries alone are over ~4 GB. If you want GPU OCR, clone the repo and self-compile with `setup.bat` (option 1, then 2 or 3) on a machine with NVIDIA drivers - see **Building** below.

## Building

Same entry point:

```bash
setup.bat
```

| Menu | What it does |
|------|----------------|
| **1) Install dependencies** | Create/refresh `.venv`, install requirements, then choose **CPU** (~1 GB) or **CUDA** (~4-5 GB) torch |
| **2) Build exe from .venv** | PyInstaller using `.venv` from option 1 - output is CPU or CUDA matching that install |
| **3) Build release** | Developers: cached `.venv-build-cpu` / `.venv-build-cuda` so wheels are not redownloaded each time |

Release submenu: CPU only (default) / CUDA only (NVIDIA) / Both, then optional 7-Zip (default No).

| Env | Purpose |
|-----|---------|
| `.venv` | Run from source + option 2 builds |
| `.venv-build-cpu` | Cached CPU release toolchain (~1.1 GB) |
| `.venv-build-cuda` | Cached CUDA release toolchain (~4.7 GB) |

| Output | Notes |
|--------|--------|
| `dist/GunsmokeScanner-CPU/` | CPU OCR - smaller; this is what GitHub Releases publish |
| `dist/GunsmokeScanner-CUDA/` | CUDA OCR - self-compile only (not published; CUDA libs are over ~4 GB) |
| `dist/GunsmokeScanner-*-vX.Y.Z.7z` | Optional; only if you choose Yes and 7-Zip is available |

Prefer leaving `easyocr_models/` out of releases - models download on first launch
into a folder next to the exe (English by default; CN/KR/JP when enabled in Settings).
Force-refresh release torch caches: `python scripts/bootstrap_build_venvs.py --force`.

CLI shortcuts: `setup.bat setup` · `setup.bat self` · `setup.bat release`

(`compile.bat` still works as a thin forwarder to `setup.bat`.)

## Usage

### Gunsmoke
1. Open the in-game leaderboard
2. Mode **Gunsmoke** -> **Capture** -> **F9**
3. Save CSV / upload from **Upload**

### Gacha
1. Open Access Records in-game
2. Mode **Gacha** -> calibrate **Setup**, then **Capture**
3. **F9** to scan pages · **F5** to stop
4. Browse **History** / **Stats** / **Collection**

### Inventory
1. Open Growth Data (Storeroom) in-game; unlock cores first
2. Mode **Inventory** -> calibrate **Setup**, then **Capture**
3. **F9** full scan · **F7** last row · **F8** current core · **F5** stop
4. Export CSV from **List**

## Config & data (not committed)

| Path | Contents |
|------|----------|
| `config.json` | Regions, delays, UI mode/tab, encrypted upload password |
| `data/gacha.db` | Local Access Records pulls |
| `data/inventory.db` | Local Remolding Core inventory |
| `results/` | Gunsmoke / inventory CSV exports |
| `easyocr_models/` | Downloaded OCR weights (created on first run / language apply) |

## Links

- Website: [gunsmoke.app](https://gunsmoke.app)
- Repo: [GitHub](https://github.com/ravushimo/GunsmokeScanner)

## Troubleshooting

- **Startup crash** - delete `config.json` and relaunch (defaults regenerate)
- **Slow first launch** - EasyOCR downloads model files into `easyocr_models\`; later launches are faster
- **Bad OCR** - retune regions; adjust gacha click/settle delays if pages skip; add CN/KR/JP in Settings if needed
- **Unsigned exe blocked** - Properties -> Unblock on Windows

## License

MIT
