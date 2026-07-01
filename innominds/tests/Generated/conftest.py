"""
conftest.py — Fixtures for AI-Generated Test Cases

Provides the same fixtures as tests/SSO/conftest.py so that generated test files
(test_TC0XX_*.py) work without modification. Generated tests use:
  - api_config      (session scope) — loads testdata/sso/api_config.yaml["igel"]
  - browser_instance (module scope) — Playwright browser logged into UMS device shadow

## Author  : IGEL QA Automation (AI-Generated Tests)
## Version : 1.1
"""

import os

import pytest

from core.testing.conftest_helpers import (
    allure_screenshot_on_failure,
    load_yaml_config,
    make_ums_browser,
)


@pytest.fixture(scope="session")
def api_config():
    """Load API-related configuration from testdata/sso/api_config.yaml."""
    return load_yaml_config("testdata/sso/api_config.yaml", key="igel")


@pytest.fixture(scope="module")
def browser_instance(api_config):
    """Module-scoped Playwright browser session logged into UMS device shadow URL."""
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.fixture(scope="module")
def browser_cic_instance(api_config):
    """Alias fixture for tests that reference browser_cic_instance."""
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.fixture(scope="module")
def browser_cs_instance(api_config):
    """Alias fixture for tests that reference browser_cs_instance."""
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot and attach to Allure on test failure."""
    outcome = yield
    allure_screenshot_on_failure(item, call, outcome, prefix="screenshot_generated")
