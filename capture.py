"""
GFL2 Leaderboard OCR Capture Tool
Captures player data from the Girls Frontline 2 leaderboard using EasyOCR.

Controls:
  F9  - Capture current 5 rows
  F10 - Save captured data to CSV
  ESC - Exit program
"""
import json
import time
import keyboard
import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab
import easyocr
import pandas as pd
import re
import os
from datetime import datetime

# ANSI color codes for better console output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_color(text, color=Colors.OKGREEN):
    """Print colored text to console"""
    print(f"{color}{text}{Colors.ENDC}")

# Load configuration
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
    print_color("✓ Configuration loaded successfully", Colors.OKGREEN)
except FileNotFoundError:
    print_color("✗ ERROR: config.json not found!", Colors.FAIL)
    print("Please run 'python visual_selector.py' first to create the configuration.")
    exit(1)
except json.JSONDecodeError as e:
    print_color(f"✗ ERROR: Invalid JSON in config.json: {e}", Colors.FAIL)
    exit(1)

# Initialize EasyOCR
print("\nLoading EasyOCR models...")
print("(This may take a moment on first run...)")
try:
    languages = CONFIG.get("ocr_languages", ["ch_sim", "en"])
    reader = easyocr.Reader(languages, gpu=False, model_storage_directory='./easyocr_models')
    print_color("✓ EasyOCR ready!\n", Colors.OKGREEN)
except Exception as e:
    print_color(f"✗ ERROR loading EasyOCR: {e}", Colors.FAIL)
    exit(1)

# Global state
captured_data = []
screen_w, screen_h = pyautogui.size()
capture_count = 0
start_time = time.time()

def safe_grab(bbox):
    """Safely capture a screen region with bounds checking"""
    x, y, w, h = bbox
    
    # Ensure coordinates are within screen bounds
    x = max(0, x)
    y = max(0, y)
    right = min(screen_w, x + w)
    bottom = min(screen_h, y + h)
    
    # Check if region is valid
    if right <= x or bottom <= y or w <= 0 or h <= 0:
        return None
    
    try:
        img = ImageGrab.grab(bbox=(x, y, right, bottom))
        return np.array(img)
    except Exception as e:
        print_color(f"  ⚠ Error grabbing region: {e}", Colors.WARNING)
        return None

def preprocess_image(img, adaptive=True):
    """Preprocess image for better OCR results"""
    if img is None or img.size == 0:
        return None
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Try adaptive thresholding first (better for varied backgrounds)
    if adaptive:
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
    else:
        # Fallback to simple thresholding
        threshold_value = CONFIG.get("preprocessing", {}).get("threshold", 150)
        _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
    
    # Denoise with morphological operations
    kernel_size = CONFIG.get("preprocessing", {}).get("kernel_size", [2, 2])
    kernel = np.ones(kernel_size, np.uint8)
    processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return processed

def extract_text_ocr(img, allow_chars=None, is_number=False):
    """Extract text from preprocessed image using EasyOCR"""
    if img is None:
        return ""
    
    try:
        # Try adaptive preprocessing first
        processed = preprocess_image(img, adaptive=True)
        
        if is_number:
            # For numbers, use allowlist
            result = reader.readtext(processed, detail=0, allowlist='0123456789,')
        else:
            # For text (nicknames)
            result = reader.readtext(processed, detail=0, paragraph=False)
        
        # Join all detected text
        text = ''.join(result)
        
        # If result is poor, try non-adaptive preprocessing
        if is_number and not text.strip():
            processed = preprocess_image(img, adaptive=False)
            result = reader.readtext(processed, detail=0, allowlist='0123456789,')
            text = ''.join(result)
        
        return text.strip()
    except Exception as e:
        print_color(f"  ⚠ OCR error: {e}", Colors.WARNING)
        return ""

def clean_nickname(text):
    """Clean and validate nickname text"""
    # Remove special characters, keep alphanumeric and Chinese characters
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return cleaned.strip()

def clean_number(text, is_single_score=False):
    """Clean and convert number text to integer"""
    # Remove any non-digit characters
    cleaned = re.sub(r'[^\d]', '', text)
    
    # Handle spurious leading '1' from flame icon in single_high scores
    if is_single_score and cleaned and len(cleaned) == 5 and cleaned[0] == '1':
        # If it's a 5-digit number starting with 1, try removing the first digit
        # This fixes cases like 13420 -> 3420, 16596 -> 6596
        potential_fix = cleaned[1:]
        if 1000 <= int(potential_fix) <= 9999:  # Typical single match score range
            cleaned = potential_fix
    
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0

