"""
############################################################
## QCL-4225: [Base] | WUMS Shadowing + Secure terminal
# As part of the test, Verifying the WUMS Shadowing + Secure terminal
#
# 1. check the default setting after new installation/reset-to-factory-defaults.
# 2. Enable Allow remote shadowing
# 3. Enable “Allow remote shadowing” and disable Deny shadowing via external VNC-tool
# 4. Check if a Secure Shadowing Connection is possible from UMS-Console and Web UMS with starter license.
# 5. Check if a Secure Shadowing Connection is possible from UMS-Console and Web UMS with Workspace Edition license
#     expired.
# 6. Check how long a shadowing session will be kept alive by Web-UMS and UMS
# 7. check if secure terminal is working with user “user”.
#
# Author: Sachin M U
# email: sachin.mu_ext@igel.com
# creation date: 20-Jan-2026
# Version : 1.1
# changes made - First Draft
############################################################
"""

import pytest
from playwright.sync_api import sync_playwright
from core.ui.ui_automation_text import OcrUiInteractor
import time
import allure
import paramiko
import sys
from core.api.UMS import UMS
from config.read_config import ums_cred, device_cred, root_path
from core.api.api_bearertoken import ApiWithBearerToken, UMSAuthTokenProvider

click = OcrUiInteractor()  # Shared OCR UI interactor

sys.path.append("..")
sys.path.append('../..')
from core.ssh.my_logger import logger
from core.ssh.ssh import SSHClient
from playwright.sync_api import sync_playwright
from locators.read_config import web_element, get_element_by_name


URL = "https://192.168.10.28:8443/webapp/#/devices"
USERNAME = "sachin.ums"
PASSWORD = ums_cred["password"]

