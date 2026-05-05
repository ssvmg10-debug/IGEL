###########################################################
# Test Case ID : QCL-4437
# Title        : Default Browser Handling
#
# Description :
# Validate automatic default browser selection behavior.
# If no default browser is configured manually, the OS
# must automatically assign the alphabetically last
# browser as the default and also validate behavior if default browser can be configured manually
#
# Scenario :
#
# Prerequisites:
# - Fresh IGEL OS device
# - Device must be reachable via SSH
# - Device must be registered in UMS
#
# Author       : Sai Arokala
# Version      : 1.0
############################################################


import os
import time
import yaml
import sys
import subprocess
import allure
import pytest
import pyautogui
from playwright.sync_api import sync_playwright
from core.ui.ui_automation_text import OcrUiInteractor
from core.api.wums_api import UMSWUMSApi
from core.ssh.ssh_client import SSHClientIGEL
from core.utils.logger import get_logger, step_log_context
from core.utils.vnc_client import capture_vnc_screenshot

log = get_logger(__name__)


# ==========================================================
# STEP HELPERS
# ==========================================================
def step_start(step):
    log.info(f"[STEP {step} START]")


def step_end(step):
    log.info(f"[STEP {step} END]")


# ==========================================================
# YAML LOADER
# ==========================================================
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)


def load_yaml():
    yaml_path = os.path.join(PROJECT_ROOT, "testdata", "tc_qcl_data.yaml")

    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="function")
def page():
    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(
        headless=False,
        args=["--start-maximized"]
    )

    context = browser.new_context(
        ignore_https_errors=True,
        no_viewport=True
    )

    page = context.new_page()

    yield page

    context.close()
    browser.close()
    playwright.stop()


# ==========================================================
# CONTEXT FIXTURE
# ==========================================================
@pytest.fixture(scope="module")
def tc4437_context():
    data = load_yaml()

    ums_cfg = data["ums"]

    api = UMSWUMSApi(
        base_url=ums_cfg["base_url"],
        username=ums_cfg["username"],
        password=ums_cfg["password"]
    )

    return {
        "CFG": data,
        "api": api,
        "device_cfg": data["QCL_4437_device"],
        "apps": data["QCL_4437_apps"]["browser"],
        "device_id": None
    }


def get_device_id(ctx):
    if ctx.get("device_id"):
        return ctx["device_id"]

    ctx["device_id"] = ctx["api"].get_device_id(
        ctx["device_cfg"]["device_name"]
    )
    return ctx["device_id"]


