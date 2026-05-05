import allure
import playwright
import pyautogui
import pytest
import time
import urllib3

from core.utils.setup_ini import OBSSetupManager
from core.utils.logger import step_log_context, get_logger
from core.ui.ui_automation_text import OcrUiInteractor
from core.api.auth_token import UMSAuthTokenService
from core.api.ums_wums_api import UMSWUMSApi

log = get_logger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==========================================================
# Helper to type special key words
# ==========================================================
def type_text_with_shift(page, text):
    """
    Types text handling special characters manually
    for VM console compatibility.
    """

    for char in text:
        if char == "_":
            page.keyboard.down("Shift")
            page.keyboard.press("-")
            page.keyboard.up("Shift")

        elif char == "@":
            page.keyboard.down("Shift")
            page.keyboard.press("2")
            page.keyboard.up("Shift")

        elif char == ".":
            page.keyboard.press(".")

        else:
            page.keyboard.type(char)

        page.wait_for_timeout(50)


def type_text_safe(page, text, delay=120):
    """
    Type text reliably inside VM console.
    Uses real keyboard events.
    """

    for char in text:
        if char.isupper():
            page.keyboard.down("Shift")
            page.keyboard.press(char.lower())
            page.keyboard.up("Shift")
        else:
            page.keyboard.type(char)

        page.wait_for_timeout(delay)


# ==========================================================
# LOCAL BROWSER FIXTURE (NO CONFTST NEEDED)
# ==========================================================
@pytest.fixture(scope="session")
def browser(playwright):
    # You actually don't need pyautogui for fullscreen here
    browser = playwright.chromium.launch(
        headless=False,
        args=["--start-maximized"],  # let Chrome decide full window
    )
    yield browser
    browser.close()


@pytest.fixture(scope="module")
def tc3117_page(browser):
    # IMPORTANT: no_viewport=True (older) or viewport=None (newer)
    context = browser.new_context(no_viewport=True)  # or viewport=None
    page = context.new_page()

    log.info("Launching FULLSCREEN browser page for TC-3117")

    yield page

    log.info("Closing browser page for TC-3117")
    context.close()


# ==========================================================
# SHARED CONTEXT
# ==========================================================

@pytest.fixture(scope="module")
def tc3117_context():
    return {
        "steps": {},
        "igel": None
    }


@pytest.fixture(scope="function")
def tc3117_api_context(playwright):
    """
    Shared state across TC-3117 steps.
    Creates separate HEADLESS browser for backend auth.
    """

    # --------------------------------------------------
    # LOAD YAML CONFIG
    # --------------------------------------------------
    config_path = Path(__file__).resolve().parents[2] / "config" / "tc_qcl_data.yaml"
    log.info(f"[CTX] Loading config from: {config_path}")

    with open(config_path, "r") as f:
        CFG = yaml.safe_load(f)

    ums_cfg = CFG["ums"]
    obs_cfg = CFG["OBS_Creds"]

    log.info("[CTX] Initializing backend auth session (HEADLESS)")

    # --------------------------------------------------
    # CREATE HEADLESS BROWSER FOR AUTH ONLY
    # --------------------------------------------------
    auth_browser = playwright.chromium.launch(
        headless=True
    )

    auth_context = auth_browser.new_context(ignore_https_errors=True)
    auth_page = auth_context.new_page()

    api = UMSWUMSApi(ums_cfg["base_url"])

    # -------------------------------
    # GET BEARER TOKEN
    # -------------------------------
    bearer = UMSAuthTokenService(auth_page).get_bearer_token(
        ums_cfg["webapp_url"],
        ums_cfg["username"],
        ums_cfg["password"],
        CFG["timeouts"]["ui_settle"]
    )

    api.set_bearer(bearer)

    # -------------------------------
    # LOGIN UMS API
    # -------------------------------
    api.login_ums_api(
        ums_cfg["username"],
        ums_cfg["password"]
    )

    auth_context.close()
    auth_browser.close()

    log.info("[CTX] Backend auth ready")

    return {
        "steps": {},
        "igel": None,
        "CFG": CFG,
        "api": api,
        "ums_cfg": ums_cfg,
        "obs_cfg": obs_cfg
    }