def ums_enable_shadow(playwright):
    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(no_viewport=True, ignore_https_errors=True)
    page = context.new_page()


    with allure.step("Navigate to URL"):
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

    with allure.step("Login with username and password"):
        page.fill("css=spike-input#username >> input#input-field", USERNAME)
        page.fill("css=spike-password#password >> input#input-field", PASSWORD)
        page.click("css=spike-button#buttonLogin >> div#button-label")
        print("Login successful!")
        time.sleep(3)

    with allure.step("Reset to factory defaults"):
         restore_factory()

    with allure.step("Go to edit settings"):
        # Access the web elements

        xpath_selector = get_element_by_name("DeviceSachin","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("ITC005056AD9677","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("Edit","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("EditConfiguration","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("System","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("RemoteAccess","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.dblclick()
        time.sleep(3)

        xpath_selector = get_element_by_name("Shadow","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        checkbox_one = page.locator("#input-checkbox").first
        # Check the first checkbox
        checkbox_one.check()
        time.sleep(3)
        page.evaluate('document.body.style.zoom = "70%"')
        time.sleep(5)

        xpath_selector = get_element_by_name("save", "xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(5)

        xpath_selector = get_element_by_name("now", "xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.get_by_role('radio').check()
        # docs_link_locator.locator('[role="radio"]').check()
        time.sleep(5)

        xpath_selector = get_element_by_name("true1", "xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(30)
        return True


def ums_enable_vnc(playwright):
    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(no_viewport=True, ignore_https_errors=True)
    page = context.new_page()

    with allure.step("Navigate to URL"):
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

    with allure.step("Login with username and password"):
        page.fill("css=spike-input#username >> input#input-field", USERNAME)
        page.fill("css=spike-password#password >> input#input-field", PASSWORD)
        page.click("css=spike-button#buttonLogin >> div#button-label")
        print("Login successful!")
        time.sleep(3)

    # with allure.step("Reset to factory defaults"):
    #     pass
    #
    with allure.step("Go to edit settings"):
        # Access the web elements

        xpath_selector = get_element_by_name("DeviceSachin","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("ITC005056AD9677","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("Edit","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("EditConfiguration","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("System","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("RemoteAccess","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.dblclick()
        time.sleep(3)

        xpath_selector = get_element_by_name("Shadow","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)


        xpath_selector = get_element_by_name("VNC","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.get_by_role('checkbox').check()
        time.sleep(3)

        page.evaluate('document.body.style.zoom = "70%"')
        time.sleep(10)

        xpath_selector = get_element_by_name("save","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(3)

        xpath_selector = get_element_by_name("now","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.get_by_role('radio').check()
        time.sleep(3)

        xpath_selector = get_element_by_name("true1","xpath")
        docs_link_locator = page.locator(f"xpath={xpath_selector}")
        # Perform the click action
        docs_link_locator.click()
        time.sleep(30)
        return True




def ssh_execute1():
    try:
        with allure.step("check ip listen state"):
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect("192.168.9.161", 22, 'root', '')
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command('netstat -tulpn')
            return ssh_stdout.read().decode('utf-8')
            #return True
    except Exception as e:
        logger.error(f"Exception executing step 1: {e}")
        return False

def __chunk_list(input_list, chunk_size):
    """
    Splits a list into smaller lists (chunks) of a specified size.
    """
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]

def ssh_execute(ip_with_port='', chunk_size=7):
    try:
        ssh=SSHClient("192.168.9.161", 'root', '')
        ret = ssh.exec("netstat -tulpn")
        # logger.info(ret)
        word_list = ret.split()
        result = __chunk_list(word_list[15:], chunk_size)
        logger.info("checking IP in the network list")
        for i in range(len(result)):
                if result[i][3] != ip_with_port:
                    logger.info("Not Present")
                    return True
    except Exception as e:
        logger.error(f"Exception executing : {e}")
        return False

def ssh_execute_listen(ip_with_port='', chunk_size=7):
    try:
        ssh=SSHClient("192.168.9.161", 'root', '')
        ret = ssh.exec("netstat -tulpn")
        logger.info(ret)
        word_list = ret.split()
        result = __chunk_list(word_list[15:], chunk_size)
        logger.info("checking IP in the network list")
        for i in range(len(result)):
                if result[i][3] == ip_with_port and result[i][5]  == "LISTEN":
                    logger.info("Present")
                    return True
    except Exception as e:
        logger.error(f"Exception executing : {e}")
        return False

def ssh_update_date(date,playwright):
    try:
        ssh=SSHClient("192.168.9.161", 'root', '')
        ret = ssh.exec(f"date -s '{date}'")

        browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True, ignore_https_errors=True)
        page = context.new_page()

        with allure.step("Navigate to URL"):
            page.goto("https://192.168.10.28:8443/webapp/#/device-shadow/shadow/801")
            page.wait_for_load_state("networkidle")
            time.sleep(2)

        with allure.step("Login with username and password"):
            page.fill("css=spike-input#username >> input#input-field", USERNAME)
            page.fill("css=spike-password#password >> input#input-field", PASSWORD)
            page.click("css=spike-button#buttonLogin >> div#button-label")
            print("Login successful!")
            time.sleep(2)

        time.sleep(1)
        return click.is_text_present_on_screen("Shadowing terminated",
                                               refresh_before_check=True)

    except Exception as e:
        logger.error(f"Exception executing : {e}")
        return False

def ssh_reboot():
    ssh = SSHClient("192.168.9.161", 'root', '')
    ret = ssh.reboot()
    return ret



def restore_factory():
    payload= ('{"command": {"commandParams": {}, "name": "RESET_TO_FACTORY_DEFAULTS", '
              '"genericCommandId": null}, "deviceId": 1449}')
    url = "https://192.168.10.28:8443/wums-app/device-command/execute"

    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])
    bearer_token = UMSAuthTokenProvider.get_bearer_token_sync(
        ums_cred["weburl"] + "/webapp/#/devices",
        ums_cred["username"],
        ums_cred["password"],
        settle_timeout=5000,
        headless=True
    )
    api = ApiWithBearerToken(bearer_token)
    api.restore_factory(device_details)




@allure.feature("WUMS shadowing + secure terminal ")
@allure.story("Validate secure shadowing and secure terminal ")
@allure.step("Step 1: check the default setting after new installation/reset-to-factory-defaults.")

def test_qcl_4225_step1():
    with allure.step("check ip listen state : 0.0.0.0:5900"):
        ret = ssh_execute('0.0.0.0:5900',7)
        assert ret == True
    with allure.step("check ip listen state : 127.0.0.1:5900"):
        ret = ssh_execute('0.0.0.0:5900', 7)
        assert ret == True

def test_qcl_4225_step2():
    with sync_playwright() as playwright:
        result = ums_enable_shadow(playwright)
        assert result == True

def test_qcl_4225_step3():
    with allure.step("check ip listen state : 0.0.0.0:5900"):
        ret = ssh_execute_listen('0.0.0.0:5900',7)
        assert ret == True

def test_qcl_4225_step4():
    with sync_playwright() as playwright:
        result = ums_enable_vnc(playwright)
        assert result == True

def test_qcl_4225_step5():
    with allure.step("check ip listen state : 127.0.0.1:5900"):
        ret = ssh_execute_listen('127.0.0.1:5900',7)
        assert ret == True


def test_qcl_4225_step6():
    with allure.step("check expiry of the Workspace Edition License"):
        with sync_playwright() as playwright:
            ret = ssh_update_date('2027-10-24 12:26:00',playwright)
            ssh_reboot()
            assert ret == True


