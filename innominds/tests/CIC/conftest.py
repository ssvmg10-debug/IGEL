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
import sys
#-->
import logging

logging.getLogger("paramiko").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
#-->

# PROJECT_ROOT = os.path.abspath(
#     os.path.join(os.path.dirname(__file__), "../../")
#     # os.path.join(os.path.dirname(__file__), "../../")
# )
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

@pytest.fixture(scope="module")
def api_config():
    with open(os.path.join("testdata/cic", "cic_config.yaml"), "r") as f:
        api_cfg = yaml.safe_load(f)["igel"]
    return api_cfg

@pytest.fixture(scope="module")
def browser_cic_instance(api_config):
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
    outcome = yield
    report = outcome.get_result()

    # Only run for the actual test call (not setup/teardown)
    if report.when == "call" and report.failed:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"screenshot_cic_{timestamp}.png"

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
    
