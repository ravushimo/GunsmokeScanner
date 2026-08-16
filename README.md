# Gunsmoke Scanner

![Version](https://img.shields.io/badge/version-1.4.2--dev-blue)
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

Choose **1) Install dependencies** (recommended / default), or run `setup.bat setup`.
This creates `.venv` and installs CPU PyTorch (no GPU/CUDA build).

Then:

```bash
start.bat
```

Or: `.venv\Scripts\python.exe main.py`

Python 3.9+ recommended.

## End users

1. Download the **CPU** release build from GitHub Releases
2. Run `GunsmokeScanner-CPU.exe`
3. Pick **Gunsmoke**, **Gacha**, **Inventory**, or **Settings** in the header
4. Calibrate regions in **Setup**, then use **Capture**

OCR runs on CPU. EasyOCR loads in the background after the window opens by default
(see Settings -> Load OCR libraries on startup). Models download into `easyocr_models\`
on first use.

## Building

Same entry point:

```bash
setup.bat
```

| Menu | What it does |
|------|----------------|
| **1) Install dependencies** | Create/refresh `.venv`, install requirements + CPU torch |
| **2) Build exe from .venv** | PyInstaller using `.venv` from option 1 -> `dist/GunsmokeScanner-CPU/` |
| **3) Build release** | Developers: cached `.venv-build-cpu` so wheels are not redownloaded each time |

Optional 7-Zip archive after build (default No).

| Env | Purpose |
|-----|---------|
| `.venv` | Run from source + option 2 builds |
| `.venv-build-cpu` | Cached CPU release toolchain (~1.1 GB) |

| Output | Notes |
|--------|--------|
| `dist/GunsmokeScanner-CPU/` | CPU OCR - this is what GitHub Releases publish |
| `dist/GunsmokeScanner-CPU-vX.Y.Z.7z` | Optional; only if you choose Yes and 7-Zip is available |

Prefer leaving `easyocr_models/` out of releases - models download on first use
into a folder next to the exe (English by default; CN/KR/JP when enabled in Settings).
Force-refresh release torch cache: `python scripts/bootstrap_build_venvs.py --force`.

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
- **Slow first OCR** - EasyOCR downloads model files into `easyocr_models\` on first use; later scans are faster. Enable **Load OCR libraries on startup** in Settings if you prefer splash-time loading.
- **Bad OCR** - retune regions; adjust gacha click/settle delays if pages skip; add CN/KR/JP in Settings if needed
- **Unsigned exe blocked** - Properties -> Unblock on Windows

## License

MIT
