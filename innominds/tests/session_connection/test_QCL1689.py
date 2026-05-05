"""
############################################################
## Test Case ID : QCL-1689
## Title        : Connection | Citrix Storefront/Selfservice
##
## Description:
# Quick AVD connection test, to prevent that in a 
# new base_system releases the connection no longer works.
#
## Prerequisites:
# - ADV profile created in UMS with correct configuration.
#
## Test Scope:
# - Create a AVD Session
# - Start the created AVD session
# - Select the Workspace to start
# - Logoff the AVD session
# - Check the logs for errors
#
## Author       : Pooja Swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 9-mar-2026
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
@allure.step("Step 1 and 2: Assign profile and verify session created")
def QCL_1689_step1(api_config, browser):
    """ 
        Assigns the AVD UMS profile to the device 
        and verifies the AVD session is created.  
        Returns: 
            bool: True if the AVD session is created, else False. 
    """
    logging.info("Starting Step 1: Assign profile and verify session created")
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
        
        profile_details = ums.get_profile_details( api_config["profile_avd"])

        api.assign_profile(device_details["id"], profile_details["id"])
        if click.click_text_on_screen("restart now", refresh_after_click=True, timeout=60):

            logging.info("Clicked on 'restart now' prompt")
        else:
            found_text_ok = click.click_text_on_screen("ok", refresh_after_click=True)

        if ssh := get_ssh():
            ssh.reboot()
            return click.is_text_present_on_screen("avd session", refresh_before_check=True, timeout=120)
        else:
            logging.error("SSH connection failed")
            return False
     
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False




@allure.step("Step 3: Start the created AVD session")
def QCL_1689_step3(browser):
    """ 
        Starts the created AVD session. 
        Returns: 
            bool: True if session is started successfully, else False. 
    """
    logging.info("Starting Step 3: Start the created AVD session")   
    try:

        browser.reload_page()
        click.click_text_on_screen("avd session", refresh_after_click=True)
        return click.is_text_present_on_screen("windows", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step3_start_storefront: {e}")
        return False
    
@allure.step("Step 4: Select the Workspace to start")
def QCL_1689_step4(browser):
    """ 
        Starts workspace. 
        Returns: 
            bool: True if session is started successfully, else False. 
    """
    logging.info("Starting Step 4: Select the Workspace to start")   
    try:

        # browser.reload_page()
        click.click_text_on_screen("windows", refresh_after_click=True,index=3)
        time.sleep(10)  # wait for the workspace to load
        return click.is_text_present_on_screen("recyclebin", refresh_before_check=True, timeout=120)
    except Exception as e:
        logging.error(f"Exception in step3_start_storefront: {e}")
        return False
    
@allure.step("Step 5: logoff the workspace")
def QCL_1689_step5(browser,api_config):
    """ 
        logoff the workspace.
        Returns: 
            bool: True if workspace is logged off successfully, else False. 
    """
    logging.info("Starting Step 5: logoff the workspace")   
    try:

        # browser.reload_page()
        ssh = get_ssh()
        if ssh:
            ssh.exec("export DISPLAY=:0 && xdotool key Ctrl+Alt+Delete")
            click.click_text_on_screen("sign out", refresh_after_click=True)

        return click.is_text_present_on_screen("avd session", refresh_before_check=True)
    except Exception as e:
        logging.error(f"Exception in step5_logoff_workspace: {e}")
        return False

def QCL_1689_step6(browser):
    """
    Check AVD logs for real crashes or segmentation faults.
    Returns:
        bool: True if no critical errors found
    """

    logging.info("Starting Step 6: Check AVD logs")

    log_file = "/var/log/user/avd0"
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
            logging.error("AVD session crash detected:")
            logging.error(output)
            return False
        else:
            logging.info("No AVD session crashes or segfaults found.")
            return True

    except Exception as e:
        logging.error(f"Exception in QCL_3126_step6: {e}")
        return False


@allure.step("Clean all assigned profiles")
def clean_up(api_config, browser):
    """
        Detaches all assigned UMS profiles from the device
        and reboots the device to restore the initial state.
        Returns:
            bool: True if cleanup is successful, else False.
    """
    logger.info("Starting Clean Up: Detach all assigned profiles")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
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
        api = UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        ssh = get_ssh()
        for profile_key in ["profile_avd"]:

            profile_details = ums.get_profile_details(api_config[profile_key])
            api.detach_profile(device_details["id"], profile_details["id"])
            browser.reload_page()
            logger.info(f"Detached profile: {api_config[profile_key]}")
            click.click_text_on_screen("ok", refresh_after_click=True)
            time.sleep(10)
            ssh.reboot()
            return True

        
    except Exception as e:
        logger.error(f"Exception in clean_up: {e}")
        return False

allure.feature("AVD Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_cs_instance")
def test_QCL_1689_step1(api_config, browser_cs_instance):
    assert QCL_1689_step1(api_config, browser_cs_instance
)

@allure.feature("AVD Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1689_step3(browser_cs_instance):
    assert QCL_1689_step3(browser_cs_instance
)
    
@pytest.mark.dependency(name="step4")
@allure.feature("AVD Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1689_step4(browser_cs_instance):
    assert QCL_1689_step4(browser_cs_instance
) 

@pytest.mark.dependency(depends=["step4"])
@allure.feature("AVD Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1689_step5(browser_cs_instance, api_config):
    assert QCL_1689_step5(browser_cs_instance, api_config)

@allure.feature("AVD Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1689_step6(browser_cs_instance):
    assert QCL_1689_step6(browser_cs_instance
)

@allure.feature("AVD cleanup")
@allure.severity(allure.severity_level.CRITICAL)
def test_clean_up(api_config, browser_cs_instance):
    assert clean_up(api_config, browser_cs_instance
)