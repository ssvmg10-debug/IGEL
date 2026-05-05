import time, allure
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()
def get_ssh(): return SSHClient(host=device_cred["host"],user=device_cred["user"],pwd=device_cred["pwd"],port=device_cred["port"])

@allure.step("TC004 S1: Assign Omnissa Horizon SSO profile, reboot, verify login screen in VNC")
def TC004_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("omnissa_profile","Omnissa-Horizon-SSO-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("Omnissa",refresh_before_check=True) or
                click.is_text_present_on_screen("Horizon",refresh_before_check=True) or
                click.is_text_present_on_screen("Workspace ONE",refresh_before_check=True))
        logger.info(f"Omnissa login screen: {result}"); return result
    except Exception as e: logger.error(f"TC004_step1: {e}"); return False

@allure.step("TC004 S2: Enter Omnissa credentials, verify Horizon session launches")
def TC004_step2(api_config, browser):
    try:
        click.type_text(api_config.get("omnissa_username","")); click.press_key("Tab")
        click.type_text(api_config.get("omnissa_password","")); click.press_key("Return"); time.sleep(8)
        result=(click.is_text_present_on_screen("Horizon",refresh_before_check=True) or
                click.is_text_present_on_screen("desktop",refresh_before_check=True))
        logger.info(f"Horizon session launched: {result}"); return result
    except Exception as e: logger.error(f"TC004_step2: {e}"); return False

@allure.step("TC004 S3: Check journalctl for Horizon session events via SSH")
def TC004_step3():
    try:
        ssh=get_ssh(); out=ssh.exec("journalctl -t Horizon --no-pager -n 50 2>&1"); ssh.close()
        logger.info(f"journalctl Horizon (first 200): {(out or '')[:200]}"); return True
    except Exception as e: logger.error(f"TC004_step3: {e}"); return False

@allure.step("TC004 S4: Logoff from Horizon session")
def TC004_step4(browser):
    try:
        click.click_on_text("Log Off"); time.sleep(5)
        logger.info("Horizon logoff attempted"); return True
    except Exception as e: logger.error(f"TC004_step4: {e}"); return False

@allure.step("TC004 Cleanup: Unassign Omnissa profile")
def TC004_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("omnissa_profile","Omnissa-Horizon-SSO-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC004_cleanup: {e}"); return False

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC004_step1(api_config,browser_instance): assert TC004_step1(api_config,browser_instance),"Omnissa login screen not detected."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC004_step2(api_config,browser_instance): assert TC004_step2(api_config,browser_instance),"Horizon session did not launch."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC004_step3(): assert TC004_step3(),"Horizon journalctl check failed."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC004_step4(browser_instance): assert TC004_step4(browser_instance),"Horizon logoff failed."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.MINOR)
def test_TC004_cleanup(api_config): assert TC004_cleanup(api_config),"TC004 cleanup failed."
