# Gunsmoke Scanner

![Version](https://img.shields.io/badge/version-1.3.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

OCR desktop app for Girls' Frontline 2: Exilium (GLOBAL). Two modes:

- **Gunsmoke** — scan Gunsmoke leaderboard rows for [gunsmoke.app](https://gunsmoke.app)
- **Gacha** — scan Access Records history, store pulls locally, and compute pity / 50/50 / campaign stats

## Features

### Shared
- Visual region overlays (drag, nudge, resize) with profiles per mode
- EasyOCR (Chinese + English)
- Dark UI aligned with gunsmoke.app
- Always on top + show overlay toggles
- Auto-check GitHub releases on startup
- Remembers last mode and tab in `config.json`

### Gunsmoke mode
- Setup / Capture / Upload tabs
- Season auto-calculation with manual override
- F9 capture, inline table edit, CSV export, upload to gunsmoke.app

### Gacha mode
- Setup / Capture / History / Stats tabs
- Multi-page Access Records scan (F9 start, **F5** stop)
- Configurable click delay / OCR settle (defaults 150ms / 100ms)
- Local SQLite history (`./data/gacha.db`) with rarity, pity, filters, date picker
- Per-source pity, 50/50 win/loss (standard elite pool), premium campaigns, charts

## Libraries

| Library | Purpose |
|---------|---------|
| EasyOCR / PyTorch | OCR |
| OpenCV, NumPy, Pillow | Image capture & preprocessing |
| Pandas | CSV export (Gunsmoke) |
| PyAutoGUI | Resolution / clicks |
| keyboard | Global hotkeys (F9, F5) |
| CustomTkinter | UI |
| cryptography | Upload credential hashing |

Fonts: IBM Plex Sans bundled under `assets/fonts/`.

## Installation (dev)

```bash
install_deps.bat
python main.py
```

Or manually:

```bash
pip install -r requirements.txt
python scripts/ensure_torch.py
python main.py
```

`ensure_torch.py` checks for an NVIDIA GPU (`nvidia-smi`). If present, it installs the CUDA PyTorch wheel; otherwise it keeps CPU torch. **Card model does not matter** (any recent RTX/GTX with drivers uses the same build). At runtime EasyOCR auto-enables GPU when `torch.cuda.is_available()`.

Python 3.9+ recommended.

## End users

1. Download a release build
2. Run `GunsmokeScanner.exe`
3. Pick **Gunsmoke** or **Gacha** in the header
4. Calibrate regions in **Setup**, then use **Capture**

## Building

```bash
compile.bat
```

Builds **two** onedir releases (torch is baked in, so CPU and CUDA cannot share one folder):

| Output | Notes |
|--------|--------|
| `dist/GunsmokeScanner-CPU/` | CPU OCR — smaller, works everywhere |
| `dist/GunsmokeScanner-CUDA/` | CUDA OCR — needs NVIDIA GPU + drivers |
| `dist/GunsmokeScanner-*-vX.Y.Z.7z` | 7-Zip archives (if 7-Zip is installed) |

Requires `.venv`, project deps, and preferably `easyocr_models/`. The script switches the venv between CPU and CUDA torch between the two PyInstaller runs.

## Usage

### Gunsmoke
1. Open the in-game leaderboard
2. Mode **Gunsmoke** → **Capture** → **F9**
3. Save CSV / upload from **Upload**

### Gacha
1. Open Access Records in-game
2. Mode **Gacha** → calibrate **Setup**, then **Capture**
3. **F9** to scan pages · **F5** to stop
4. Browse **History** / **Stats**

## Config & data (not committed)

| Path | Contents |
|------|----------|
| `config.json` | Regions, delays, UI mode/tab, hashed upload password |
| `data/gacha.db` | Local Access Records pulls |
| `results/` | Gunsmoke CSV exports |
| `easyocr_models/` | Downloaded OCR weights |

## Links

- Website: [gunsmoke.app](https://gunsmoke.app)
- Repo: [GitHub](https://github.com/ravushimo/GunsmokeScanner)

## Troubleshooting

- **Startup crash** — delete `config.json` and relaunch (defaults regenerate)
- **Bad OCR** — retune regions; adjust gacha click/settle delays if pages skip
- **Unsigned exe blocked** — Properties → Unblock on Windows

## License

MIT