# ==========================================================
# STEP 1 IMPLEMENTATION
# ==========================================================
def step1_default_browser_validation(context):
    CFG = context["CFG"]
    api = context["api"]
    dev = context["device_cfg"]
    browsers = context["apps"]

    step_start("1 Default Browser Validation")

    ssh = None

    try:

        # --------------------------------------------------
        # PRECHECK DEVICE
        # --------------------------------------------------
        with allure.step("Cleanup device if exists"):
            with step_log_context("Cleanup device if exists"):
                api.cleanup_device_if_exists(dev["device_name"])

        # --------------------------------------------------
        # REGISTER DEVICE
        # --------------------------------------------------
        with allure.step("Register device to UMS"):
            with step_log_context("Register device to UMS"):
                directory_id = api.get_directory_id(dev["target_folder"])

                api.scan_devices()
                time.sleep(20)

                api.register_device(
                    directory_id=directory_id,
                    mac=dev["mac"],
                    ip=dev["device_ip"]
                )

                time.sleep(10)

                device_id = get_device_id(context)

                log.info(f"Device registered: {device_id}")

        # --------------------------------------------------
        # ENABLE SSH / VNC
        # --------------------------------------------------
        with allure.step("Enable SSH/VNC and reboot"):

            device_id = get_device_id(context)

            api.enable_ssh_vnc(device_id)
            api.reboot_device(device_id)

            log.info("Waiting for reboot after enabling SSH/VNC")
            time.sleep(60)

        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Validate SSH connectivity"):
            with step_log_context("Validate SSH connectivity"):
                ssh = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "SSH connection failed"
                time.sleep(30)

                ssh.run_command(
                    f"igelpkgctl update",
                    timeout=1800
                )

        # --------------------------------------------------
        # INSTALL BROWSERS
        # --------------------------------------------------
        installed = []
        time.sleep(20)

        for browser in browsers:

            name = browser["name"]

            # --------------------------------------------------
            # INSTALL
            # --------------------------------------------------
            with allure.step(f"Install {name}"):

                log.info(f"[STEP 1] Installing {name}")
                time.sleep(10)

                ssh.run_command(
                    f"igelpkgctl install {name} -y",
                    timeout=1800
                )

                installed.append(name)

                time.sleep(10)

            # --------------------------------------------------
            # REBOOT
            # --------------------------------------------------
            with allure.step("Reboot device"):

                ssh.run_command("reboot")
                ssh.close()

                time.sleep(20)

            # --------------------------------------------------
            # RECONNECT SSH
            # --------------------------------------------------
            with allure.step("Reconnect SSH"):

                ssh = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "SSH reconnect failed"

                time.sleep(10)

            # --------------------------------------------------
            # CHECK DEFAULT BROWSER
            # --------------------------------------------------
            with allure.step("Check default browser"):

                default_browser = ""

                for _ in range(10):

                    _, output, _ = ssh.run_command(
                        "su user -c 'xdg-settings get default-web-browser'"
                    )

                    default_browser = output.strip().lower()

                    log.info(f"[STEP 1] Current default browser: {default_browser}")

                    if name in default_browser.lower():
                        break

                    time.sleep(4)

                allure.attach(
                    default_browser,
                    "Detected Default Browser",
                    allure.attachment_type.TEXT
                )

                priority = ["chromium", "edge", "firefox"]

                expected = "chromium"

                for browser_name in priority:
                    if browser_name in installed:
                        expected = browser_name

                assert expected in default_browser, \
                    f"Expected {expected} but got {default_browser}"

            # --------------------------------------------------
            # OPEN BROWSER
            # --------------------------------------------------
            with allure.step("Validate browser launch"):

                ssh.run_command(
                    "su - user -c \"app=\\$(xdg-settings get default-web-browser); "
                    "cmd=\\$(grep '^Exec=' /usr/share/applications/\\$app | head -n1 | cut -d= -f2 | sed 's/%u//g; s/%U//g'); "
                    "DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/777 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/777/bus setsid \\$cmd https://google.com\""
                )

                browser_detected = False

                for _ in range(6):

                    _, output, _ = ssh.run_command(
                        "su user -c 'DISPLAY=:0 wmctrl -lx'"
                    )

                    if expected in output.lower():
                        browser_detected = True
                        break

                    time.sleep(1)

                assert browser_detected, "Browser window did not appear"

                screenshot = capture_vnc_screenshot(dev["device_ip"])

                allure.attach.file(
                    screenshot,
                    name="Browser Screenshot",
                    attachment_type=allure.attachment_type.PNG
                )

                log.info(f"[STEP 1] wmctrl output:\n{output}")

                assert expected in output.lower(), \
                    f"{expected} browser window not found"

                ssh.run_command("pkill -9 -f 'chromium|edge|firefox'")

        log.info("[STEP 1] Default Browser Validation COMPLETED")

    except Exception:
        log.error("Step1 execution failed", exc_info=True)
        raise

    finally:
        log.info("[STEP 1] Cleanup")

        if ssh:
            ssh.run_command("pkill -9 -f 'chromium|edge|firefox'")
            ssh.close()

    step_end("1 Default Browser Validation")


