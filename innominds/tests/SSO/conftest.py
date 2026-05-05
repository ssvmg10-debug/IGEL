"""
conftest.py

Pytest configuration file for UI tests.

Contains fixtures and hooks used across UI tests in the framework. 

Fixtures:
    - device_config: Loads device-specific configuration from YAML.
    - api_config: Loads API-related configuration from YAML.
    - browser_instance: Starts a Playwright browser, performs login, and provides a reusable browser session.

Hooks:
    - pytest_runtest_makereport: Captures a screenshot on test failure and attaches it to Allure reports.

## Author       : Pooja Swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 16-Jan-2026
## Version      : 1.0
"""

import os
import yaml
import pytest
import time
import allure
import pytest
import pyautogui
import allure
import datetime
from core.api.UMS import UMS
from bussiness.page_login import ums_login
from config.read_config import ums_cred, device_cred, root_path


@pytest.fixture(scope="session")
def api_config():
    """
    Load API-related configuration from 'testdata/sso/api_config.yaml'.

    Returns:
        dict: Configuration details for API tests (base URLs, credentials, etc.).
    """
    with open(os.path.join(root_path, "testdata/sso", "api_config.yaml"), "r") as f:
        api_cfg = yaml.safe_load(f)["igel"]
    return api_cfg


@pytest.fixture(scope="module")
def browser_instance(api_config):
    """
    Start a Playwright browser session and perform login.

    Uses the device configuration fixture for credentials and URL.

    Yields:
        ums_login: An active browser instance ready for UI tests.

    Cleanup:
        Closes the browser after all tests in the session are complete.
    """
    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])
    browser = ums_login(

        ums_cred["weburl"]+"/webapp/#/device-shadow/shadow/"+str(device_details['id']),

        ums_cred["username"],

        ums_cred["password"],

    )
    browser.start_browser()
    browser.login()
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to take a screenshot and attach it to Allure if a test fails.
    """
    outcome = yield
    report = outcome.get_result()

    # Only run for the actual test call (not setup/teardown)
    if report.when == "call" and report.failed:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"screenshot_{timestamp}.png"

        # Take screenshot
        pyautogui.screenshot(screenshot_name)

        # Attach to Allure
        allure.attach.file(
            screenshot_name,
            name=f"Failure Screenshot: {item.name}",
            attachment_type=allure.attachment_type.PNG
        )

        print(f"[Allure] Screenshot captured for failed test: {screenshot_name}")

        # Optional: clean up the screenshot after attaching
        import os; os.remove(screenshot_name)
    
