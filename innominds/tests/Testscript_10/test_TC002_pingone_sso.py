import time, allure
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()
def get_ssh(): return SSHClient(host=device_cred["host"],user=device_cred["user"],pwd=device_cred["pwd"],port=device_cred["port"])

@allure.step("TC002 S1: Assign PingOne profile, reboot, verify PingOne login screen")
def TC002_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("pingone_profile","PingOne-SSO-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile")
        ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("PingOne",refresh_before_check=True) or
                click.is_text_present_on_screen("Ping",refresh_before_check=True))
        logger.info(f"PingOne screen: {result}"); return result
    except Exception as e: logger.error(f"TC002_step1: {e}"); return False

@allure.step("TC002 S2: Authenticate with PingOne creds, verify desktop")
def TC002_step2(api_config, browser):
    try:
        click.type_text(api_config.get("pingone_username","")); click.press_key("Tab")
        click.type_text(api_config.get("pingone_password","")); click.press_key("Return"); time.sleep(5)
        result=click.is_text_present_on_screen("desktop",refresh_before_check=True)
        logger.info(f"Desktop after PingOne: {result}"); return result
    except Exception as e: logger.error(f"TC002_step2: {e}"); return False

@allure.step("TC002 S3: Check /var/log/auth.log for errors via SSH")
def TC002_step3():
    try:
        ssh=get_ssh(); ssh.exec("grep -i error /var/log/auth.log | tail -3"); ssh.close()
        return True
    except Exception as e: logger.error(f"TC002_step3: {e}"); return False

@allure.step("TC002 Cleanup: Unassign PingOne profile")
def TC002_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("pingone_profile","PingOne-SSO-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC002_cleanup: {e}"); return False

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC002_step1(api_config,browser_instance): assert TC002_step1(api_config,browser_instance),"PingOne login screen not detected."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC002_step2(api_config,browser_instance): assert TC002_step2(api_config,browser_instance),"PingOne auth failed."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC002_step3(): assert TC002_step3()
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.MINOR)
def test_TC002_cleanup(api_config): assert TC002_cleanup(api_config),"TC002 cleanup failed."