# ==========================================================
# STEP 2: DEFAULT BROWSER CONFIGURATION
# ==========================================================
def step2_set_default_browser(context):
    api = context["api"]
    dev = context["device_cfg"]

    device_id = get_device_id(context)

    step_start("2 Manual Default Browser Validation")

    # --------------------------------------------------
    # CONNECT SSH
    # --------------------------------------------------
    ssh = SSHClientIGEL(
        host=dev["device_ip"],
        port=22,
        username="root"
    )

    assert ssh.reconnect_with_retry(
        attempts=12,
        delay_sec=15
    ), "SSH connection failed"

    # --------------------------------------------------
    # BROWSER CONFIG PAYLOADS
    # --------------------------------------------------
    browsers = [

        (
            "chromium",
            "{\"app.edge.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
            "\"app.chromium.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":true,\"type\":2}}"
        ),

        (
            "edge",
            "{\"app.chromium.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
            "\"app.edge.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":true,\"type\":2}}"
        ),

        (
            "firefox",
            "{\"app.edge.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
            "\"app.firefox.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":true,\"type\":2}}"
        )
    ]

    # --------------------------------------------------
    # LOOP THROUGH BROWSERS
    # --------------------------------------------------
    for browser_name, data_payload in browsers:
        # --------------------------------------------------
        # APPLY CONFIG USING  API METHOD
        # --------------------------------------------------
        with allure.step(f"Set {browser_name} as default via API"):
            api.update_device_configuration(
                device_id=device_id,
                data_payload=data_payload,
                send_now=True
            )

            log.info(f"[STEP2] Default browser set to {browser_name}")

            time.sleep(5)

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        with allure.step("Reboot device to apply browser config"):
            ssh.run_command("reboot")
            ssh.close()

            log.info("[STEP2] Waiting 25 seconds for reboot")
            time.sleep(25)

        # --------------------------------------------------
        # RECONNECT SSH
        # --------------------------------------------------
        with allure.step("Reconnect SSH after reboot"):
            ssh = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh.reconnect_with_retry(
                attempts=12,
                delay_sec=15
            ), "SSH reconnect failed"

            log.info("[STEP2] SSH reconnected")

            time.sleep(10)

        # --------------------------------------------------
        # VALIDATE DEFAULT BROWSER
        # --------------------------------------------------
        _, output, _ = ssh.run_command(
            "su user -c 'xdg-settings get default-web-browser'"
        )

        default_browser = output.strip().lower()

        log.info(f"[STEP2] Detected default browser: {default_browser}")

        assert browser_name in default_browser, \
            f"Expected {browser_name}, got {default_browser}"

        # --------------------------------------------------
        # OPEN TEST URL
        # --------------------------------------------------
        ssh.run_command(
            "su - user -c \"app=\\$(xdg-settings get default-web-browser); "
            "cmd=\\$(grep '^Exec=' /usr/share/applications/\\$app | head -n1 | cut -d= -f2 | sed 's/%u//g; s/%U//g'); "
            "DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/777 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/777/bus setsid \\$cmd https://google.com\""
        )

        time.sleep(5)

        # --------------------------------------------------
        # SCREENSHOT
        # --------------------------------------------------
        screenshot = capture_vnc_screenshot(dev["device_ip"])

        allure.attach.file(
            screenshot,
            name=f"{browser_name}_browser_screenshot",
            attachment_type=allure.attachment_type.PNG
        )

        # --------------------------------------------------
        # VALIDATE WINDOW
        # --------------------------------------------------
        _, output, _ = ssh.run_command(
            "su user -c 'DISPLAY=:0 wmctrl -lx'"
        )

        log.info(f"[STEP2] wmctrl output:\n{output}")

        assert browser_name in output.lower(), \
            f"{browser_name} window not detected"

        # --------------------------------------------------
        # CLOSE BROWSERS
        # --------------------------------------------------
        ssh.run_command("pkill -9 -f 'chromium|edge|firefox'")
        time.sleep(2)

    ssh.close()

    step_end("2 Manual Default Browser Validation")


