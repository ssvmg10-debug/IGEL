import logging
import os

import pytest
import yaml

from core.testing.conftest_helpers import (
    allure_screenshot_on_failure,
    make_ums_browser,
)

logging.getLogger("paramiko").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)


@pytest.fixture(scope="module")
def api_config():
    with open(os.path.join("testdata/cic", "cic_config.yaml"), "r") as f:
        api_cfg = yaml.safe_load(f)["igel"]
    return api_cfg


@pytest.fixture(scope="module")
def browser_cic_instance(api_config):
    browser = make_ums_browser(api_config)
    yield browser
    browser.close_browser()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    allure_screenshot_on_failure(item, call, outcome, prefix="screenshot_cic")
