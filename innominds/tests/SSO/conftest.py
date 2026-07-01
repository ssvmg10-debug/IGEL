"""
conftest.py

Pytest configuration file for SSO UI tests.

Fixtures:
    - api_config: Loads API-related configuration from YAML.
    - browser_instance: Starts a Playwright browser, performs login, and provides a reusable browser session.

Hooks:
    - pytest_runtest_makereport: Captures a screenshot on test failure and attaches it to Allure reports.

## Author       : Pooja Swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 16-Jan-2026
## Version      : 1.1
"""

import pytest

from core.testing.conftest_helpers import (
    allure_screenshot_on_failure,
    load_yaml_config,
    make_ums_browser,
)


@pytest.fixture(scope="session")
def api_config():
    """Load API-related configuration from 'testdata/sso/api_config.yaml'."""
    return load_yaml_config("testdata/sso/api_config.yaml", key="igel")


@pytest.fixture(scope="module")
def browser_instance(api_config):
    """Module-scoped Playwright browser session logged into UMS device shadow URL."""
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot and attach to Allure on test failure."""
    outcome = yield
    allure_screenshot_on_failure(item, call, outcome, prefix="screenshot_sso")
