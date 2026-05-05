import time, allure
from core.api.UMS import UMS
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

@allure.step("TC008 S1: Assign Citrix StoreFront + cert profiles, reboot, verify Citrix login screen")
def TC008_step1(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("citrix_profile","Citrix-StoreFront-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile")
        cp=api_config.get("citrix_cert_profile","")
        if cp:
            cprof=ums.get_profile_details(cp); wums.assign_object(dev["id"],cprof["id"],"profile")
        ums.device_reboot(dev); time.sleep(90)
        result=(click.is_text_present_on_screen("Citrix",refresh_before_check=True) or
                click.is_text_present_on_screen("StoreFront",refresh_before_check=True))
        logger.info(f"Citrix login screen: {result}"); return result
    except Exception as e: logger.error(f"TC008_step1: {e}"); return False

@allure.step("TC008 S2: Enter QA credentials, verify Citrix app catalog loads")
def TC008_step2(api_config, browser):
    try:
        dom=api_config.get("citrix_domain","")
        user=api_config.get("citrix_username","")
        click.type_text((dom+"\\"+user) if dom else user); click.press_key("Tab")
        click.type_text(api_config.get("citrix_password","")); click.press_key("Return"); time.sleep(8)
        result=(click.is_text_present_on_screen("Apps",refresh_before_check=True) or
                click.is_text_present_on_screen("Favorites",refresh_before_check=True))
        logger.info(f"Citrix catalog visible: {result}"); return result
    except Exception as e: logger.error(f"TC008_step2: {e}"); return False

@allure.step("TC008 S3: Launch published app from Citrix catalog")
def TC008_step3(api_config, browser):
    try:
        app=api_config.get("citrix_published_app","Notepad")
        click.click_on_text(app); time.sleep(10)
        result=click.is_text_present_on_screen(app,refresh_before_check=True)
        logger.info(f"Published app launched: {result}"); return result
    except Exception as e: logger.error(f"TC008_step3: {e}"); return False

@allure.step("TC008 S4: Logoff from Citrix session")
def TC008_step4(browser):
    try:
        click.click_on_text("Log Off"); time.sleep(5)
        logger.info("Citrix logoff attempted"); return True
    except Exception as e: logger.error(f"TC008_step4: {e}"); return False

@allure.step("TC008 Cleanup: Unassign Citrix and cert profiles")
def TC008_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("citrix_profile","Citrix-StoreFront-Profile"))
        wums.detach_profile(dev["id"],prof["id"])
        cp=api_config.get("citrix_cert_profile","")
        if cp:
            cprof=ums.get_profile_details(cp); wums.detach_profile(dev["id"],cprof["id"])
        ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC008_cleanup: {e}"); return False

@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC008_step1(api_config,browser_instance): assert TC008_step1(api_config,browser_instance),"Citrix login screen not detected."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC008_step2(api_config,browser_instance): assert TC008_step2(api_config,browser_instance),"Citrix catalog not loaded."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC008_step3(api_config,browser_instance): assert TC008_step3(api_config,browser_instance),"Published app did not launch."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC008_step4(browser_instance): assert TC008_step4(browser_instance),"Citrix logoff failed."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.MINOR)
def test_TC008_cleanup(api_config): assert TC008_cleanup(api_config),"TC008 cleanup failed."
