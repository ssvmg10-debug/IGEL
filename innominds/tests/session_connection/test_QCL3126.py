"""
############################################################
## Test Case ID : QCL-3126
## Title        : Connection | Citrix Storefront/Selfservice
##
## Description:
# Validates Citrix Storefront and self service session connection, 
# application launch, and logoff functionality for citrix application.
#
## Prerequisites:
# - certificate need to be installed on the device.
#
## Test Scope:
# - Assign UMS profile to the device
# - Verify successful SSO login
# - Validate behavior without internet connectivity
# - Verify screen lock enabled and disabled scenarios
# - Validate auto-login functionality
#
## Author       : Pooja Swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 17-Feb-2026
## Version      : 1.0
############################################################
"""

import time
import pyautogui
import allure
import pytest
from core.api.UMS import UMS
from core.ssh import ssh
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from bussiness.page_login import ums_login
from core.api.auth_token import UMSAuthTokenService
from config.read_config import ums_cred, device_cred, otp_secrets_cred
from core.ssh.my_logger import logger
from core.utils.logger import logging
from core.api.ums_wums_api import UMSWUMSApi
from tests.session_connection.conftest import api_config

click = OcrUiInteractor()  # Shared OCR UI interactor


# ------------------------
# Helpers
# ------------------------
def get_ssh():
    """Return SSH client for the given device config."""
    return SSHClient(
        host=device_cred["host"],             # host
        user=device_cred["user"], # user (required)
        pwd = device_cred["pwd"],
        port = device_cred["port"]
    )


# ------------------------
# Step functions
# ------------------------
@allure.step("Step 1: Assign profile and verify password screen")
def QCL_3126_step1(api_config, browser):
    """ 
        Assigns the Entra ID SSO UMS profile to the device (if required) 
        and verifies the Microsoft password screen.  
        Returns: 
            bool: True if the password screen is detected, else False. 
    """
    logging.info("Starting Step 1: Assign profile and verify password screen")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        page = browser.page
        target_hash_url = ums_cred["weburl"]+"/webapp/#/device-shadow/shadow/"+str(device_details['id'])

        bearer_token = UMSAuthTokenService(page).get_bearer_token(
                ums_cred["weburl"]+"/webapp/",
                ums_cred["username"],
                ums_cred["password"],
                settle_timeout=5000,
                
            )
        page.goto(target_hash_url, wait_until="load")
        logger.info("page goto target")
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        cert= api_config["certificate_profile_citrix"]
        file_id = api.get_file_details(cert)
        api.assign_files(device_details["id"], file_id)
        
        
        # profile_details = api.get_installed_app_id("Citrix Workspace App")
        # api.assign_app(device_details["id"], profile_details)
        profile_details = ums.get_profile_details( api_config["profile_citrix"])

        api.assign_profile(device_details["id"], profile_details["id"])
        if click.click_text_on_screen("restart now", refresh_after_click=True, timeout=30):

            logging.info("Clicked on 'restart now' prompt")
        else:
            found_text_ok = click.click_text_on_screen("ok", refresh_after_click=True)
            
        if ssh := get_ssh():
            ssh.reboot()
        return click.is_text_present_on_screen("citrix storefront", refresh_before_check=True)
        # return True
     
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False



# ------------------------
# Step functions
# ------------------------
@allure.step("Step 2 : Assign profile and verify password screen")
def QCL_3126_step2(api_config, browser):
    """ 
        Assigns the Entra ID SSO UMS profile to the device (if required) 
        and verifies the Microsoft password screen.  
        Returns: 
            bool: True if the password screen is detected, else False. 
    """
    logging.info("Starting Step 1 and step2: Assign profile and verify password screen")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
       
        page = browser.page
        target_hash_url = "https://192.168.10.28:8443/webapp/#/device-shadow/shadow/2239"
        bearer_token = UMSAuthTokenService(page).get_bearer_token(
                ums_cred["weburl"]+"/webapp/",
                
                ums_cred["username"],
                ums_cred["password"],
                settle_timeout=5000,
                
            )
        page.wait_for_load_state("load")
        page.goto(target_hash_url, wait_until="load")
        logger.info("page goto target")
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        
        cert= api_config["certificate_profile_citrix"]
        file_id = api.get_file_details(cert)

        time.sleep(10)
        profile_details = api.get_installed_app_id("Citrix Workspace App")
        time.sleep(10)
        return True
     
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False



