from PIL import ImageGrab
import numpy as np
import pyautogui

def safe_grab(bbox) -> np.ndarray:
    """Safely capture screen region"""
    x, y, w, h = bbox
    screen_w, screen_h = pyautogui.size()
    
    x = max(0, x)
    y = max(0, y)
    right = min(screen_w, x + w)
    bottom = min(screen_h, y + h)
    
    if right <= x or bottom <= y or w <= 0 or h <= 0:
        return None
    
    try:
        img = ImageGrab.grab(bbox=(x, y, right, bottom))
        return np.array(img)
    except:
        return None
