"""
GFL2 Leaderboard Configuration Validator
Tests the config.json to ensure regions are correctly defined before running full capture.
"""
import json
import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab, Image
import os
import time

# ANSI color codes
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
    """Print colored text"""
    print(f"{color}{text}{Colors.ENDC}")

# Load config
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
    print_color("✓ Configuration loaded successfully\n", Colors.OKGREEN)
except FileNotFoundError:
    print_color("✗ ERROR: config.json not found!", Colors.FAIL)
    print("Please run 'python selector.py' first.")
    exit(1)
except json.JSONDecodeError as e:
    print_color(f"✗ ERROR: Invalid JSON: {e}", Colors.FAIL)
    exit(1)

print("=" * 70)
print_color("GFL2 CONFIGURATION VALIDATOR", Colors.HEADER + Colors.BOLD)
print("=" * 70)

# Display config info
print("\nConfiguration Details:")
print(f"  Rows: {len(CONFIG.get('rows', []))}")
print(f"  OCR Languages: {', '.join(CONFIG.get('ocr_languages', []))}")
print(f"  Screen Resolution: {' x '.join(map(str, CONFIG.get('screen_resolution', [])))}")

# Check screen resolution
screen_w, screen_h = pyautogui.size()
config_res = CONFIG.get("screen_resolution", [])
if config_res and (config_res[0] != screen_w or config_res[1] != screen_h):
    print_color(f"\n⚠ WARNING: Screen resolution mismatch!", Colors.WARNING)
    print(f"  Config: {config_res[0]} x {config_res[1]}")
    print(f"  Current: {screen_w} x {screen_h}")
    print("  You may need to re-run selector.py")

print("\n" + "=" * 70)
print("READY TO TEST CAPTURE")
print("=" * 70)
print("Make sure:")
print("  1. GFL2 is running and in focus")
print("  2. Leaderboard is visible")
print("  3. Rank 1 is at the top of the visible list")
print("\nThis will capture test images for validation.")

input("\nPress ENTER when ready...")

# Create output directory for test images
output_dir = "validation_output"
os.makedirs(output_dir, exist_ok=True)

def safe_grab(bbox):
    """Safely capture a screen region"""
    x, y, w, h = bbox
    x = max(0, x)
    y = max(0, y)
    right = min(screen_w, x + w)
    bottom = min(screen_h, y + h)
    
    if right <= x or bottom <= y:
        return None
    
    try:
        return np.array(ImageGrab.grab(bbox=(x, y, right, bottom)))
    except:
        return None

print("\n" + "=" * 70)
print("CAPTURING TEST IMAGES...")
print("=" * 70)

all_success = True

for i, row in enumerate(CONFIG["rows"]):
    row_num = i + 1
    print(f"\nRow {row_num}:")
    
    # Capture each region
    for region_name in ["nickname", "single_high", "total_score"]:
        bbox = row.get(region_name)
        if not bbox:
            print_color(f"  ✗ {region_name}: Missing in config", Colors.FAIL)
            all_success = False
            continue
        
        img = safe_grab(bbox)
        if img is None:
            print_color(f"  ✗ {region_name}: Failed to capture", Colors.FAIL)
            all_success = False
            continue
        
        # Save image
        filename = f"{output_dir}/row{row_num}_{region_name}.png"
        Image.fromarray(img).save(filename)
        
        # Check if image is mostly blank
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        non_blank = np.count_nonzero(gray < 250)
        total_pixels = gray.size
        coverage = (non_blank / total_pixels) * 100
        
        if coverage < 5:
            print_color(f"  ⚠ {region_name}: Image mostly blank ({coverage:.1f}% content)", Colors.WARNING)
            all_success = False
        else:
            coords = f"({bbox[0]}, {bbox[1]}, {bbox[2]}x{bbox[3]})"
            print_color(f"  ✓ {region_name}: Saved ({coverage:.1f}% content) {coords}", Colors.OKGREEN)

print("\n" + "=" * 70)

if all_success:
    print_color("✓ VALIDATION SUCCESSFUL!", Colors.OKGREEN)
    print(f"\nTest images saved to: {output_dir}/")
    print("\nNext steps:")
    print("  1. Review the test images to ensure they contain the correct text")
    print("  2. If images look good, run: python capture.py")
    print("  3. Use F9 to capture, F10 to save, ESC to quit")
else:
    print_color("⚠ VALIDATION ISSUES DETECTED", Colors.WARNING)
    print(f"\nTest images saved to: {output_dir}/")
    print("\nRecommended actions:")
    print("  1. Review the test images")
    print("  2. If regions are wrong, re-run: python selector.py")
    print("  3. Make sure the game is visible and leaderboard is showing")

print("=" * 70)
