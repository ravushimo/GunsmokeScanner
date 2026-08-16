import os
import re
import threading
import time
from contextlib import contextmanager
from typing import Callable, List, Optional
from urllib.request import urlretrieve
from zipfile import ZipFile

import cv2
import numpy as np

# filename, bytes downloaded, total bytes (0 if unknown)
DownloadProgressCB = Callable[[str, int, int], None]
# Optional status line while EasyOCR imports / initializes (no download).
StatusCB = Callable[[str], None]


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
    import easyocr.utils as easyocr_utils

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
    """Lazy EasyOCR wrapper - CPU only. Call load() before OCR or let extract_text wait."""

    def __init__(
        self,
        languages: List[str] = None,
        *,
        load_now: bool = False,
        on_download_progress: Optional[DownloadProgressCB] = None,
        on_status: Optional[StatusCB] = None,
    ):
        if languages is None:
            languages = ["en"]
        self.languages = list(languages)
        self.use_gpu = False
        self.reader = None
        self._lock = threading.Lock()
        self._load_error: Optional[str] = None
        if load_now:
            self.load(
                on_download_progress=on_download_progress,
                on_status=on_status,
            )

    @property
    def is_ready(self) -> bool:
        return self.reader is not None

    def load(
        self,
        languages: Optional[List[str]] = None,
        on_download_progress: Optional[DownloadProgressCB] = None,
        on_status: Optional[StatusCB] = None,
    ) -> None:
        """Import EasyOCR and build the reader (may download models). Thread-safe."""
        langs = list(languages) if languages is not None else list(self.languages)
        langs = [str(x).strip() for x in langs if str(x).strip()]
        if "en" not in langs:
            langs.insert(0, "en")

        with self._lock:
            if self.reader is not None and langs == self.languages:
                return
            self._load_reader(
                langs,
                on_download_progress=on_download_progress,
                on_status=on_status,
            )

    def ensure_ready(
        self,
        on_download_progress: Optional[DownloadProgressCB] = None,
        on_status: Optional[StatusCB] = None,
    ) -> None:
        """Block until the reader is available (loads on first use if needed)."""
        if self.reader is not None:
            return
        self.load(
            on_download_progress=on_download_progress,
            on_status=on_status,
        )

    def _load_reader(
        self,
        languages: List[str],
        on_download_progress: Optional[DownloadProgressCB] = None,
        on_status: Optional[StatusCB] = None,
    ) -> None:
        def status(msg: str) -> None:
            print(msg)
            if on_status is not None:
                on_status(msg)

        self._load_error = None
        try:
            status("Importing EasyOCR...")
            import easyocr

            status("Loading EasyOCR models (CPU)...")
            print(f"EasyOCR languages: {languages}")
            self.languages = list(languages)
            self.use_gpu = False
            with _easyocr_download_progress(on_download_progress):
                self.reader = easyocr.Reader(
                    self.languages,
                    gpu=False,
                    model_storage_directory="./easyocr_models",
                    # Terminal progress goes to our UI callback when present.
                    verbose=on_download_progress is None,
                )
            status("EasyOCR ready")
            print("EasyOCR ready!")
        except Exception as e:
            self.reader = None
            self._load_error = str(e)
            print(f"EasyOCR load failed: {e}")
            raise

    def set_languages(
        self,
        languages: List[str],
        on_download_progress: Optional[DownloadProgressCB] = None,
        on_status: Optional[StatusCB] = None,
    ) -> None:
        """Rebuild the EasyOCR reader with a new language list (may download models)."""
        langs = [str(x).strip() for x in languages if str(x).strip()]
        if "en" not in langs:
            langs.insert(0, "en")
        if langs == self.languages and self.reader is not None:
            return
        self.load(
            langs,
            on_download_progress=on_download_progress,
            on_status=on_status,
        )

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
        Loads EasyOCR on first use if not already loaded.
        """
        if img is None:
            return ""

        try:
            self.ensure_ready()
            if self.reader is None:
                return ""

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
