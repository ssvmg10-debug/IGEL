"""
Shared conftest utilities for IGEL test suites.

Centralizes the duplicated patterns found across multiple conftest.py files:
  - Screenshot-on-failure Allure hook
  - Browser fixture factory (UMS login + Playwright)
  - YAML config loader
"""

import datetime
import os

import allure
import pyautogui
import yaml

from core.api.UMS import UMS
from bussiness.page_login import ums_login
from config.read_config import ums_cred, device_cred, root_path


# ------------------------------------------------------------------
# Screenshot-on-failure hook (shared implementation)
# ------------------------------------------------------------------

def allure_screenshot_on_failure(item, call, outcome, prefix="screenshot"):
    """
    Attach a screenshot to Allure when a test fails.

    Call this from a ``pytest_runtest_makereport`` hookwrapper in each
    conftest that needs failure screenshots::

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(item, call):
            outcome = yield
            allure_screenshot_on_failure(item, call, outcome, prefix="sso")
    """
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_name = f"{prefix}_{timestamp}.png"

    pyautogui.screenshot(screenshot_name)

    allure.attach.file(
        screenshot_name,
        name=f"Failure Screenshot: {item.name}",
        attachment_type=allure.attachment_type.PNG,
    )

    if os.path.exists(screenshot_name):
        os.remove(screenshot_name)


# ------------------------------------------------------------------
# Browser fixture factory
# ------------------------------------------------------------------

def make_ums_browser(api_config=None):
    """
    Create and return a logged-in UMS browser instance.

    This replaces the duplicated browser setup code found in the CIC,
    SSO, Generated, and session_connection conftest files.

    Returns:
        ums_login: An active browser instance ready for UI tests.
    """
    ums = UMS(
        ums_cred["base_url"],
        ums_cred["username"],
        ums_cred["password"],
    )
    device_details = ums.get_vm_details(device_cred["hostname"])
    shadow_url = (
        ums_cred["weburl"]
        + "/webapp/#/device-shadow/shadow/"
        + str(device_details["id"])
    )
    browser = ums_login(shadow_url, ums_cred["username"], ums_cred["password"])
    browser.start_browser()
    browser.login()
    return browser


# ------------------------------------------------------------------
# Config loader
# ------------------------------------------------------------------

def load_yaml_config(relative_path, key=None):
    """
    Load a YAML config file relative to the project root.

    Args:
        relative_path: Path segments joined with ``/`` relative to *root_path*
                       (e.g. ``"testdata/sso/api_config.yaml"``).
        key:           Optional top-level key to extract (e.g. ``"igel"``).

    Returns:
        The parsed YAML dict (or the value under *key* if provided).
    """
    config_path = os.path.join(root_path, relative_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if key is not None:
        return data[key]

    return data