# ==========================================================
# STEP 3 : MULTIPLE DEFAULT BROWSER BEHAVIOR
# ==========================================================
def step3_multiple_default_browser(context):
    api = context["api"]
    dev = context["device_cfg"]

    device_id = get_device_id(context)

    step_start("3 Multiple Default Browser Validation")

    # --------------------------------------------------
    # CONNECT SSH
    # --------------------------------------------------
    ssh = SSHClientIGEL(
        host=dev["device_ip"],
        port=22,
        username="root"
    )

    assert ssh.reconnect_with_retry(
        attempts=12,
        delay_sec=15
    ), "SSH connection failed"

    # --------------------------------------------------
    # SET MULTIPLE DEFAULT BROWSERS (NEW API METHOD ✅)
    # --------------------------------------------------
    with allure.step("Set all browsers as default via API"):

        data_payload = (
            "{\"app.chromium.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
            "\"app.firefox.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
            "\"app.edge.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":true,\"type\":2}}"
        )

        api.update_device_configuration(
            device_id=device_id,
            data_payload=data_payload,
            send_now=True
        )

        log.info("[STEP3] Multiple default browsers configured")

        time.sleep(5)

    # --------------------------------------------------
    # REBOOT DEVICE
    # --------------------------------------------------
    with allure.step("Reboot device to apply configuration"):

        ssh.run_command("reboot")
        ssh.close()

        log.info("[STEP3] Waiting 25 seconds for reboot")
        time.sleep(25)

    # --------------------------------------------------
    # RECONNECT SSH
    # --------------------------------------------------
    with allure.step("Reconnect SSH after reboot"):

        ssh = SSHClientIGEL(
            host=dev["device_ip"],
            port=22,
            username="root"
        )

        assert ssh.reconnect_with_retry(
            attempts=12,
            delay_sec=15
        ), "SSH reconnect failed"

        log.info("[STEP3] SSH reconnected")

        time.sleep(10)

    # --------------------------------------------------
    # VALIDATE DEFAULT BROWSER
    # --------------------------------------------------
    with allure.step("Validate default browser via xdg-settings"):

        _, output, _ = ssh.run_command(
            "su user -c 'xdg-settings get default-web-browser'"
        )

        default_browser = output.strip().lower()

        log.info(f"[STEP3] Default browser detected: {default_browser}")

        # Alphabetical rule → last browser = firefox
        expected_browser = "firefox"

        assert expected_browser in default_browser, \
            f"Expected firefox but got {default_browser}"

    # --------------------------------------------------
    # OPEN TEST URL
    # --------------------------------------------------
    with allure.step("Open test URL"):

        ssh.run_command(
            "su - user -c \"app=\\$(xdg-settings get default-web-browser); "
            "cmd=\\$(grep '^Exec=' /usr/share/applications/\\$app | head -n1 | cut -d= -f2 | sed 's/%u//g; s/%U//g'); "
            "DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/777 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/777/bus setsid \\$cmd https://google.com\""
        )

        time.sleep(5)

    # --------------------------------------------------
    # CAPTURE VNC SCREENSHOT
    # --------------------------------------------------
    screenshot = capture_vnc_screenshot(dev["device_ip"])

    allure.attach.file(
        screenshot,
        name="step3_firefox_browser",
        attachment_type=allure.attachment_type.PNG
    )

    # --------------------------------------------------
    # VALIDATE WINDOW MANAGER
    # --------------------------------------------------
    with allure.step("Validate browser window via wmctrl"):

        for _ in range(5):

            _, output, _ = ssh.run_command(
                "su user -c 'DISPLAY=:0 wmctrl -lx'"
            )

            if "firefox" in output.lower():
                break

            time.sleep(2)

        log.info(f"[STEP3] wmctrl output:\n{output}")

        assert "firefox" in output.lower(), \
            "Firefox window not detected"

    # --------------------------------------------------
    # CLOSE BROWSER
    # --------------------------------------------------
    ssh.run_command("pkill -9 -f 'chromium|edge|firefox'")

    ssh.close()

    step_end("3 Multiple Default Browser Validation")


