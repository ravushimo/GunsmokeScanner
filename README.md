# Gunsmoke Scanner

![Version](https://img.shields.io/badge/version-1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

A powerful OCR-based tool for scanning and extracting leaderboard data from Girls Frontline 2 (GFL2) game screenshots. Features automatic season calculation, visual region configuration, and inline data editing.

## 🌟 Features

- **🎯 Visual Region Setup**: Click-to-select and drag overlays to configure capture regions
- **📅 Auto Season Calculation**: Automatically calculates current GFL2 season based on date (7-day seasons + 14-day breaks)
- **🔍 Intelligent OCR**: Uses EasyOCR with GPU acceleration for accurate Chinese and English text recognition
- **⚡ Threaded Capture**: Capture process runs in background to keep UI responsive
- **✏️ Inline Editing**: Double-click any cell to edit data directly in the table
- **✨ Guild Rank Support**: Option to include Guild Rank when saving data
- **💾 CSV Export**: Export captured data in standardized format (season, ign, topscore, totalscore, guildrank)
- **🔄 Auto Updates**: Checks GitHub releases for new versions on startup
- **🌐 Cloud Upload**: Direct upload integration with gunsmoke.app
- **🎨 Modern UI**: Dark theme with cyan accents inspired by gunsmoke.app
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

The app automatically calculates the current GFL2 season based on a reference date.

- **Auto-detection**: Shows current season with dates on launch
- **Manual override**: Click "Set Season" to manually specify season number

### 3. **OCR Capture Process**

When F9 is pressed:

1. **Screen Capture**: Grabs pixels from all 15 defined regions
2. **Preprocessing**: Converts to grayscale, thresholding, and noise removal
3. **Text Extraction**: EasyOCR processing in a background thread
4. **Data Cleaning**: Regex-based cleaning for scores and nicknames
5. **Storage**: Valid entries added to in-memory data table

### 4. **Data Management**

- **Live Table**: Displays all captured data with formatting
- **Inline Editing**: Double-click cell to edit right in the table
- **CSV Export**: Saves to `./results/` with optional Guild Rank prompt
- **Upload**: Securely upload data to gunsmoke.app directly from the app

## 🛠️ Installation

### For Development

1. **Clone or download** this repository

2. **Install Python 3.9+** from [python.org](https://python.org)

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the app**:
```bash
python main.py
```

### For End Users

1. **Download** the pre-built executable from releases
2. **Run** `GunsmokeScanner.exe`
3. **First time**: Configure regions in Setup tab
4. **Start scanning**: Switch to Capture tab and press F9

## 📦 Building Executable

To create a standalone `.exe` file using the provided script:

```bash
compile.bat
```

The executable will be created in the `dist/GunsmokeScanner` folder.

**Note**: The build is configured in `onedir` mode to handle EasyOCR's large dependencies efficiently.

## 📖 Usage Guide

### Capturing Data

1. Open GFL2 game to leaderboard screen
2. Go to **Capture Data** tab
3. Press **F9** or click "📸 Capture"
4. App scans all 5 rows and adds new players to table
5. Repeat for each page of leaderboard
6. Click **💾 Save to CSV** when finished
7. Enter **Guild Rank** if desired, or press Esc to skip

### Uploading to Cloud

1. Go to **Upload** tab
2. Enter your gunsmoke.app credentials
3. Click **Verify Login** to check permissions
4. Click **Upload Last CSV** to send the most recent capture

## ⚙️ Configuration Files

### `config.json`

Stores capture regions, OCR settings, and upload credentials (encrypted).

### CSV Output Format

```csv
season,ign,topscore,totalscore,guildrank
17,PlayerName,3420,125000,5
17,AnotherPlayer,6154,98500,
```

## 🤝 Contributing

Contributions welcome!

## 📝 License

MIT License - feel free to modify and distribute.

## 🔗 Links

- **Website**: [gunsmoke.app](https://gunsmoke.app)
- **Game**: Girls Frontline 2

## ⚠️ Troubleshooting

**App crashes on startup?**
- Delete config.json and restart (creates default)
- Check Python version is 3.9+

**OCR not accurate?**
- Adjust preprocessing threshold in config.json
- Ensure regions are precisely positioned over text

**Executable won't run?**
- Windows may block unsigned executables -> Right-click -> Properties -> Unblock

---

Made with ⚡ by the Gunsmoke team
