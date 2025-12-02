# GFL2 Leaderboard Scanner

![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

A powerful OCR-based tool for scanning and extracting leaderboard data from Girls Frontline 2 (GFL2) game screenshots. Features automatic season calculation, visual region configuration, and inline data editing.

## 🌟 Features

- **🎯 Visual Region Setup**: Click-to-select and drag overlays to configure capture regions
- **📅 Auto Season Calculation**: Automatically calculates current GFL2 season based on date (7-day seasons + 14-day breaks)
- **🔍 Intelligent OCR**: Uses EasyOCR with GPU acceleration for accurate Chinese and English text recognition
- **✏️ Inline Editing**: Double-click any cell to edit data directly in the table
- **💾 CSV Export**: Export captured data in standardized format (season, ign, topscore, totalscore)
- **🎨 Modern UI**: Dark theme with cyan accents inspired by gunsmoke.app
- **⌨️ Hotkey Support**: F9 to capture, Enter to navigate cells
- **🪟 Always on Top**: Optional window mode for easy multitasking

## 📚 Libraries Used

### Core Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| **EasyOCR** | Latest | Deep learning-based OCR engine for text recognition |
| **PyTorch** | Latest | Neural network framework (required by EasyOCR) |
| **OpenCV (cv2)** | Latest | Image preprocessing and manipulation |
| **NumPy** | Latest | Numerical operations and array handling |
| **Pandas** | Latest | Data manipulation and CSV export |
| **Pillow (PIL)** | Latest | Screen capture via ImageGrab |
| **PyAutoGUI** | Latest | Screen resolution detection and positioning |
| **keyboard** | Latest | Global hotkey registration (F9) |

### GUI Framework

| Library | Purpose |
|---------|---------|
| **tkinter** | Main GUI framework (built-in with Python) |
| **ttk** | Themed widgets for modern appearance |

### Build Tool

| Library | Purpose |
|---------|---------|
| **PyInstaller** | Package app into standalone executable |

## 🚀 How It Works

### 1. **Region Configuration**

The app uses a visual overlay system to define capture regions:

- **15 total regions**: 5 rows × 3 columns (Nickname, Single High, Total Score)
- **Color-coded overlays**: Cyan for nicknames, Green for single scores, Orange for total scores
- **Interactive positioning**: Click any overlay to auto-select that row/column
- **Drag-to-adjust**: Mouse drag or arrow keys for fine-tuning
- **Manual entry**: Type exact coordinates in 2×2 grid layout

Regions are saved to `config.json` for persistence.

### 2. **Season Calculation**

The app automatically calculates the current GFL2 season:

```
Reference: Season 17 = Nov 30 - Dec 6, 2025 (Sunday to Saturday)
Pattern: 7 days active → 14 days break → repeat (21-day cycle)
```

- **Auto-detection**: Shows current season with dates on launch
- **Off-season handling**: Displays "Off-Season Break" during break periods
- **Manual override**: Click "Set Season" to manually specify season number

### 3. **OCR Capture Process**

When F9 is pressed:

1. **Screen Capture**: Grabs pixels from all 15 defined regions
2. **Preprocessing**:
   - Convert to grayscale
   - Apply adaptive thresholding for better contrast
   - Morphological operations to clean noise
3. **Text Extraction**:
   - EasyOCR reads Chinese and English characters
   - Numbers extracted with allowlist (0-9, comma)
   - Fallback to non-adaptive processing if initial attempt fails
4. **Data Cleaning**:
   - Remove special characters from nicknames
   - Strip non-digits from scores
   - Handle spurious leading '1' from flame icons
5. **Validation**:
   - Minimum nickname length check
   - Duplicate detection (checks last 20 entries)
6. **Storage**: Valid entries added to in-memory data table

### 4. **Data Management**

- **Live Table**: Displays all captured data with formatting (commas in scores)
- **Inline Editing**: Double-click cell → Edit → Press Enter to save and move to next
- **Navigation**: Enter moves right/down, Esc cancels edit
- **CSV Export**: Saves to `./results/GFL2_Season{N}_{timestamp}.csv`

## 🛠️ Installation

### For Development

1. **Clone or download** this repository

2. **Install Python 3.7+** from [python.org](https://python.org)

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the app**:
```bash
python gfl2_scanner.py
```

### For End Users

1. **Download** the pre-built executable from releases
2. **Run** `GFL2_Scanner.exe`
3. **First time**: Configure regions in Setup tab
4. **Start scanning**: Switch to Capture tab and press F9

## 📦 Building Executable

To create a standalone `.exe` file:

```bash
python -m PyInstaller gfl2_scanner.spec
```

The executable will be created in the `dist/` folder (~335 MB).

**Why is it large?**
- PyTorch deep learning framework: ~150-200 MB
- EasyOCR with language models: ~50-80 MB
- OpenCV and scientific libraries: ~80-100 MB

This is normal for AI-powered applications and allows the app to work offline without additional setup.

## 📖 Usage Guide

### First Run

1. **Welcome message** appears → Click OK
2. Go to **Setup Regions** tab
3. Enable **Show Overlay** checkbox in header
4. Position overlays over your game leaderboard:
   - Click an overlay to select it
   - Drag with mouse or use arrow keys
   - Or manually enter X, Y, Width, Height values
5. Click **Save Config** when done
6. Disable overlay (optional)

### Capturing Data

1. Open GFL2 game to leaderboard screen
2. Go to **Capture Data** tab
3. Season should auto-display (e.g., "Season 17 (Nov 30 - Dec 06)")
4. Press **F9** or click "📸 Capture"
5. App scans all 5 rows and adds new players to table
6. Repeat for each page of leaderboard
7. Click **💾 Save to CSV** when finished

### Editing Data

- **Double-click** any cell to edit
- **Enter** key: Save and move to next cell
- **Esc** key: Cancel editing
- **Delete row**: Not implemented (clear all and recapture if needed)

## ⚙️ Configuration Files

### `config.json`

Stores capture regions and settings:

```json
{
  "screen_resolution": [1920, 1080],
  "ocr_languages": ["ch_sim", "en"],
  "preprocessing": {
    "threshold": 140,
    "adaptive": true,
    "kernel_size": [2, 2]
  },
  "validation": {
    "min_nickname_length": 2,
    "min_total_score": 0,
    "max_duplicate_check": 20
  },
  "rows": [
    {
      "nickname": [x, y, width, height],
      "single_high": [x, y, width, height],
      "total_score": [x, y, width, height]
    }
    // ... 5 rows total
  ]
}
```

### CSV Output Format

```csv
season,ign,topscore,totalscore
17,PlayerName,3420,125000
17,AnotherPlayer,6154,98500
```

## 🎮 Season Reference

| Season | Start Date | End Date | Status |
|--------|------------|----------|--------|
| 17 | Nov 30, 2025 | Dec 06, 2025 | Active |
| 18 | Dec 21, 2025 | Dec 27, 2025 | Future |

*Break periods: 14 days between each season*

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Support for different game resolutions/DPI scaling
- [ ] Batch processing multiple screenshots
- [ ] Database integration instead of CSV
- [ ] Row deletion in data table
- [ ] Statistics and analytics dashboard

## 📝 License

MIT License - feel free to modify and distribute.

## 🔗 Links

- **Website**: [gunsmoke.app](https://gunsmoke.app)
- **Game**: Girls Frontline 2

## ⚠️ Troubleshooting

**OCR not accurate?**
- Adjust preprocessing threshold in config.json (try 120-160)
- Ensure regions are precisely positioned over text
- Check game UI scale settings

**App crashes on startup?**
- Delete config.json and restart (creates default)
- Check Python version is 3.7+
- Reinstall dependencies

**Executable won't run?**
- Windows may block unsigned executables
- Right-click → Properties → Unblock
- Some antivirus software flags PyInstaller apps

**Season wrong?**
- Use "Set Season" to manually override
- Verify your system date is correct

---

Made with ⚡ by the Gunsmoke team
