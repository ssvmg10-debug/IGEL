import time, allure
from core.api.UMS import UMS
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

@allure.step("TC009 S1: Assign Cloud PC profile, reboot, verify launcher visible in VNC")
def TC009_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("cloudpc_profile","Windows365-CloudPC-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("Cloud PC",refresh_before_check=True) or
                click.is_text_present_on_screen("Windows 365",refresh_before_check=True))
        logger.info(f"Cloud PC launcher: {result}"); return result
    except Exception as e: logger.error(f"TC009_step1: {e}"); return False

@allure.step("TC009 S2: Launch Cloud PC, authenticate, verify Windows 365 desktop")
def TC009_step2(api_config, browser):
    try:
        click.click_on_text("Cloud PC"); time.sleep(3)
        if click.is_text_present_on_screen("Sign in",refresh_before_check=True):
            click.type_text(api_config.get("cloudpc_username","")); click.press_key("Return"); time.sleep(2)
            click.type_text(api_config.get("cloudpc_password","")); click.press_key("Return")
        time.sleep(15)
        result=(click.is_text_present_on_screen("Start",refresh_before_check=True) or
                click.is_text_present_on_screen("desktop",refresh_before_check=True))
        logger.info(f"Cloud PC desktop: {result}"); return result
    except Exception as e: logger.error(f"TC009_step2: {e}"); return False

@allure.step("TC009 S3: Disconnect from Cloud PC")
def TC009_step3(browser):
    try:
        click.press_key_combination(["ctrl","alt","Delete"]); time.sleep(2)
        click.click_on_text("Disconnect"); time.sleep(8)
        logger.info("Cloud PC disconnect attempted"); return True
    except Exception as e: logger.error(f"TC009_step3: {e}"); return False

@allure.step("TC009 Cleanup: Unassign Cloud PC profile")
def TC009_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("cloudpc_profile","Windows365-CloudPC-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC009_cleanup: {e}"); return False

@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC009_step1(api_config,browser_instance): assert TC009_step1(api_config,browser_instance),"Cloud PC launcher not visible."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC009_step2(api_config,browser_instance): assert TC009_step2(api_config,browser_instance),"Cloud PC desktop did not load."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC009_step3(browser_instance): assert TC009_step3(browser_instance),"Cloud PC disconnect failed."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.MINOR)
def test_TC009_cleanup(api_config): assert TC009_cleanup(api_config),"TC009 cleanup failed."
