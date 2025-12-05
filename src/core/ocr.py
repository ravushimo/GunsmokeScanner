import cv2
import numpy as np
import easyocr
import re
from typing import List, Tuple, Optional

class OCRProcessor:
    def __init__(self, languages: List[str] = None):
        if languages is None:
            languages = ["ch_sim", "en"]
        
        print("Loading EasyOCR models...")
        self.reader = easyocr.Reader(languages, gpu=True, model_storage_directory='./easyocr_models')
        print("EasyOCR ready!")
    
    def preprocess_image(self, img: np.ndarray, config: dict = None) -> Optional[np.ndarray]:
        """Preprocess image for OCR"""
        if img is None or img.size == 0:
            return None
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        adaptive = True
        if config and "preprocessing" in config:
            adaptive = config["preprocessing"].get("adaptive", True)
        
        if adaptive:
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            threshold_value = 150
            if config:
                threshold_value = config.get("preprocessing", {}).get("threshold", 150)
            _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
        
        kernel_size = [2, 2]
        if config:
            kernel_size = config.get("preprocessing", {}).get("kernel_size", [2, 2])
            
        kernel = np.ones(kernel_size, np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def extract_text(self, img: np.ndarray, is_number: bool = False, config: dict = None) -> str:
        """Extract text using EasyOCR"""
        if img is None:
            return ""
        
        try:
            processed = self.preprocess_image(img, config)
            if processed is None:
                return ""
            
            if is_number:
                result = self.reader.readtext(processed, detail=0, allowlist='0123456789,')
            else:
                result = self.reader.readtext(processed, detail=0, paragraph=False)
            
            text = ''.join(result)
            
            # Double check for numbers if empty
            if is_number and not text.strip():
                # Try without adaptive thresholding just in case
                # Or just re-run with different settings - adhering to original logic which re-ran preprocess
                # logic from original:
                # processed = self.preprocess_image(img, adaptive=False)
                # But here I refactored preprocess to take config. 
                # I'll manually disable adaptive for retry
                retry_config = config.copy() if config else {}
                if "preprocessing" not in retry_config:
                    retry_config["preprocessing"] = {}
                retry_config["preprocessing"]["adaptive"] = False
                
                processed_retry = self.preprocess_image(img, retry_config)
                result = self.reader.readtext(processed_retry, detail=0, allowlist='0123456789,')
                text = ''.join(result)
            
            return text.strip()
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    @staticmethod
    def clean_nickname(text: str) -> str:
        """Clean nickname"""
        cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        return cleaned.strip()

    @staticmethod
    def clean_number(text: str, is_single_score: bool = False) -> int:
        """Clean and convert number"""
        cleaned = re.sub(r'[^\d]', '', text)
        
        # Fix spurious leading '1' from flame icon
        if is_single_score and cleaned and len(cleaned) == 5 and cleaned[0] == '1':
            potential_fix = cleaned[1:]
            if 1000 <= int(potential_fix) <= 9999:
                cleaned = potential_fix
        
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0
