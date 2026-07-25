import os
import re
import time
from contextlib import contextmanager
from typing import Callable, List, Optional, Tuple
from urllib.request import urlretrieve
from zipfile import ZipFile

import cv2
import easyocr
import easyocr.utils as easyocr_utils
import numpy as np

# filename, bytes downloaded, total bytes (0 if unknown)
DownloadProgressCB = Callable[[str, int, int], None]


def format_byte_size(n: int) -> str:
    """Human-readable size for download progress (e.g. 512 KB, 28.1 MB)."""
    n = max(0, int(n))
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    if n < 1024 * 1024 * 1024:
        mb = n / (1024 * 1024)
        return f"{mb:.1f} MB" if mb < 10 else f"{mb:.0f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def detect_ocr_device() -> Tuple[bool, str]:
    """Return (use_gpu, human-readable device label).

    Also smoke-tests a tiny CUDA tensor so an incompatible wheel (wrong
    compute capability) falls back to CPU instead of crashing mid-OCR.
    """
    try:
        import torch

        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            name = torch.cuda.get_device_name(0)
            try:
                torch.zeros(1, device="cuda")
            except Exception as e:
                return False, f"CPU (CUDA present but unusable on {name}: {e})"
            return True, f"CUDA ({name})"
        build = getattr(torch.version, "cuda", None)
        if build is None:
            return False, "CPU (torch is CPU-only build - run scripts/ensure_torch.py)"
        return False, "CPU (CUDA build present but no GPU visible)"
    except Exception as e:
        return False, f"CPU (torch check failed: {e})"


@contextmanager
def _easyocr_download_progress(on_progress: Optional[DownloadProgressCB]):
    """Route EasyOCR model downloads through on_progress instead of a console bar.

    EasyOCR binds ``download_and_unzip`` into ``easyocr.easyocr`` at import time,
    so both that module and ``easyocr.utils`` must be patched.
    """
    if on_progress is None:
        yield
        return

    import easyocr.easyocr as easyocr_main

    original_utils = easyocr_utils.download_and_unzip
    original_main = getattr(easyocr_main, "download_and_unzip", original_utils)

    def patched(url, filename, model_storage_directory, verbose=True):
        zip_path = os.path.join(model_storage_directory, "temp.zip")
        label = os.path.basename(str(filename)) or "model"
        last_emit = [0.0]
        last_bytes = [-1]

        def reporthook(count, block_size, total_size):
            downloaded = count * block_size
            if total_size and total_size > 0:
                downloaded = min(downloaded, total_size)
            else:
                total_size = 0
            now = time.monotonic()
            # Throttle UI churn; always emit first update and completion.
            if downloaded != last_bytes[0] and (
                last_bytes[0] < 0
                or now - last_emit[0] >= 0.15
                or (total_size and downloaded >= total_size)
            ):
                last_emit[0] = now
                last_bytes[0] = downloaded
                on_progress(label, downloaded, total_size)

        # Suppress EasyOCR's terminal progress bar; UI owns progress.
        urlretrieve(url, zip_path, reporthook=reporthook)
        with ZipFile(zip_path, "r") as zip_obj:
            zip_obj.extract(filename, model_storage_directory)
        os.remove(zip_path)
        done = last_bytes[0] if last_bytes[0] > 0 else 0
        on_progress(label, done, done if done else 0)

    easyocr_utils.download_and_unzip = patched
    easyocr_main.download_and_unzip = patched
    try:
        yield
    finally:
        easyocr_utils.download_and_unzip = original_utils
        easyocr_main.download_and_unzip = original_main


class OCRProcessor:
    def __init__(
        self,
        languages: List[str] = None,
        on_download_progress: Optional[DownloadProgressCB] = None,
    ):
        if languages is None:
            languages = ["en"]
        self.languages = list(languages)
        self.use_gpu = False
        self.reader = None
        self._load_reader(self.languages, on_download_progress=on_download_progress)

    def _load_reader(
        self,
        languages: List[str],
        on_download_progress: Optional[DownloadProgressCB] = None,
    ) -> None:
        use_gpu, device_label = detect_ocr_device()
        print("Loading EasyOCR models...")
        print(f"EasyOCR languages: {languages}")
        print(f"EasyOCR device: {device_label}")
        self.use_gpu = use_gpu
        self.languages = list(languages)
        with _easyocr_download_progress(on_download_progress):
            self.reader = easyocr.Reader(
                self.languages,
                gpu=use_gpu,
                model_storage_directory="./easyocr_models",
                # Terminal progress goes to our UI callback when present.
                verbose=on_download_progress is None,
            )
        print("EasyOCR ready!")

    def set_languages(
        self,
        languages: List[str],
        on_download_progress: Optional[DownloadProgressCB] = None,
    ) -> None:
        """Rebuild the EasyOCR reader with a new language list (may download models)."""
        langs = [str(x).strip() for x in languages if str(x).strip()]
        if "en" not in langs:
            langs.insert(0, "en")
        if langs == self.languages and self.reader is not None:
            return
        self._load_reader(langs, on_download_progress=on_download_progress)

    def preprocess_image(
        self, img: np.ndarray, config: dict = None
    ) -> Optional[np.ndarray]:
        """Preprocess image for OCR"""
        if img is None or img.size == 0:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        adaptive = True
        if config and "preprocessing" in config:
            adaptive = config["preprocessing"].get("adaptive", True)

        if adaptive:
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
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

    def extract_text(
        self,
        img: np.ndarray,
        is_number: bool = False,
        config: dict = None,
        allowlist: str = None,
    ) -> str:
        """Extract text using EasyOCR.

        `allowlist` restricts characters when set (e.g. timestamps / page digits).
        """
        if img is None:
            return ""

        try:
            processed = self.preprocess_image(img, config)
            if processed is None:
                return ""

            if allowlist is not None:
                result = self.reader.readtext(
                    processed, detail=0, allowlist=allowlist
                )
            elif is_number:
                result = self.reader.readtext(
                    processed, detail=0, allowlist="0123456789,"
                )
            else:
                result = self.reader.readtext(processed, detail=0, paragraph=False)

            text = "".join(result)

            # Double check for numbers if empty
            if is_number and not text.strip() and allowlist is None:
                retry_config = config.copy() if config else {}
                if "preprocessing" not in retry_config:
                    retry_config["preprocessing"] = {}
                retry_config["preprocessing"]["adaptive"] = False

                processed_retry = self.preprocess_image(img, retry_config)
                result = self.reader.readtext(
                    processed_retry, detail=0, allowlist="0123456789,"
                )
                text = "".join(result)

            return text.strip()
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    @staticmethod
    def clean_nickname(text: str) -> str:
        """Clean nickname"""
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
        return cleaned.strip()

    @staticmethod
    def clean_number(text: str, is_single_score: bool = False) -> int:
        """Clean and convert number"""
        cleaned = re.sub(r"[^\d]", "", text)

        # Fix spurious leading '1' from flame icon
        if is_single_score and cleaned and len(cleaned) == 5 and cleaned[0] == "1":
            potential_fix = cleaned[1:]
            if 1000 <= int(potential_fix) <= 9999:
                cleaned = potential_fix

        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0
