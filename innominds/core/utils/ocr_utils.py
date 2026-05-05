###########################################################
# Title        : Screen Capture & OCR Verification Utilities
# Description  : Utility functions for capturing desktop
#                screenshots, performing OCR using
#                Tesseract, normalizing extracted text,
#                and verifying the presence of application
#                names on the screen during automated
#                UI or device validation workflows.
#
# Prerequisites:
#   - Python 3.10+
#   - Pillow (PIL)
#   - pytesseract
#   - Tesseract OCR installed and configured
#   - Windows environment (ImageGrab)
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.1
############################################################





import time
import tempfile
import os
from PIL import ImageGrab, Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace(".", "")
        .replace("\n", " ")
        .strip()
    )


def derive_keywords_from_app_name(app_name: str) -> list[str]:
    cleaned = normalize_text(app_name)
    tokens = cleaned.split()
    keywords = [t for t in tokens if len(t) >= 3]
    return keywords or [cleaned]


def capture_screen() -> str:
    time.sleep(5)
    img = ImageGrab.grab()
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    return path


def screen_contains_text(app_name: str, retries: int = 5, delay: int = 3) -> bool:
    keywords = derive_keywords_from_app_name(app_name)

    for attempt in range(1, retries + 1):
        screenshot = capture_screen()
        ocr_text = pytesseract.image_to_string(Image.open(screenshot))
        norm_ocr = normalize_text(ocr_text)

        for keyword in keywords:
            if keyword in norm_ocr:
                return True

        print(
            f"[OCR] Retry {attempt}/{retries} – "
            f"'{app_name}' not detected yet (keywords={keywords})"
        )
        time.sleep(delay)

    return False
