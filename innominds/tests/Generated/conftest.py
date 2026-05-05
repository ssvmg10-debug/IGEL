"""
conftest.py — Fixtures for AI-Generated Test Cases

Provides the same fixtures as tests/SSO/conftest.py so that generated test files
(test_TC0XX_*.py) work without modification. Generated tests use:
  - api_config      (session scope) — loads testdata/sso/api_config.yaml["igel"]
  - browser_instance (module scope) — Playwright browser logged into UMS device shadow

## Author  : IGEL QA Automation (AI-Generated Tests)
## Version : 1.0
"""

import datetime
import os

import allure
import pyautogui
import pytest
import yaml

from bussiness.page_login import ums_login
from config.read_config import device_cred, root_path, ums_cred
from core.api.UMS import UMS


def _make_browser(api_config):
    """Shared browser factory used by all browser fixture variants."""
    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
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


@pytest.fixture(scope="session")
def api_config():
    """
    Load API-related configuration from testdata/sso/api_config.yaml.
    Returns the 'igel' sub-dict with profile names, credentials, device name, etc.
    """
    config_path = os.path.join(root_path, "testdata", "sso", "api_config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)["igel"]


@pytest.fixture(scope="module")
def browser_instance(api_config):
    """
    Module-scoped Playwright browser session logged into UMS device shadow URL.
    Yields the ums_login instance; closes browser after module tests complete.
    """
    browser = _make_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.fixture(scope="module")
def browser_cic_instance(api_config):
    """Alias fixture for tests that reference browser_cic_instance."""
    browser = _make_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.fixture(scope="module")
def browser_cs_instance(api_config):
    """Alias fixture for tests that reference browser_cs_instance."""
    browser = _make_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot and attach to Allure on test failure."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"screenshot_generated_{timestamp}.png"
        pyautogui.screenshot(screenshot_name)
        allure.attach.file(
            screenshot_name,
            name=f"Failure Screenshot: {item.name}",
            attachment_type=allure.attachment_type.PNG,
        )
        os.remove(screenshot_name)
