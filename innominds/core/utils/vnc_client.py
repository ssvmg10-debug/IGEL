###########################################################
# Title        : VNC Desktop Validation Utilities
# Description  : Utilities to launch a VNC session using
#                TigerVNC Viewer and validate that expected
#                applications are visible on the IGEL
#                desktop by leveraging OCR-based screen
#                text detection.
#
# Prerequisites:
#   - Python 3.10+
#   - TigerVNC Viewer installed (Windows)
#   - core.ocr_utils
#   - core.logger.get_logger
#   - Network access to IGEL device (VNC enabled)
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.2
############################################################


import os
import subprocess
import time
from typing import List
from datetime import datetime
from pathlib import Path

from core.utils.ocr_utils import screen_contains_text
from core.utils.logger import get_logger

log = get_logger(__name__)


# ==========================================================
# FIND TIGERVNC VIEWER
# ==========================================================
def find_vnc_viewer():
    """
    Locate TigerVNC viewer on Windows.
    """

    candidates = [
        r"C:\Program Files\TigerVNC\vncviewer.exe",
        r"C:\Program Files\TigerVNC Viewer\vncviewer.exe",
        r"C:\Program Files (x86)\TigerVNC\vncviewer.exe",
        r"C:\Program Files (x86)\TigerVNC Viewer\vncviewer.exe",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError("TigerVNC viewer not found on this system")


def capture_vnc_screenshot(ip: str):
    viewer = find_vnc_viewer()

    screenshot_dir = Path("vnc_screenshots")
    screenshot_dir.mkdir(exist_ok=True)

    file = screenshot_dir / f"vnc_{datetime.now().strftime('%H%M%S')}.png"

    log.info(f"[VNC] Opening VNC for screenshot: {ip}")

    proc = subprocess.Popen([viewer, ip])

    time.sleep(5)

    import pyautogui
    image = pyautogui.screenshot()

    image.save(file)

    proc.terminate()

    log.info(f"[VNC] Screenshot saved: {file}")

    return str(file)


# ==========================================================
# OPEN VNC SESSION
# ==========================================================
def open_vnc(ip: str):
    """
    Launch TigerVNC viewer for given device IP.
    """

    viewer = find_vnc_viewer()

    log.info(f"[VNC] Using viewer: {viewer}")
    log.info(f"[VNC] Connecting to device: {ip}")

    return subprocess.Popen([viewer, ip])


# ==========================================================
# DESKTOP VALIDATION USING OCR
# ==========================================================
def validate_desktop(ip: str, app_names: List[str]):
    """
    Open VNC and verify that given application names
    appear on the desktop using OCR.
    """

    log.info("[VNC] Opening VNC for desktop validation")

    proc = open_vnc(ip)

    # allow desktop to load
    time.sleep(10)

    for app_name in app_names:

        log.info(f"[VNC] Validating '{app_name}' on desktop")

        if not screen_contains_text(app_name):
            proc.terminate()

            raise AssertionError(
                f"VNC validation FAILED – '{app_name}' not visible on desktop"
            )

    proc.terminate()

    log.info("[VNC] Desktop validation PASSED")


# ==========================================================
# PUBLIC WRAPPER USED BY TESTS
# ==========================================================
def vnc_validate_desktop(ip: str, app_names: List[str]):
    """
    Wrapper used by test cases.

    Parameters
    ----------
    ip : str
        Device IP passed from test case.

    app_names : List[str]
        List of application names expected to appear on screen.
    """
    validate_desktop(ip, app_names)