@allure.step("Step 3: Start the created Storefront session")
def QCL_3126_step3(browser):
    """ 
        Starts the created Citrix Storefront session. 
        Returns: 
            bool: True if session is started successfully, else False. 
    """
    logging.info("Starting Step 3: Start the created Storefront session")   
    try:

        browser.reload_page()
        click.click_text_on_screen("citrix storefront", refresh_after_click=True)
        return click.is_text_present_on_screen("calculator", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step3_start_storefront: {e}")
        return False

@allure.step("Step 4: Start desktop session")
def QCL_3126_step4(browser):
    """ 
        Starts the desktop session from Storefront. 
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 4: Start desktop session")   
    try:

        browser.reload_page()
        click.click_text_on_screen("windows server", refresh_after_click=True)
        if click.is_text_present_on_screen("access denied", refresh_before_check=True,timeout=20):
            click.click_text_on_screen("ok", refresh_after_click=True)
            logging.error("Access denied error appeared while launching desktop session")
            return False
        
        else:
            return click.is_text_present_on_screen("recycle bin", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step4_start_desktop: {e}")
        return False
    
@allure.step("Step 5: Logout desktop session")
def QCL_3126_step5(browser):
    """ 
        Logs out of the desktop session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 5: Logout desktop session")   
    try:

        browser.reload_page()
        ssh = get_ssh()
        if ssh:
            ssh.exec("export DISPLAY=:0 && xdotool key Ctrl+Alt+Delete")
            time.sleep(2)
            click.click_text_on_screen("sign out", refresh_after_click=True)
            return click.is_text_present_on_screen("calculator", refresh_before_check=True)
        else:
            logging.error("Session might not have launched successfully, 'IIIIII' text not found")
            return False
    except Exception as e:
        logging.error(f"Exception in step5_logout_desktop: {e}")
        return False
    
@allure.step("Step 6: Start any application")
def QCL_3126_step6(browser):
    """ 
        Starts any application in the desktop session. 
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 6: Start any application")   
    try:

        browser.reload_page()
        click.click_text_on_screen("Calculator", refresh_after_click=True)
        if click.is_text_present_on_screen("access denied", refresh_before_check=True,timeout=20):
            click.click_text_on_screen("ok", refresh_after_click=True)
            logging.error("Access denied error appeared while launching desktop session")
            return False
        
        else:
            return click.is_text_present_on_screen("MC MR MS M+ M-", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step6_start_application: {e}")
        return False

@allure.step("Step 7: Close application")
def QCL_3126_step7(browser):
    """ 
        Closes the application started in the storefront session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 7: Close application")   
    try:
        f= click.click_text_on_screen("x", refresh_after_click=True,index=-1)
        time.sleep(1)
        return f

    except Exception as e:
        logging.error(f"Exception in step7_close_application: {e}")
        return False
    

@allure.step("Step 8: Logoff the Storefront session")
def QCL_3126_step8(browser):
    """ 
        Logs off the Storefront session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 8: Logoff the Storefront session")   
    try:

        browser.reload_page()
        click.click_text_on_screen("logoff", refresh_after_click=True)
        return click.is_text_present_on_screen("citrix storefront", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step8_logoff: {e}")
        return False
    
@allure.step("Step 12: Start the created Selfservice session")
def QCL_3126_step12(api_config,browser):
    """ 
        Starts the created Selfservice session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 12: Start the created Selfservice session")   
    try:
        # time.sleep(20)
        browser.reload_page()

        click.click_text_on_screen("Citrix SelfService", refresh_after_click=True)
        # time.sleep(5)
        if click.is_text_present_on_screen("citrix | workspace", refresh_before_check=True):
            click.click_text_on_screen("x", refresh_after_click=True,index=-1)
            time.sleep(5)
            click.click_text_on_screen("Citrix SelfService", refresh_after_click=True,doubleclick=True)
            click.click_text_on_screen("igel", refresh_after_click=True)
            time.sleep(5)
            click.click_text_on_screen("Citrix SelfService", refresh_after_click=True,doubleclick=True)


        click.click_text_on_screen("sign in with another method", refresh_after_click=True)
        if click.is_text_present_on_screen("username", refresh_before_check=True):
            qa_username= api_config["qa_test_username"]
            pyautogui.write(qa_username)
            pyautogui.press("tab")
        if click.is_text_present_on_screen("password", refresh_before_check=False):
            qa_password= api_config["qa_test_password"]
            pyautogui.write(qa_password)
        click.click_text_on_screen("log on", refresh_after_click=True)
        return click.is_text_present_on_screen("welcome", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step12_start_selfservice: {e}")
        return False


@allure.step("Step 13: Start desktop session")
def QCL_3126_step13(browser):
    """ 
        Starts the created desktop session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 13: Start the created desktop session")   
    try:

        browser.reload_page()
        click.click_text_on_screen("Desktops", refresh_after_click=True)
        time.sleep(2)
        click.click_text_on_screen("windows server", refresh_after_click=True)
        click.click_text_on_screen("open", refresh_after_click=True)
        if click.is_text_present_on_screen("access denied", refresh_before_check=True,timeout=20):
            click.click_text_on_screen("ok", refresh_after_click=True)
            logging.error("Access denied error appeared while launching desktop session")
            return False
        else:
            return click.is_text_present_on_screen("recycle bin", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step13_start_desktop: {e}")
        return False

@allure.step("Step 14: Logout desktop session")
def QCL_3126_step14(browser):
    """ 
        Logs out of the desktop session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 14: Logout desktop session")   
    try:

        ssh = get_ssh()
        if ssh:
            ssh.exec("export DISPLAY=:0 && xdotool key Ctrl+Alt+Delete")
        time.sleep(2)
        click.click_text_on_screen("sign out", refresh_after_click=True)
        return click.is_text_present_on_screen("apps", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step14_logout_desktop: {e}")
        return False
    
@allure.step("Step 15: Start any application")
def QCL_3126_step15(browser):
    """ 
        Starts any application in the desktop session. 
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 15: Start any application")   
    try:

        browser.reload_page()
        click.click_text_on_screen("apps", refresh_after_click=True)
        click.click_text_on_screen("Calculator", refresh_after_click=True)
        click.click_text_on_screen("open", refresh_after_click=True)
        if click.is_text_present_on_screen("access denied", refresh_before_check=True,timeout=20):
            click.click_text_on_screen("ok", refresh_after_click=True)
            logging.error("Access denied error appeared while launching desktop session")
            return False
        else:
            return click.is_text_present_on_screen("MC MR MS M+ M-", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step6_start_application: {e}")
        return False

@allure.step("Step 16: Close application")
def QCL_3126_step16(browser):
    """ 
        Closes the application started in the storefront session.
        Returns: 
            bool: True if login is successful, else False. 
    """
    logging.info("Starting Step 16: Close application")   
    try:
        f= click.click_text_on_screen("x", refresh_after_click=True,index=-2)
        time.sleep(1)
        return f

    except Exception as e:
        logging.error(f"Exception in step16_close_application: {e}")
        return False
    
@allure.step("Step 17: sign out of self service")
def QCL_3126_step17(browser):
    """ 
        Signs out of the self service session.
        Returns: 
            bool: True if sign out is successful, else False. 
    """
    logging.info("Starting Step 17: Sign out of self service")   
    try:
        f= click.click_text_on_screen("Desktop", refresh_after_click=True)
        pyautogui.press("tab", presses=2, interval=1)
        time.sleep(1)
        pyautogui.press("enter")
        click.click_text_on_screen("sign out", refresh_after_click=True)
        return click.is_text_present_on_screen("sign in", refresh_before_check=True)

    except Exception as e:
        logging.error(f"Exception in step17_sign_out_self_service: {e}")
        return False
    
@allure.step("Step 9 and1 8: Check citrix logs")
def QCL_3126_step9_18(api_config, browser):
    logging.info("Starting Step 9 and 18: Check citrix logs")

    log_file = "/var/log/citrix/ICAClient.log"
    error_keywords = ['segfault', 'core dumped', 'fatal', 'assert']

    try:
        ssh = get_ssh()

        if not ssh:
            logging.error("SSH connection failed")
            return False

        grep_cmd = f"grep -iE '{'|'.join(error_keywords)}' {log_file} || true"

        output = ssh.exec(grep_cmd)

        print("Output =", output)

        if output and output.strip():
            logging.error(" Citrix session crash detected:")
            logging.error(output)
            return False
        else:
            logging.info("No Citrix session crashes or segfaults found.")
            return True

    except Exception as e:
        logging.error(f"Exception in QCL_3126_step9_18: {e}")
        return False
    
def cleanup(api_config, browser):
    """Cleanup function to log off sessions and unassign profiles if needed."""
    logging.info("Starting cleanup: Logging off sessions and unassigning profiles")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        

        api= UMSWUMSApi(ums_cred["weburl"])
        context = browser.page.context
        auth_page = context.new_page()

        bearer_token = UMSAuthTokenService(auth_page).get_bearer_token(
            ums_cred["weburl"] + "/webapp/",
            ums_cred["username"],
            ums_cred["password"],
            settle_timeout=5000,
        )

        auth_page.close() 
        page = browser.page
        target_hash_url = ums_cred["weburl"]+"/webapp/#/device-shadow/shadow/"+str(device_details['id'])

        page.goto(target_hash_url, wait_until="domcontentloaded")
        logger.info("page goto target")
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        profile_details = ums.get_profile_details( api_config["profile_citrix"])
        cert= api_config["certificate_profile_citrix"]
        file_id = api.get_file_details(cert)
        api.remove_files(device_details["id"], file_id)
        api.detach_profile(device_details["id"], profile_details["id"])
        click.click_text_on_screen("ok", refresh_after_click=True)
        time.sleep(10)
        
        if ssh := get_ssh():
            return ssh.reboot()

    except Exception as e:
        logging.error(f"Exception in cleanup: {e}") 
# ------------------------
# Tests
# ------------------------
@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_cs_instance")
def test_QCL_3126_step1(api_config, browser_cs_instance):
    assert QCL_3126_step1(api_config, browser_cs_instance
)

@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step3(browser_cs_instance):
    assert QCL_3126_step3(browser_cs_instance)

@pytest.mark.dependency(name="step4")
@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step4(browser_cs_instance):
    assert QCL_3126_step4(browser_cs_instance) 

@pytest.mark.dependency(depends=["step4"])
@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step5(browser_cs_instance):
    assert QCL_3126_step5(browser_cs_instance)

@pytest.mark.dependency(name="step6")
@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step6(browser_cs_instance):
    assert QCL_3126_step6(browser_cs_instance)

@pytest.mark.dependency(depends=["step6"])
@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step7(browser_cs_instance):
    assert QCL_3126_step7(browser_cs_instance)

@allure.feature("Citrix storefront Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step8(browser_cs_instance):
    assert QCL_3126_step8(browser_cs_instance)


@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step12(api_config, browser_cs_instance):
    assert QCL_3126_step12(api_config, browser_cs_instance)

@pytest.mark.dependency(name="step13")
@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)    
def test_QCL_3126_step13(browser_cs_instance):
    assert QCL_3126_step13(browser_cs_instance)

@pytest.mark.dependency(depends=["step13"])
@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)    
def test_QCL_3126_step14(browser_cs_instance):
    assert QCL_3126_step14(browser_cs_instance)

@pytest.mark.dependency(name="step15")
@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)    
def test_QCL_3126_step15(browser_cs_instance):
    assert QCL_3126_step15(browser_cs_instance)

@pytest.mark.dependency(depends=["step15"])
@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step16(browser_cs_instance):
    assert QCL_3126_step16(browser_cs_instance)

@allure.feature("Citrix Selfservice Validation")
@allure.severity(allure.severity_level.CRITICAL)    
def test_QCL_3126_step17(browser_cs_instance):
    assert QCL_3126_step17(browser_cs_instance)

@allure.feature("Citrix logs validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3126_step9_18(api_config, browser_cs_instance):
    assert QCL_3126_step9_18(api_config, browser_cs_instance
) 

allure.feature("Citrix storefront and Selfservice cleanup")
allure.severity(allure.severity_level.CRITICAL) 
def test_cleanup_QCL_3126(api_config, browser_cs_instance):
    logger.info("Running cleanup for QCL-3126")
    assert cleanup(api_config, browser_cs_instance)

  