# ==========================================================
# STEP 0 — PRECHECK DEVICE IN UMS
# ==========================================================
def step_0_precheck_device_cleanup(context):

    log.info("STEP 0 started: Precheck device in UMS")

    try:
        api = context["api"]
        CFG = context["CFG"]

        obs_cfg = CFG["OBS_Creds"]
        device_name = obs_cfg["OBS_device_name"]

        with allure.step("Cleanup device if exists"):
            with step_log_context("Cleanup device if exists"):

                api.cleanup_device_if_exists(
                    device_name=device_name,
                    page=None,
                    ums_cfg=CFG["ums"],
                    CFG=CFG
                )

        context["steps"]["step0"] = True
        log.info("STEP 0 completed successfully")

    except Exception as e:
        context["steps"]["step0"] = False
        log.error("STEP 0 failed", exc_info=True)
        raise RuntimeError(f"STEP 0 execution failed: {e}")

# ==========================================================
# STEP 1 — LOGIN
# ==========================================================
def step_1_open_console_login(context, page):
    log.info("STEP 1 started: Open console and login")

    try:
        igel = OBSSetupManager(page)
        vm = igel.get_vmware_config()

        with allure.step("Open console and login"):
            with step_log_context("Open console and login"):
                page.goto(vm["url"], timeout=80000)

                page.locator("input[type='text']").first.fill(vm["username"])
                page.locator("input[type='password']").fill(vm["password"])
                page.keyboard.press("Enter")

                log.info("Waiting 10 seconds for console load")
                page.wait_for_timeout(10000)

                assert page.url != "about:blank"

        context["igel"] = igel
        context["steps"]["step1"] = True

    except Exception as e:
        context["steps"]["step1"] = False
        raise RuntimeError(f"STEP 1 failed: {e}")


# ==========================================================
# STEP 2 — ADD OBS to Setup.ini
# ==========================================================
def step_2_add_obs_setup_ini(context, page):
    log.info("STEP 2 started: Add QA OBS URL to setup.ini")

    try:
        # --------------------------------------------------
        # Check if step1 succeeded (informational only)
        # --------------------------------------------------
        if not context["steps"].get("step1", False):
            log.warning(
                "STEP 1 did not succeed. "
                "STEP 2 will attempt to run anyway."
            )

        # --------------------------------------------------
        # ensure IGEL manager exists
        # --------------------------------------------------
        igel = context.get("igel")

        if igel is None:
            log.error("IGEL manager not available from STEP 1")
            raise AssertionError(
                "Cannot execute STEP 2 because STEP 1 "
                "did not create IGEL session"
            )

        # rebind persistent page
        igel.page = page

        with allure.step("STEP 2 - Add QA OBS URL to setup.ini"):
            with step_log_context("Add QA OBS URL"):
                log.info("Applying OBS configuration to setup.ini")
                igel.apply_obs_configuration()

                log.info("QA OBS URL added to setup.ini successfully")

        context["steps"]["step2"] = True
        log.info("STEP 2 completed successfully")
        page.wait_for_timeout(60000)

    except AssertionError as ae:
        context["steps"]["step2"] = False
        log.error(f"STEP 2 validation failed: {ae}", exc_info=True)
        raise

    except Exception as e:
        context["steps"]["step2"] = False
        log.error("STEP 2 failed unexpectedly", exc_info=True)
        raise RuntimeError(f"STEP 2 execution failed: {e}")


# ==========================================================
# STEP 3 — DISPLAY LANGUAGE (TAB ONLY)
# ==========================================================

