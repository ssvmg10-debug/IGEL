import logging
import os

import pytest
import yaml

from config.read_config import root_path
from core.testing.conftest_helpers import (
    allure_screenshot_on_failure,
    make_ums_browser,
)

logging.getLogger("paramiko").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)


@pytest.fixture(scope="module")
def api_config():
    """Load API-related configuration from 'testdata/session_connection/cs_config.yaml'."""
    with open(os.path.join(root_path, "testdata/session_connection", "cs_config.yaml"), "r") as f:
        api_cfg = yaml.safe_load(f)["igel"]
    return api_cfg


@pytest.fixture(scope="module")
def browser_cs_instance(api_config):
    """Module-scoped Playwright browser session logged into UMS device shadow URL."""
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    allure_screenshot_on_failure(item, call, outcome, prefix="screenshot_cpc")
