import time, allure
from core.api.UMS import UMS
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

@allure.step("TC006 S1: Assign AVD profile, reboot, verify AVD client visible in VNC")
def TC006_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("avd_profile","AVD-Session-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("Azure",refresh_before_check=True) or
                click.is_text_present_on_screen("Virtual Desktop",refresh_before_check=True))
        logger.info(f"AVD client visible: {result}"); return result
    except Exception as e: logger.error(f"TC006_step1: {e}"); return False

@allure.step("TC006 S2: Enter Azure credentials, select workspace, verify virtual desktop")
def TC006_step2(api_config, browser):
    try:
        click.type_text(api_config.get("avd_username","")); click.press_key("Return"); time.sleep(3)
        click.type_text(api_config.get("avd_password","")); click.press_key("Return"); time.sleep(8)
        ws=api_config.get("avd_workspace_name","")
        if ws: click.click_on_text(ws); time.sleep(5)
        result=(click.is_text_present_on_screen("desktop",refresh_before_check=True) or
                click.is_text_present_on_screen("Taskbar",refresh_before_check=True))
        logger.info(f"AVD desktop loaded: {result}"); return result
    except Exception as e: logger.error(f"TC006_step2: {e}"); return False

@allure.step("TC006 S3: Logoff from AVD session")
def TC006_step3(browser):
    try:
        click.press_key_combination(["ctrl","alt","Delete"]); time.sleep(2)
        click.click_on_text("Sign out"); time.sleep(8)
        logger.info("AVD logoff attempted"); return True
    except Exception as e: logger.error(f"TC006_step3: {e}"); return False

@allure.step("TC006 Cleanup: Unassign AVD profile")
def TC006_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("avd_profile","AVD-Session-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC006_cleanup: {e}"); return False

@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC006_step1(api_config,browser_instance): assert TC006_step1(api_config,browser_instance),"AVD client not visible."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC006_step2(api_config,browser_instance): assert TC006_step2(api_config,browser_instance),"AVD desktop did not load."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC006_step3(browser_instance): assert TC006_step3(browser_instance),"AVD logoff failed."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.MINOR)
def test_TC006_cleanup(api_config): assert TC006_cleanup(api_config),"TC006 cleanup failed."
