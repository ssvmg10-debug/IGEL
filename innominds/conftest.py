import os
import sys

import pytest
import yaml

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Make project root importable
# ==================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ==================================================
# Global config fixture
# ==================================================
@pytest.fixture(scope="session")
def config():
    config_path = os.path.join(PROJECT_ROOT, "config", "tc3119.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ==================================================
# Playwright context with HTTPS ignored
# ==================================================
@pytest.fixture(scope="function")
def context(browser):
    context = browser.new_context(
        ignore_https_errors=True
    )
    yield context
    context.close()


# ==================================================
# Page fixture (OVERRIDES default)
# ==================================================





