import time, allure
from core.api.UMS import UMS
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

@allure.step("TC003 S1: Assign Okta SSO profile (short timeout), reboot, verify Okta login screen")
def TC003_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("okta_profile","Okta-SSO-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile")
        ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("Okta",refresh_before_check=True) or
                click.is_text_present_on_screen("Sign In",refresh_before_check=True))
        logger.info(f"Okta login screen: {result}"); return result
    except Exception as e: logger.error(f"TC003_step1: {e}"); return False

@allure.step("TC003 S2: Authenticate with Okta credentials")
def TC003_step2(api_config, browser):
    try:
        click.type_text(api_config.get("okta_username","")); click.press_key("Tab")
        click.type_text(api_config.get("okta_password","")); click.press_key("Return"); time.sleep(5)
        result=click.is_text_present_on_screen("desktop",refresh_before_check=True)
        logger.info(f"Desktop after Okta: {result}"); return result
    except Exception as e: logger.error(f"TC003_step2: {e}"); return False

@allure.step("TC003 S3: Wait for session timeout, verify re-auth prompt (screenlock or login page)")
def TC003_step3(api_config):
    try:
        t=api_config.get("okta_session_timeout_seconds",120)
        logger.info(f"Waiting {t}s for Okta session expiry…"); time.sleep(t+15)
        locked=click.is_text_present_on_screen("locked",refresh_before_check=True)
        signin=click.is_text_present_on_screen("Sign In",refresh_before_check=True)
        logger.info(f"Re-auth prompt: locked={locked} signin={signin}"); return locked or signin
    except Exception as e: logger.error(f"TC003_step3: {e}"); return False

@allure.step("TC003 S4: Re-authenticate and verify session restored")
def TC003_step4(api_config, browser):
    try:
        click.type_text(api_config.get("okta_username","")); click.press_key("Tab")
        click.type_text(api_config.get("okta_password","")); click.press_key("Return"); time.sleep(5)
        result=click.is_text_present_on_screen("desktop",refresh_before_check=True)
        logger.info(f"Session restored after re-auth: {result}"); return result
    except Exception as e: logger.error(f"TC003_step4: {e}"); return False

@allure.step("TC003 Cleanup: Unassign Okta profile")
def TC003_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("okta_profile","Okta-SSO-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC003_cleanup: {e}"); return False

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC003_step1(api_config,browser_instance): assert TC003_step1(api_config,browser_instance),"Okta login screen not detected."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC003_step2(api_config,browser_instance): assert TC003_step2(api_config,browser_instance),"Okta initial auth failed."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC003_step3(api_config): assert TC003_step3(api_config),"Re-auth prompt not shown after Okta timeout."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC003_step4(api_config,browser_instance): assert TC003_step4(api_config,browser_instance),"Session not restored after re-auth."
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.MINOR)
def test_TC003_cleanup(api_config): assert TC003_cleanup(api_config),"TC003 cleanup failed."