def capture_once():
    """Capture current 5 rows from the leaderboard"""
    global captured_data, capture_count
    
    capture_count += 1
    print("\n" + "=" * 70)
    print_color(f"CAPTURE #{capture_count} - Processing 5 rows...", Colors.HEADER)
    print("=" * 70)
    
    batch = []
    successful_rows = 0
    
    for i, row_config in enumerate(CONFIG["rows"]):
        row_num = i + 1
        
        # Capture screen regions
        nick_img = safe_grab(row_config["nickname"])
        single_img = safe_grab(row_config["single_high"])
        total_img = safe_grab(row_config["total_score"])
        
        # Check if all regions captured successfully
        if nick_img is None or single_img is None or total_img is None:
            print_color(f"  Row {row_num}: Skipped (invalid region)", Colors.WARNING)
            continue
        
        # Extract text using OCR
        nickname = extract_text_ocr(nick_img, is_number=False)
        single_text = extract_text_ocr(single_img, is_number=True)
        total_text = extract_text_ocr(total_img, is_number=True)
        
        # Clean extracted data
        nickname = clean_nickname(nickname)
        single_score = clean_number(single_text, is_single_score=True)
        total_score = clean_number(total_text, is_single_score=False)
        
        # Validate data
        min_nick_len = CONFIG.get("validation", {}).get("min_nickname_length", 2)
        min_score = CONFIG.get("validation", {}).get("min_total_score", 1000)
        
        if len(nickname) >= min_nick_len and total_score >= min_score:
            batch.append({
                "nickname": nickname,
                "single_high": single_score,
                "total_score": total_score
            })
            successful_rows += 1
            print(f"  Row {row_num}: {nickname:20} | Single: {single_score:>7,} | Total: {total_score:>7,}")
        else:
            print_color(f"  Row {row_num}: Invalid data (nickname='{nickname}', total={total_score})", Colors.WARNING)
    
    # Remove duplicates (e.g., logged-in player appearing in multiple captures)
    max_dup_check = CONFIG.get("validation", {}).get("max_duplicate_check", 20)
    if batch and captured_data:
        recent_players = [p["nickname"] for p in captured_data[-max_dup_check:]]
        for player in batch[:]:
            if player["nickname"] in recent_players:
                print_color(f"  ⚠ Removed duplicate: {player['nickname']}", Colors.WARNING)
                batch.remove(player)
    
    # Add to captured data
    captured_data.extend(batch)
    
    # Print summary
    print("-" * 70)
    print_color(f"✓ Captured {successful_rows} rows this batch", Colors.OKGREEN)
    print_color(f"✓ Total unique players captured: {len(captured_data)}", Colors.OKCYAN)
    print("=" * 70)

def save_data():
    """Save captured data to CSV file"""
    if not captured_data:
        print_color("\n⚠ No data to save!", Colors.WARNING)
        return
    
    print("\n" + "=" * 70)
    print_color("SAVING DATA...", Colors.HEADER)
    print("=" * 70)
    
    # Create DataFrame
    df = pd.DataFrame(captured_data)
    
    # Remove duplicates (keep first occurrence)
    original_count = len(df)
    df = df.drop_duplicates(subset="nickname", keep="first")
    removed_dupes = original_count - len(df)
    
    # Sort by total score (descending)
    df = df.sort_values("total_score", ascending=False)
    
    # Add rank column
    df.insert(0, "rank", range(1, len(df) + 1))
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"GFL2_Leaderboard_{timestamp}.csv"
    
    # Save to CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    # Print summary
    print_color(f"✓ File saved: {filename}", Colors.OKGREEN)
    print(f"  Total players: {len(df)}")
    if removed_dupes > 0:
        print(f"  Duplicates removed: {removed_dupes}")
    
    # Show top 10
    print("\n" + "-" * 70)
    print("TOP 10 PLAYERS:")
    print("-" * 70)
    print(df.head(10)[["rank", "nickname", "single_high", "total_score"]].to_string(index=False))
    print("=" * 70)
    
    # Calculate session stats
    elapsed_time = time.time() - start_time
    print(f"\nSession Stats:")
    print(f"  Captures: {capture_count}")
    print(f"  Duration: {elapsed_time:.1f} seconds")
    print(f"  Players captured: {len(df)}")

# Print welcome message
print("\n" + "=" * 70)
print_color("GFL2 LEADERBOARD OCR CAPTURE TOOL", Colors.HEADER + Colors.BOLD)
print( "=" * 70)
print(f"\nScreen Resolution: {screen_w} x {screen_h}")
print(f"OCR Languages: {', '.join(CONFIG.get('ocr_languages', ['en']))}")
print("\nCONTROLS:")
print("  F9  - Capture current 5 rows")
print("  F10 - Save all captured data to CSV")
print("  ESC - Exit program")
print("\n" + "=" * 70)
print_color("Ready! Press F9 to start capturing...", Colors.OKGREEN)
print("=" * 70)

# Register hotkeys
keyboard.add_hotkey('f9', capture_once)
keyboard.add_hotkey('f10', save_data)

# Wait for ESC to exit
keyboard.wait('esc')

print_color("\nExiting... Goodbye!", Colors.OKCYAN)