# ==========================================================
# STEP 4 : ZOOM AUTHENTICATION DEFAULT BROWSER VALIDATION
# ==========================================================
def step4_zoom_default_browser(context, page):
    CFG = context["CFG"]
    api = context["api"]
    dev = context["device_cfg"]

    device_id = get_device_id(context)

    step_start("4 Zoom Default Browser Validation")

    # --------------------------------------------------
    # CONNECT SSH
    # --------------------------------------------------
    ssh = SSHClientIGEL(
        host=dev["device_ip"],
        port=22,
        username="root"
    )

    assert ssh.reconnect_with_retry(
        attempts=12,
        delay_sec=15
    ), "SSH connection failed"

    # # --------------------------------------------------
    # # SET CHROMIUM DEFAULT (NEW API METHOD)
    # # --------------------------------------------------
    with allure.step("Set Chromium as default browser via API"):

        data_payload = (
            "{\"app.chromium.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
            "\"app.firefox.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
            "\"app.edge.mimetype.default_browser\":"
            "{\"uiType\":\"bool\",\"value\":false,\"type\":2}}"
        )

        api.update_device_configuration(
            device_id=device_id,
            data_payload=data_payload,
            send_now=True
        )

        log.info("[STEP4] Chromium set as default")

        time.sleep(5)

    # --------------------------------------------------
    # INSTALL ZOOM
    # --------------------------------------------------
    with allure.step("Install Zoom"):

        ssh.run_command(
            "igelpkgctl install zoom -y",
            timeout=1800
        )

        log.info("[STEP4] Zoom installed")

        time.sleep(10)

    # --------------------------------------------------
    # REBOOT AFTER INSTALL
    # --------------------------------------------------
    ssh.run_command("reboot")
    ssh.close()

    log.info("[STEP4] Waiting for reboot")
    time.sleep(10)

    ssh = SSHClientIGEL(
        host=dev["device_ip"],
        port=22,
        username="root"
    )

    assert ssh.reconnect_with_retry(12, 15)
    time.sleep(10)

    # --------------------------------------------------
    # OPEN SHADOW SESSION
    # --------------------------------------------------

    with allure.step("Open Shadow session"):

        shadow_url = f"{CFG['shadow']['base_webapp_url']}/webapp/#/device-shadow/shadow/{device_id}"

        log.info(f"[STEP4] Opening shadow session: {shadow_url}")

        page.goto(
            shadow_url,
            timeout=90000,
            wait_until="domcontentloaded"
        )

        page.locator("input[name='username']").fill(CFG["shadow"]["username"])
        page.locator("input[name='password']").fill(CFG["shadow"]["password"])

        page.keyboard.press("Enter")

        page.wait_for_timeout(5000)
        page.wait_for_load_state("networkidle")

    # --------------------------------------------------
    # LAUNCH ZOOM
    # --------------------------------------------------
    with allure.step("Launch Zoom from desktop icon with retry"):

        ocr = OcrUiInteractor()
        zoom_clicked = False
        width = page.evaluate("window.innerWidth")
        height = page.evaluate("window.innerHeight")
        page.mouse.click(width // 2, height // 2)

        time.sleep(2)

        for attempt in range(5):
            log.info(f"[STEP4] Attempt {attempt + 1}: Clicking Zoom icon")

            zoom_clicked = (
                    ocr.click_text_on_screen_strict("Zoom", True)
                    or ocr.click_text_on_screen_strict("zoom", True)
            )

            if zoom_clicked:
                log.info("[STEP4] Zoom icon clicked successfully")
                break

            log.warning("[STEP4] Zoom icon not found, retrying in 10 seconds...")
            time.sleep(10)

        assert zoom_clicked, "Failed to click Zoom icon after 5 attempts"

    time.sleep(5)

    width = page.evaluate("window.innerWidth")
    height = page.evaluate("window.innerHeight")
    page.mouse.click(width // 2, height // 2)

    time.sleep(2)

    # --------------------------------------------------
    # OCR UI INTERACTION
    # --------------------------------------------------
    with allure.step("Zoom authentication UI flow"):

        ocr = OcrUiInteractor()

        log.info("[STEP4] Clicking Sign in")
        assert ocr.click_text_on_screen_strict("Sign in", True)

        time.sleep(5)

        log.info("[STEP4] Clicking SSO")

        page.keyboard.press("Tab")
        page.wait_for_timeout(3000)
        page.keyboard.press("Enter")

        time.sleep(5)

        log.info("[STEP4] Entering company domain")

        ocr.click_text_on_screen_strict("Company domain", True)
        time.sleep(1)

        page.keyboard.type("igel")
        time.sleep(2)

        log.info("[STEP4] Clicking Continue")

        assert ocr.click_text_on_screen_strict("Continue", True)

    # --------------------------------------------------
    # WAIT FOR REDIRECT
    # --------------------------------------------------
    time.sleep(5)

    # --------------------------------------------------
    # SCREENSHOT
    # --------------------------------------------------
    screenshot_path = "zoom_browser_redirect.png"

    page.screenshot(
        path=screenshot_path,
        full_page=True
    )

    allure.attach.file(
        screenshot_path,
        name="zoom_browser_redirect",
        attachment_type=allure.attachment_type.PNG
    )

    # --------------------------------------------------
    # VALIDATE CHROMIUM OPENED
    # --------------------------------------------------
    with allure.step("Validate browser via wmctrl"):

        for _ in range(10):

            _, output, _ = ssh.run_command(
                "su user -c 'DISPLAY=:0 wmctrl -lx'"
            )

            if "chromium" in output.lower():
                break

            time.sleep(2)

        log.info(f"[STEP4] wmctrl output:\n{output}")

        assert "chromium" in output.lower(), \
            "Chromium browser not opened during Zoom authentication"

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------
    ssh.run_command("pkill -9 -f zoom")
    ssh.run_command("pkill -9 -f chromium")

    ssh.close()

    # --------------------------------------------------
    # CLOSE PLAYWRIGHT PAGE
    # --------------------------------------------------
    with allure.step("Close Playwright session"):
        try:
            page.close()
            log.info("[STEP4] Playwright page closed")
        except Exception as e:
            log.warning(f"[STEP4] Failed to close page: {e}")

    step_end("4 Zoom Default Browser Validation")


# ==========================================================
# STEP 5 : FINAL CLEANUP (BROWSER + ZOOM + DEVICE RESET)
# ==========================================================
def step_cleanup(context):
    CFG = context["CFG"]
    api = context["api"]
    dev = context["device_cfg"]

    step_start("5 Cleanup")

    MAX_RETRIES = 3
    BACKEND_SETTLE = 40
    POST_REBOOT_SETTLE = 20

    ssh = None

    try:
        # --------------------------------------------------
        # RESOLVE DEVICE
        # --------------------------------------------------
        device_id = context.get("device_id") or api.get_device_id(dev["device_name"])
        context["device_id"] = device_id

        log.info(f"[STEP] Device ID: {device_id}")

        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        ssh = SSHClientIGEL(
            host=dev["device_ip"],
            port=22,
            username="root"
        )

        assert ssh.reconnect_with_retry(
            attempts=12,
            delay_sec=15
        ), "[STEP 5] SSH connection failed"

        # ==================================================
        # KILL RUNNING PROCESSES
        # ==================================================
        with allure.step("Kill browser & zoom processes"):

            ssh.run_command("pkill -9 -f zoom || true")
            ssh.run_command("pkill -9 -f chromium || true")
            ssh.run_command("pkill -9 -f firefox || true")
            ssh.run_command("pkill -9 -f edge || true")

            log.info("[STEP] All browser/zoom processes killed")

        # ==================================================
        # RESET DEFAULT BROWSER CONFIG
        # ==================================================
        with allure.step("Reset default browser configuration"):

            reset_payload = (
                "{"
                "\"app.chromium.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
                "\"app.firefox.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
                "\"app.edge.mimetype.default_browser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2}"
                "}"
            )

            for attempt in range(1, MAX_RETRIES + 1):

                try:
                    api.update_device_configuration(
                        device_id=device_id,
                        data_payload=reset_payload,
                        send_now=True
                    )

                    log.info("[STEP] Default browser reset applied")
                    break

                except Exception as e:
                    log.warning(f"[STEP] Reset config failed: {e}")

                    if attempt == MAX_RETRIES:
                        raise

                    time.sleep(5)

        # --------------------------------------------------
        # BACKEND SETTLE
        # --------------------------------------------------
        log.info(f"[STEP] Waiting {BACKEND_SETTLE}s for backend settle")
        time.sleep(BACKEND_SETTLE)

        # ==================================================
        # OPTIONAL: UNINSTALL APPS
        # ==================================================
        with allure.step("Uninstall browsers and zoom (optional cleanup)"):

            uninstall_list = ["chromium", "firefox", "edge", "zoom"]

            for app in uninstall_list:
                ssh.run_command(
                    f"printf 'y\\n' | igelpkgctl uninstall {app} || true"
                )

            log.info("[STEP] Uninstall commands executed")

        # ==================================================
        # REBOOT DEVICE
        # ==================================================
        with allure.step("Reboot device after cleanup"):

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(30)

        # ==================================================
        # RECONNECT SSH
        # ==================================================
        ssh = SSHClientIGEL(
            host=dev["device_ip"],
            port=22,
            username="root"
        )

        assert ssh.reconnect_with_retry(
            attempts=12,
            delay_sec=15
        ), "[STEP] SSH not reachable after cleanup reboot"

        log.info(f"[STEP] Waiting {POST_REBOOT_SETTLE}s for system settle")
        time.sleep(POST_REBOOT_SETTLE)

        # ==================================================
        # FINAL VALIDATION
        # ==================================================
        _, out, _ = ssh.run_command("igelpkgctl list installed")

        allure.attach(
            out,
            "Installed Apps After Cleanup",
            allure.attachment_type.TEXT
        )

        log.info("[STEP ] Cleanup completed successfully")

        # ==================================================
        # OPTIONAL: REMOVE DEVICE FROM UMS
        # ==================================================

    except Exception:
        log.error("[STEP] Cleanup failed", exc_info=True)
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("Cleanup")


# ==========================================================
# TEST ENTRYPOINT
# ==========================================================
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4437")
@allure.title("Step1: Default Browser Handling")
def test_QCL_4437_step01(tc4437_context):
    step1_default_browser_validation(tc4437_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4437")
@allure.title("Step2: Set Default Browser Manually")
def test_QCL_4437_step02(tc4437_context):
    step2_set_default_browser(tc4437_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4437")
@allure.title("Step3: Multiple Default Browser Behavior")
def test_QCL_4437_step03(tc4437_context):
    step3_multiple_default_browser(tc4437_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4437")
@allure.title("Step4: Zoom Default Browser Authentication")
def test_QCL_4437_step04(tc4437_context, page):
    step4_zoom_default_browser(tc4437_context, page)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4437")
@allure.title("Step: Cleanup")
def test_QCL_4437_step05(tc4437_context):
    step_cleanup(tc4437_context)