def step_3_select_display_language(context, page):
    log.info("STEP 3 started")

    try:
        # --------------------------------------------------
        # REFRESH BROWSER
        # --------------------------------------------------
        log.info("Refreshing browser before STEP 3")
        page.reload()
        page.wait_for_timeout(8000)

        # focus VM console
        page.mouse.click(800, 450)
        page.wait_for_timeout(1000)

        # --------------------------------------------------
        # DISPLAY LANGUAGE DROPDOWN
        # --------------------------------------------------
        log.info("Navigate to display language dropdown")

        page.keyboard.press("Tab")
        page.wait_for_timeout(800)

        log.info("Open dropdown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        log.info("Confirm selected language (default)")
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        context["steps"]["step3"] = True
        log.info("STEP 3 completed successfully")

    except Exception as e:
        context["steps"]["step3"] = False
        raise RuntimeError(f"STEP 3 failed: {e}")


# ==========================================================
# STEP 4 — KEYBOARD + CONTINUE (TAB ONLY)
# ==========================================================

def step_4_select_keyboard_and_continue(context, page):
    log.info("STEP 4 started")

    try:
        # --------------------------------------------------
        # KEYBOARD LAYOUT DROPDOWN
        # --------------------------------------------------
        log.info("Navigate to keyboard layout dropdown")

        page.keyboard.press("Tab")
        page.wait_for_timeout(800)

        log.info("Open keyboard dropdown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        log.info("Confirm selected keyboard (default)")
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        # --------------------------------------------------
        # CONTINUE BUTTON
        # --------------------------------------------------
        log.info("Navigate to Continue button")

        page.keyboard.press("Tab")
        page.wait_for_timeout(800)

        log.info("Click Continue")
        page.keyboard.press("Enter")
        page.wait_for_timeout(10000)

        context["steps"]["step4"] = True
        log.info("STEP 4 completed successfully")

    except Exception as e:
        context["steps"]["step4"] = False
        raise RuntimeError(f"STEP 4 failed: {e}")


# ==========================================================
# STEP 5 — EULA + TIMEZONE + REGION
# ==========================================================

def step_5_license_timezone_region(context, page):
    log.info("STEP 5 started: License + Timezone + Region")

    try:
        # --------------------------------------------------
        # SCREEN 1 — EULA LICENSE ACCEPT
        # --------------------------------------------------
        with allure.step("Accept EULA license"):
            with step_log_context("EULA accept"):
                log.info("Navigate to license checkbox")

                page.wait_for_timeout(500)

                log.info("Enable 'I accept the license terms'")
                page.keyboard.press("Space")

                page.wait_for_timeout(800)

                log.info("Navigate to Continue")

                page.keyboard.press("Tab")
                page.wait_for_timeout(500)
                page.keyboard.press("Tab")
                page.wait_for_timeout(500)

                log.info("Click Continue")
                page.keyboard.press("Enter")

        page.wait_for_timeout(3000)

        # --------------------------------------------------
        # SCREEN 2 — TIME ZONE AUTO DETECT
        # --------------------------------------------------
        with allure.step("Enable automatic timezone detection"):
            with step_log_context("Timezone auto detect"):
                log.info("Navigate to auto detect checkbox")

                page.keyboard.press("Tab")
                page.wait_for_timeout(500)
                page.keyboard.press("Tab")
                page.wait_for_timeout(500)

                log.info("Enable checkbox")
                page.keyboard.press("Space")

                page.wait_for_timeout(800)

                log.info("Navigate to Continue")

                page.keyboard.press("Tab")
                page.wait_for_timeout(500)
                page.keyboard.press("Tab")
                page.wait_for_timeout(500)

                log.info("Click Continue")
                page.keyboard.press("Enter")

        page.wait_for_timeout(3000)

        # --------------------------------------------------
        # SCREEN 3 — COUNTRY / REGION CONFIRM
        # --------------------------------------------------
        with allure.step("Confirm country / region"):
            with step_log_context("Region confirm"):
                ocr = OcrUiInteractor()
                log.info("Confirm region → Continue")
                ocr.click_text_on_screen_strict("Continue", True)

        page.wait_for_timeout(4000)

        context["steps"]["step5"] = True
        log.info("STEP 5 completed successfully")

    except Exception as e:
        context["steps"]["step5"] = False
        log.error("STEP 5 failed", exc_info=True)
        raise RuntimeError(f"STEP 5 execution failed: {e}")


# ==========================================================
# STEP 6 — CHECK CONNECTION STATUS (FIXED)
# ==========================================================

def step_6_check_connection_status(context, page):
    log.info("STEP 6 started: Check connection status")

    try:
        ocr = OcrUiInteractor()

        # --------------------------------------------------
        # CLICK SYSTEM INFO ICON (BOTTOM RIGHT)
        # --------------------------------------------------
        with allure.step("Open system information"):
            with step_log_context("Click info icon"):
                log.info("Clicking bottom-right info icon")

                # get REAL browser window size (works even when viewport=None)
                width = page.evaluate("window.innerWidth")
                height = page.evaluate("window.innerHeight")

                log.info(f"Browser size detected: {width} x {height}")

                # safe offset from bottom-right corner
                x = width - 60
                y = height - 60

                page.mouse.click(x, y)

        page.wait_for_timeout(3000)

        # --------------------------------------------------
        # VALIDATE INTERNET CONNECTIVITY
        # --------------------------------------------------
        with allure.step("Validate Internet connectivity"):
            internet_ok = ocr.is_text_present_on_screen(
                "Internet connectivity",
                refresh_before_check=True
            )

            true_ok = ocr.is_text_present_on_screen(
                "true",
                refresh_before_check=False
            )

            assert internet_ok and true_ok, \
                "Internet connectivity is NOT true"

            log.info("Internet connectivity = TRUE ✔")

        # --------------------------------------------------
        # VALIDATE ONBOARDING SERVICE
        # --------------------------------------------------
        with allure.step("Validate Onboarding Service"):
            onboard_text = ocr.is_text_present_on_screen(
                "Onboarding Service",
                refresh_before_check=True
            )

            reachable_text = ocr.is_text_present_on_screen(
                "reachable",
                refresh_before_check=False
            )

            assert onboard_text and reachable_text, \
                "Onboarding Service NOT reachable"

            log.info("Onboarding Service = REACHABLE ✔")

        # --------------------------------------------------
        # CLOSE POPUP
        # --------------------------------------------------
        with allure.step("Close system information popup"):
            closed = ocr.click_text_on_screen_strict(
                "Close",
                refresh_after_click=True
            )

            if not closed:
                log.warning("Close OCR failed — pressing Close with Tab")
                page.keyboard.press("Space")

        context["steps"]["step6"] = True
        log.info("STEP 6 completed successfully")

    except AssertionError as ae:
        context["steps"]["step6"] = False
        log.error(f"STEP 6 validation failed: {ae}", exc_info=True)
        raise

    except Exception as e:
        context["steps"]["step6"] = False
        log.error("STEP 6 failed unexpectedly", exc_info=True)
        raise RuntimeError(f"STEP 6 execution failed: {e}")


# ==========================================================
# STEP 7 — ONBOARD VIA EMAIL + PASSWORD LOGIN
# ==========================================================

import yaml
from pathlib import Path


def step_7_onboard_via_email(context, page):
    """
    STEP 7
    Onboard via email + Microsoft login password
    """

    log.info("STEP 7 started: Onboard via email")

    try:
        # --------------------------------------------------
        # LOAD CREDENTIALS FROM YAML
        # --------------------------------------------------
        config_path = Path(__file__).resolve().parents[2] / "config" / "tc_qcl_data.yaml"  # adjust path if needed

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        email = data["OBS_Creds"]["OBS_Email"]
        password = data["OBS_Creds"]["OBS_Password"]

        assert email, "OBS_Email missing in YAML"
        assert password, "OBS_Password missing in YAML"

        log.info(f"Using onboarding email: {email}")

        # --------------------------------------------------
        # REFRESH PAGE
        # --------------------------------------------------
        with allure.step("Refresh onboarding page"):
            log.info("Refreshing browser")
            page.reload()
            page.wait_for_timeout(10000)

        # IMPORTANT — focus VM console
        width = page.evaluate("window.innerWidth")
        height = page.evaluate("window.innerHeight")
        page.mouse.click(width // 2, height // 2)
        page.wait_for_timeout(1000)

        # --------------------------------------------------
        # ENTER EMAIL
        # --------------------------------------------------
        with allure.step("Enter email address"):
            with step_log_context("Enter email"):
                log.info("Navigate to email field")
                page.keyboard.press("Tab")
                page.wait_for_timeout(800)

                # type email safely
                log.info("Typing email")
                type_text_with_shift(page, email)
                page.wait_for_timeout(500)

        # --------------------------------------------------
        # CLICK CONTINUE
        # --------------------------------------------------
        with allure.step("Submit email"):
            with step_log_context("Click Continue"):
                for _ in range(4):
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(400)

                page.keyboard.press("Enter")

        # --------------------------------------------------
        # WAIT FOR MICROSOFT LOGIN POPUP
        # --------------------------------------------------
        log.info("Waiting for Microsoft password popup")
        page.wait_for_timeout(5000)

        # type password safely
        type_text_safe(page, password)

        page.wait_for_timeout(500)

        # navigate to Sign in
        for _ in range(3):
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)

        page.keyboard.press("Enter")

        # --------------------------------------------------
        # SIGN IN
        # --------------------------------------------------
        with allure.step("Sign in Microsoft account"):
            with step_log_context("Submit password"):
                log.info("Navigating to Sign in button")

                for _ in range(3):
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(400)

                page.keyboard.press("Space")
                page.wait_for_timeout(10000)
                page.reload()

        # --------------------------------------------------
        # WAIT FOR MICROSOFT CONSENT POPUP
        # --------------------------------------------------
        log.info("Waiting for Microsoft consent popup (Yes button)")

        ocr = OcrUiInteractor()

        popup_detected = False
        for i in range(30):  # wait up to 30 sec
            page.wait_for_timeout(1000)

            if ocr.is_text_present_on_screen("Stay signed in", True) \
                    or ocr.is_text_present_on_screen("Yes", False):
                popup_detected = True
                break

        assert popup_detected, "Microsoft consent popup did not appear"

        log.info("Consent popup detected — clicking Yes")

        # small stabilization delay (VERY IMPORTANT)
        page.wait_for_timeout(1500)

        clicked = ocr.click_text_on_screen_strict("Yes", True)
        assert clicked, "Failed to click YES on Microsoft popup"

        log.info("Clicked YES successfully")

        # allow login redirect to finish
        page.wait_for_timeout(60000)

        context["steps"]["step7"] = True
        log.info("STEP 7 completed successfully")

    except AssertionError as ae:
        context["steps"]["step7"] = False
        log.error(f"STEP 7 validation failed: {ae}", exc_info=True)
        raise

    except Exception as e:
        context["steps"]["step7"] = False
        log.error("STEP 7 failed unexpectedly", exc_info=True)
        raise RuntimeError(f"STEP 7 execution failed: {e}")


# ==========================================================
# STEP 8 — RESET TO FACTORY DEFAULTS (API)
# ==========================================================
def step_8_reset_to_factory_defaults(context, page):
    """
    STEP 8
    If device exists in UMS → Reset to factory defaults.
    Wait 60 seconds after reset.
    """

    log.info("STEP 8 started: Reset to factory defaults")

    try:
        api = context["api"]
        obs_cfg = context["obs_cfg"]

        device_name = obs_cfg["OBS_device_name"]
        device_ip = obs_cfg["OBS_device_ip"]

        log.info(f"[STEP 8] Target device: {device_name} ({device_ip})")

        # --------------------------------------------------
        # CHECK DEVICE EXISTENCE
        # --------------------------------------------------
        log.info(f"[STEP 8] Checking device in UMS: {device_name}")

        try:
            device_id = api.get_device_id(device_name)
            log.info(f"[STEP 8] Device found. ID = {device_id}")
        except Exception:
            log.info("[STEP 8] Device not present in UMS. Skipping reset.")
            context["steps"]["step8"] = True
            return

        # --------------------------------------------------
        # SEND RESET COMMAND
        # --------------------------------------------------
        log.info("[STEP 8] Sending RESET_TO_FACTORY_DEFAULTS")

        api.reset_device_to_factory(device_id)

        log.info("[STEP 8] Reset command sent successfully")

        # --------------------------------------------------
        # WAIT AFTER RESET
        # --------------------------------------------------
        RESET_WAIT = 100
        log.info(f"[STEP 8] Waiting {RESET_WAIT} seconds for reset")
        time.sleep(RESET_WAIT)

        log.info("[STEP 8] Reset command completed")

        context["steps"]["step8"] = True
        log.info("STEP 8 completed successfully")

    except AssertionError as ae:
        context["steps"]["step8"] = False
        log.error(f"STEP 8 validation failed: {ae}", exc_info=True)
        raise

    except Exception as e:
        context["steps"]["step8"] = False
        log.error("STEP 8 failed unexpectedly", exc_info=True)
        raise RuntimeError(f"STEP 8 execution failed: {e}")


# ==========================================================
# TEST EXECUTION
# ==========================================================
@pytest.mark.order(0)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 0: Precheck device in UMS")
def test_tc3117_step0(tc3117_api_context):
    step_0_precheck_device_cleanup(tc3117_api_context)
@pytest.mark.order(1)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 1: Open console and login")
def test_tc3117_step1(tc3117_context, tc3117_page):
    step_1_open_console_login(tc3117_context, tc3117_page)



@pytest.mark.order(2)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 2: Add QA OBS URL")
def test_tc3117_step2(tc3117_context, tc3117_page):
    step_2_add_obs_setup_ini(tc3117_context, tc3117_page)


@pytest.mark.order(3)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 3: Select display language")
def test_tc3117_step3(tc3117_context, tc3117_page):
    step_3_select_display_language(tc3117_context, tc3117_page)


@pytest.mark.order(4)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 4: Select keyboard layout and continue")
def test_tc3117_step4(tc3117_context, tc3117_page):
    step_4_select_keyboard_and_continue(tc3117_context, tc3117_page)


@pytest.mark.order(5)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 5: Accept license, timezone and region")
def test_tc3117_step5(tc3117_context, tc3117_page):
    step_5_license_timezone_region(tc3117_context, tc3117_page)

@pytest.mark.order(6)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 6: Check connection status")
def test_tc3117_step6(tc3117_context, tc3117_page):
    step_6_check_connection_status(tc3117_context, tc3117_page)


@pytest.mark.order(7)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 7: Onboard via email login")
def test_tc3117_step7(tc3117_context, tc3117_page):
    step_7_onboard_via_email(tc3117_context, tc3117_page)


@pytest.mark.order(8)
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3117 OBS")
@allure.title("STEP 8: Reset to factory defaults")
def test_tc3117_step8(tc3117_api_context, tc3117_page):
    step_8_reset_to_factory_defaults(tc3117_api_context, tc3117_page)
