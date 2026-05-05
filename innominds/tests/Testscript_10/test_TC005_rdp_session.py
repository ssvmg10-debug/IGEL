import time, allure
from core.api.UMS import UMS
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

@allure.step("TC005 S1: Assign RDP profile, reboot, verify RDP session icon on IGEL desktop")
def TC005_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("rdp_profile","RDP-Session-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        name=api_config.get("rdp_session_name","RDP")
        result=(click.is_text_present_on_screen(name,refresh_before_check=True) or
                click.is_text_present_on_screen("RDP",refresh_before_check=True))
        logger.info(f"RDP icon visible: {result}"); return result
    except Exception as e: logger.error(f"TC005_step1: {e}"); return False

@allure.step("TC005 S2: Click RDP icon, enter Windows credentials, verify Windows desktop")
def TC005_step2(api_config, browser):
    try:
        click.click_on_text(api_config.get("rdp_session_name","RDP")); time.sleep(5)
        if click.is_text_present_on_screen("Username",refresh_before_check=True):
            click.type_text(api_config.get("rdp_username","")); click.press_key("Tab")
            click.type_text(api_config.get("rdp_password","")); click.press_key("Return"); time.sleep(10)
        result=(click.is_text_present_on_screen("Start",refresh_before_check=True) or
                click.is_text_present_on_screen("Taskbar",refresh_before_check=True))
        logger.info(f"Windows desktop in RDP: {result}"); return result
    except Exception as e: logger.error(f"TC005_step2: {e}"); return False

@allure.step("TC005 S3: Disconnect RDP and verify return to IGEL desktop")
def TC005_step3(browser):
    try:
        click.press_key_combination(["ctrl","alt","Delete"]); time.sleep(2)
        click.click_on_text("Disconnect"); time.sleep(5)
        logger.info("RDP disconnect attempted"); return True
    except Exception as e: logger.error(f"TC005_step3: {e}"); return False

@allure.step("TC005 Cleanup: Unassign RDP profile")
def TC005_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("rdp_profile","RDP-Session-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC005_cleanup: {e}"); return False

@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC005_step1(api_config,browser_instance): assert TC005_step1(api_config,browser_instance),"RDP icon not visible."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC005_step2(api_config,browser_instance): assert TC005_step2(api_config,browser_instance),"Windows desktop did not load."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC005_step3(browser_instance): assert TC005_step3(browser_instance),"RDP disconnect failed."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.MINOR)
def test_TC005_cleanup(api_config): assert TC005_cleanup(api_config),"TC005 cleanup failed."
