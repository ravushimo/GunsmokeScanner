# GFL2 Leaderboard OCR Scanner

Automatically capture and record player data from the Girls Frontline 2 Platoon Internal Ranking leaderboard using EasyOCR.

## Features

- ✅ Captures 3 columns: Nickname, Single Match High Score, Total Score
- ✅ Processes 5 rows at a time (visible on screen)
- ✅ Keyboard hotkeys for easy control (F9/F10)
- ✅ Automatic duplicate detection
- ✅ Exports to CSV with rankings
- ✅ Colored console output for better visibility
- ✅ Adaptive image preprocessing for better OCR accuracy

## Requirements

- Python 3.7+
- Girls Frontline 2 running in windowed or borderless mode
- Screen resolution: 3440x1440 (or reconfigure using selector.py)

## Installation

1. Install required packages:
```bash
pip install -r requirements.txt
```

2. Download EasyOCR models (happens automatically on first run, but may take a few moments)

## Usage

### Step 1: Configure Capture Regions

Run the selector script to define the screen regions for OCR:

```bash
python selector.py
```

**Instructions:**
1. Open GFL2 and navigate to **Platoon Internal Ranking**
2. Make sure the leaderboard is visible with **Rank 1 at the top**
3. Run the selector script
4. Follow the on-screen instructions to click 6 points:
   - Nickname: left edge → right edge
   - Single Match High Score: left edge → right edge
   - Total Score: left edge → right edge

**Important:** All clicks should be on the **Rank 1 row only**! Click on the actual text, not badges or icons.

This creates a `config.json` file with the screen regions.

### Step 2: Validate Configuration (Recommended)

Before running the full capture, test your configuration:

```bash
python validator.py
```

This will:
- Capture test images of all 5 rows × 3 columns
- Save them to `validation_output/` folder
- Display warnings if regions appear incorrect

**Review the test images** to ensure they capture the correct text areas.

### Step 3: Capture Leaderboard Data

Run the main capture script:

```bash
python capture.py
```

**Controls:**
- **F9** - Capture current 5 visible rows
- **F10** - Save all captured data to CSV
- **ESC** - Exit program

**Workflow:**
1. Make sure GFL2 leaderboard is visible
2. Press **F9** to capture the first 5 rows
3. Scroll down in the game to show the next 5 rows
4. Press **F9** again
5. Repeat until you've captured all desired players
6. Press **F10** to save to CSV
7. Press **ESC** to exit

### Output

The script generates a CSV file named `GFL2_Leaderboard_YYYYMMDD_HHMMSS.csv` with:
- `rank` - Player rank (auto-generated based on total score)
- `nickname` - Player nickname
- `single_high` - Single match high score
- `total_score` - Total score

Data is automatically:
- De-duplicated (keeps first occurrence)
- Sorted by total score (descending)
- Ranked from 1 to N

## Configuration

The `config.json` file contains:

```json
{
  "screen_resolution": [3440, 1440],
  "ocr_languages": ["ch_sim", "en"],
  "preprocessing": {
    "threshold": 150,
    "adaptive": true,
    "kernel_size": [2, 2]
  },
  "validation": {
    "min_nickname_length": 2,
    "min_total_score": 5000,
    "max_duplicate_check": 20
  },
  "rows": [ ... ]
}
```

**Settings:**
- `ocr_languages` - OCR languages (`ch_sim` for Chinese, `en` for English)
- `preprocessing.adaptive` - Use adaptive thresholding (better for varied backgrounds)
- `validation.min_total_score` - Minimum score to consider valid (filters OCR errors)
- `validation.max_duplicate_check` - How many recent entries to check for duplicates

## Troubleshooting

### Issue: OCR not detecting text correctly

**Solutions:**
1. Re-run `selector.py` and make sure you click the correct regions
2. Run `validator.py` to check which regions are wrong
3. Adjust `preprocessing.threshold` in `config.json` (try values between 120-180)
4. Try toggling `preprocessing.adaptive` between `true` and `false`

### Issue: Capturing wrong regions

**Solutions:**
1. Make sure GFL2 is in focus and leaderboard is visible
2. Re-run `selector.py` with the leaderboard showing Rank 1 at the top
3. Click precisely on the text edges, not badges or icons
4. Use `validator.py` to verify regions before capturing

### Issue: Screen resolution mismatch

**Solution:**
- If you change screen resolution, re-run `selector.py` to regenerate `config.json`

### Issue: Slow performance

**Solutions:**
1. The first run is slower due to EasyOCR model downloads
2. GPU acceleration is disabled by default (set `gpu=True` in capture.py if you have CUDA)
3. Processing 5 rows takes ~5-10 seconds on CPU

## File Structure

```
GunsmokeScanner/
├── capture.py          # Main OCR capture script
├── selector.py         # Region configuration tool
├── validator.py        # Configuration testing tool
├── config.json         # Screen region configuration (auto-generated)
├── requirements.txt    # Python dependencies
├── easyocr_models/     # EasyOCR model files (auto-downloaded)
└── validation_output/  # Test images from validator (auto-created)
```

## Tips

- **Scroll smoothly** in the game to avoid motion blur
- **Wait 1-2 seconds** after scrolling before pressing F9
- **Check the console output** - it shows exactly what was captured
- **Review CSV file** before processing - OCR isn't 100% perfect
- **Use F10 multiple times** if needed - each save creates a new file with timestamp

## Known Limitations

- OCR accuracy depends on image quality (typically 95%+ accuracy)
- Chinese nicknames may require manual verification
- Very similar looking characters (0/O, 1/I) may be confused
- Screen must be visible (can't capture minimized window)

## Credits

Built with:
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR engine
- [PyAutoGUI](https://pyautogui.readthedocs.io/) - Screen capture
- [OpenCV](https://opencv.org/) - Image preprocessing
- [Pandas](https://pandas.pydata.org/) - Data management
