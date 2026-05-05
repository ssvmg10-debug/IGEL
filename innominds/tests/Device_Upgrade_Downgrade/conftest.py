import sys
import yaml
import urllib3
import os
import pytest
import allure
import urllib3

from core.utils.logger import attach_current_log_file

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# PROJECT ROOT
# ==================================================
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# ==================================================
# GLOBAL CONFIG
# ==================================================
@pytest.fixture(scope="session")
def config():
    RUNNING_ROOT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../")
    )

    config_path = os.path.join(RUNNING_ROOT, "testdata", "tc_qcl_data.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ==================================================
# PLAYWRIGHT CONTEXT
# ==================================================
@pytest.fixture(scope="function")
def context(browser):
    ctx = browser.new_context(ignore_https_errors=True)
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def browser_launch_args():
    return {"headless": True}


# ==================================================
# ATTACH FULL LOG FILE PER TEST
# ==================================================
@pytest.fixture(autouse=True)
def attach_full_log_after_test(request):
    yield
    attach_current_log_file(request.node.name)


# ==================================================
# FRESH LOG FILE PER RUN
# ==================================================
import logging
from pathlib import Path


def pytest_sessionstart(session):
    log_file = Path("reports/logs/automation.log")

    log_file.parent.mkdir(parents=True, exist_ok=True)

    for handler in logging.root.handlers[:]:
        try:
            handler.close()
        except Exception:
            pass
        logging.root.removeHandler(handler)

    if log_file.exists():
        with open(log_file, "w", encoding="utf-8"):
            pass
