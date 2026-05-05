###########################################################
# Shadow VM EULA Automation Runner (OCR-based)
###########################################################

import sys
import time
import pyautogui
import os
from playwright.sync_api import sync_playwright

print("[BOOT] shadow_eula_runner starting", flush=True)
print("[BOOT] __file__ =", __file__, flush=True)

# --------------------------------------------------
# Force-add IGEL package root to PYTHONPATH
# --------------------------------------------------
IGEL_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

print("[BOOT] Adding to sys.path:", IGEL_ROOT, flush=True)

if IGEL_ROOT not in sys.path:
    sys.path.insert(0, IGEL_ROOT)

print("[BOOT] sys.path =", sys.path, flush=True)

from core.ui.ui_automation_text import OcrUiInteractor

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.6

# ============================================================
# TEXT CONSTANTS
# ============================================================

OPEN_EULA_TEXT = "open eula"

EULA_CHECKBOX_TEXT = (
    "By checking the box, I represent and warrant that I have the right, power, "
    "and authority to enter into the agreement on behalf of my organization"
)

# --------------------------------------------------
# Ensure project root is on PYTHONPATH
# --------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# HELPERS
# ============================================================

def force_focus():
    """Ensure Shadow window has focus"""
    time.sleep(1)
    pyautogui.click(400, 300)
    time.sleep(0.5)


# ============================================================
# EULA HANDLER
# ============================================================

class EulaOcrHandler:
    def __init__(self):
        self.ocr = OcrUiInteractor(fuzz_threshold=80)

    def try_accept_eula_once(self) -> bool:
        """
        One safe attempt to accept a single EULA.
        Returns True if something was handled.
        """

        # Click "Open EULA"
        opened = self.ocr.click_text_on_screen(
            OPEN_EULA_TEXT,
            refresh_after_click=True
        )

        if not opened:
            return False

        print("[EULA] Opened EULA", flush=True)
        time.sleep(5)

        #  Click checkbox legal text
        checked = self.ocr.click_text_on_screen(
            EULA_CHECKBOX_TEXT,
            refresh_after_click=True
        )

        if not checked:
            return False

        print("[EULA] Checkbox selected", flush=True)
        time.sleep(1)

        # TAB TAB ENTER
        pyautogui.press("tab", presses=2, interval=0.5)
        pyautogui.press("enter")

        print("[EULA] Accepted via keyboard", flush=True)
        time.sleep(4)
        return True


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 5:
        print(
            "Usage: shadow_eula_runner.py <device_id> <base_webapp_url> <username> <password>",
            flush=True,
        )
        sys.exit(1)

    device_id = sys.argv[1]
    base_url = sys.argv[2].rstrip("/")
    username = sys.argv[3]
    password = sys.argv[4]

    shadow_url = f"{base_url}/webapp/#/device-shadow/shadow/{device_id}"

    print("[SHADOW] Launching browser", flush=True)
    print(f"[SHADOW] URL: {shadow_url}", flush=True)

    pw = sync_playwright().start()

    browser = pw.chromium.launch(
        headless=False,
        args=[
            "--start-maximized",
            "--ignore-certificate-errors",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    )

    context = browser.new_context(
        no_viewport=True,
        ignore_https_errors=True,
    )

    page = context.new_page()
    page.goto(shadow_url, wait_until="networkidle", timeout=60000)

    # Force maximize
    page.evaluate(
        "() => { window.moveTo(0, 0); window.resizeTo(screen.width, screen.height); }"
    )

    # Login if required
    try:
        page.wait_for_selector(
            "css=spike-input#username >> input",
            timeout=8000
        )
        print("[SHADOW] Login page detected", flush=True)

        page.fill(
            "css=spike-input#username >> input",
            username
        )
        page.fill(
            "css=spike-password#password >> input",
            password
        )
        page.click(
            "css=spike-button#buttonLogin >> div#button-label"
        )

        page.wait_for_load_state("networkidle", timeout=15000)
        print("[SHADOW] Login successful", flush=True)

    except Exception:
        print("[SHADOW] Login not required / already logged in", flush=True)

    # Give Shadow time to fully load
    time.sleep(5)
    force_focus()

    print("[SHADOW] READY — Watching for EULAs (OCR)", flush=True)

    eula_handler = EulaOcrHandler()

    try:
        while True:
            handled = eula_handler.try_accept_eula_once()
            time.sleep(6 if handled else 2)

    except KeyboardInterrupt:
        print("[SHADOW] Interrupted", flush=True)

    finally:
        print("[SHADOW] Closing browser", flush=True)
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
