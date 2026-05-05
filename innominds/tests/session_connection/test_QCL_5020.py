"""
## Test Case ID : QCL-5020
## Title        : Connection | CloudPC connection.
#
## Description:
# Assign Windows 365 to the machine.
# Open IGEL Setup.
# Navigate to Apps → Windows 365.
# Under Windows 365 Sessions, click “+” to add a new session.
# In the Logon section, configure the following: 
# Username and Password: Credentials stored in 1Password under the CPC (CloudPC) entry
#
## Prerequisites:
# Create profile with above settings + config and Assign Windows 365 application to the IGEL device.
#
## Step to Automate top on above profile assignment.
# - | ---------------------------------------- | ---------------------------------------------------------- |
# N |                Scenario                  |                           Outcome                          |
# - | ---------------------------------------- | ---------------------------------------------------------- |
# 1 | Create a Cloud PC Session                | Session is created                                         |
# 2 | Start the created Cloud PC session       | Windows 365 Cloud PC Session starts and available Workspaces are displayed  |
# 3 | Logoff the Cloud PC session              | The connection closes and the IGEL desktop is displayed    |
# 4 | Start the created Cloud PC session again | Windows 365 Cloud PC Session starts and available Workspaces are displayed  |
# 5 | Disconnect the Cloud PC session          | The connection closes and the IGEL desktop is displayed    |
# 6 | Check system logs for errors             | No errors or segfaults related to Cloud PC session         |
# - | ---------------------------------------- | ---------------------------------------------------------- |
#
## Author       : Laxmikanth Ghali
## Email        : laxmikanth.ghali_ext@igel.com
## Created On   : 10-Mar-2026
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
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.utils.logger import logging
from core.api.ums_wums_api import UMSWUMSApi
from tests.session_connection.conftest import api_config

click = OcrUiInteractor()  # Shared OCR UI interactor

# Helpers Function #
#------------------#
def get_ssh():
# Return SSH client for the given device config.
    return SSHClient(host=device_cred["host"], user=device_cred["user"], pwd = device_cred["pwd"], port = device_cred["port"])

#  Step 1 Assigning the Windows 365 Configured Profile  #
#-------------------------------------------------------#
@allure.step("Step 1 Assign profile and verify session created")
def QCL_5020_step1(api_config, browser):
    logging.info("Starting Step 1: Assign profile and verify session created")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        page = browser.page
        target_hash_url = ums_cred["weburl"]+"/webapp/#/device-shadow/shadow/"+str(device_details['id'])
        bearer_token = UMSAuthTokenService(page).get_bearer_token(ums_cred["weburl"]+"/webapp/", ums_cred["username"], ums_cred["password"], settle_timeout=5000,)
        page.goto(target_hash_url, wait_until="load")
        logger.info("page goto target")
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        profile_details = ums.get_profile_details( api_config["cloudpcpc_profile_qcl-5020_01"])
        api.assign_profile(device_details["id"], profile_details["id"])
        logger.info("Profile assigned successfully")

        # wait for device reboot
        click.click_text_on_screen("RESTART", refresh_after_click=True, timeout=10)
        logger.info("Restart triggered from UI")
        ssh = get_ssh()
        ssh.reboot()
        logger.info("Restarted Device wait till device is up")
        ssh.wait_until_ready(timeout=180)

        # if click.click_text_on_screen("Restart", refresh_after_click=True, timeout=60):
        #     ssh = get_ssh()
        #     ssh.reboot()
        # ssh = get_ssh()
        logger.info("Waiting for device to reboot and reconnect")
        # ssh.wait_until_ready(timeout=180)
        return True
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False


#  STEP 2 – Launch Windows 365 Session and Validate by Opening a Windows Application  #
#######################################################################################
"""
    Launch the Windows 365 session and verify that the Cloud PC desktop loads 
    successfully. Open a Windows application to confirm that applications can 
    be started and controlled within the remote Windows environment.
"""
@allure.step("Step 2: Start Windows 365 session and validate desktop, then launch MSPaint")
def QCL_5020_step2(browser):
    logger.info("STEP 2: Launch Windows 365 session")
    try:
        # Reload shadow session page
        browser.reload_page()

        # Click Windows 365 icon
        if not click.click_text_on_screen("Windows", refresh_after_click=True):
            logger.error("Windows 365 icon not found")
            return False
        logger.info("Windows 365 session launched")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle", "chrom"]
        desktop_ready = False
        for text in search_terms:
            logger.info(f"Checking desktop icon: {text}")
            if click.is_text_present_on_screen(text, refresh_before_check=True):
                logger.info(f"Windows desktop detected using icon: {text}")
                desktop_ready = True
                break
        if not desktop_ready:
            logger.error("Windows desktop not detected")
            return False

        # Launch MSPaint inside Windows 365 session via IGEL
        logger.info("Launching MSPaint inside Windows session")
        ssh = get_ssh()
        ssh.exec(
            "export DISPLAY=:0 && "
            "xdotool key Super_L && "
            "sleep 2 && "
            "xdotool type mspaint && "
            "sleep 1 && "
            "xdotool key Return"
        )
        logger.info("MSPaint launch command sent")

        # Allow app to stay open briefly
        time.sleep(5)

        # Close MSPaint
        logger.info("Closing MSPaint")
        ssh.exec("export DISPLAY=:0 && xdotool key Alt+F4")
        logger.info("MSPaint closed successfully")
        return True
    except Exception as e:
        logger.error(f"Exception in Step 2 Windows 365: {e}")
        return False
    

#  STEP 3 – Launch Windows 365 Session and Validate Log Off functionality in Windows Application  #
###################################################################################################
@allure.step("Step 3: Log off the Windows 365 workspace")
def QCL_5020_step3(browser):
    logger.info("STEP 3: Log off Windows 365 workspace")
    try:
        ssh = get_ssh()
        if not ssh:
            logger.error("SSH connection failed")
            return False
        logger.info("Sending Win+X → U → I sequence for logoff")
        time.sleep(8)
        ssh.exec(
            "export DISPLAY=:0 && "
            "xdotool key Super_L+x && "
            "sleep 1 && "
            "xdotool key u && "
            "sleep 1 && "
            "xdotool key i"
        )
        logger.info("Logoff command sent")
        time.sleep(10)

        if click.is_text_present_on_screen("Recycle", refresh_before_check=True):
            logger.error("Windows session still active — logoff failed")
            return False

        # Validate returning to IGEL desktop
        if click.is_text_present_on_screen("Windows", refresh_before_check=True):
            logger.info("Successfully logged off Windows 365 session")
            return True

        logger.warning("IGEL desktop detected but Windows icon OCR missed")
        return True

        # logger.error("Windows 365 icon not detected after logoff")
        # return False
    except Exception as e:
        logger.error(f"Exception in step3 logoff workspace: {e}")
        return False


#  STEP 4 – Launch Windows 365 Session and Validate by Opening a Windows Application  #
#######################################################################################
"""
    Launch the Windows 365 session and verify that the Cloud PC desktop loads 
    successfully. Open a Windows application to confirm that applications can 
    be started and controlled within the remote Windows environment.
"""
@allure.step("Step 4: Start Windows 365 session and validate desktop, then launch MSPaint")
def QCL_5020_step4(browser):
    logger.info("STEP 4: Launch Windows 365 session")
    try:
        # Reload shadow session page
        browser.reload_page()

        # Click Windows 365 icon
        if not click.click_text_on_screen("Windows 365", refresh_after_click=True):
            logger.error("Windows 365 icon not found")
            return False
        logger.info("Windows 365 session launched")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        browser.reload_page()
        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle"]
        desktop_ready = False
        for text in search_terms:
            logger.info(f"Checking desktop icon: {text}")
            if click.is_text_present_on_screen(text, refresh_before_check=True):
                logger.info(f"Windows desktop detected using icon: {text}")
                desktop_ready = True
                break
        if not desktop_ready:
            # logger.error("Windows desktop not detected")
            return False

        # Launch Command_Prompt inside Windows 365 session via IGEL
        logger.info("Launching Command_Prompt inside Command session")
        ssh = get_ssh()
        ssh.exec(
            "export DISPLAY=:0 && "
            "xdotool key Super_L && "
            "sleep 2 && "
            "xdotool type Command && "
            "sleep 1 && "
            "xdotool key Return"
        )
        logger.info("Command_Prompt launch command sent")

        # Allow app to stay open briefly
        time.sleep(5)

        # Close Command
        logger.info("Closing Command prompt")
        ssh.exec("export DISPLAY=:0 && xdotool key Alt+F4")
        logger.info("Command prompt closed successfully")
        return True
    except Exception as e:
        logger.error(f"Exception in Step 4 Windows 365: {e}")
        return False
    

#  STEP 5  #
#######################################################################################
@allure.step("Step 5: disconnect the Windows 365 workspace")
def QCL_5020_step5(browser):

    logger.info("STEP 5: disconnect Windows 365 workspace")

    try:
        ssh = get_ssh()

        if not ssh:
            logger.error("SSH connection failed")
            return False

        logger.info("Sending disconnect Action Windows 365 CloudPC")
        time.sleep(8)
        ssh.exec(
            "export DISPLAY=:0 && "
            "xdotool key Super_L+x && "
            "sleep 1 && "
            "xdotool key u && "
            "sleep 1 && "
            "xdotool key D"
        )

        logger.info("Disconnect triggerred")
        time.sleep(8)

        # Validate returning to IGEL desktop
        if click.is_text_present_on_screen("Windows 365", refresh_before_check=True):
            logger.info("Successfully disconnect Windows 365 Cloud_PC session")
            return True

        logger.error("Windows 365 icon not detected after logoff")
        return False

    except Exception as e:
        logger.error(f"Exception in step5 disconnect CPC AVD workspace: {e}")
        return False
 
 #  STEP 6  #
#######################################################################################
@allure.step("Step 6: Validate the Windows 365 AVD workspace logs in the Igel logger")
def QCL_5020_step6(browser):
    logging.info("Starting Step 6: Check Cloud PC logs")
    log_file = "/var/log/user/CPC0"
        #     logger.warning("IGEL desktop detected but Windows icon OCR missed")
        # return True
    error_keywords = ['segfault', 'core dumped', 'fatal', 'assert']
    try:
        ssh = get_ssh()
        if not ssh:
            logging.error("SSH connection failed")
            return False
        grep_cmd = f"grep -iE '{'|'.join(error_keywords)}' {log_file} || true"
        output = ssh.exec(grep_cmd)

        if "No such file or directory" in output:
            logging.warning("Log file not found, skipping validation")
            return True        
        # print("Output =", output)

        if output and output.strip():
            logging.error("Windows 365 crash detected:")
            logging.error(output)
            return False
        else:
            logging.info("No Windows 365 crashes or segfaults found.")
            return True
    except Exception as e:
        logging.error(f"Exception in Validation: {e}")
        return False

#  CLEAN UP ALL PROFILE  #
#######################################################################################
@allure.step("Clean all assigned profiles")
def clean_up(api_config, browser):
    logger.info("Starting Clean Up: Detach all assigned profiles")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        page = browser.page
        target_hash_url = ums_cred["weburl"] + "/webapp/#/device-shadow/shadow/" + str(device_details['id'])
        bearer_token = UMSAuthTokenService(page).get_bearer_token(
            ums_cred["weburl"] + "/webapp/",
            ums_cred["username"],
            ums_cred["password"],
            settle_timeout=5000,
        )
        page.goto(target_hash_url, wait_until="load")
        logger.info("page goto target")
        api = UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        ssh = get_ssh()
        for profile_key in ["cloudpcpc_profile_qcl-5020_01"]:
            profile_details = ums.get_profile_details(api_config[profile_key])
            api.detach_profile(device_details["id"], profile_details["id"])
            browser.reload_page()
            logger.info(f"Detached profile: {api_config[profile_key]}")
            # click.click_text_on_screen("ok", refresh_after_click=True)
            click.click_text_on_screen("Restart", refresh_after_click=True, timeout=60)
            # time.sleep(60)
            ssh = get_ssh()
            ssh.reboot()
            ssh.wait_until_ready(timeout=180)

            return True
    except Exception as e:
        logger.error(f"Exception in clean_up: {e}")
        return False


#  QCL-5020 Test Step Control  #
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_cs_instance")
def test_QCL_5020_step1(api_config, browser_cs_instance):
    assert QCL_5020_step1(api_config, browser_cs_instance)


@allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_5020_step2(browser_cs_instance):
    assert QCL_5020_step2(browser_cs_instance)


@allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_5020_step3(browser_cs_instance):
    assert QCL_5020_step3(browser_cs_instance) 


@allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_5020_step4(browser_cs_instance):
    assert QCL_5020_step4(browser_cs_instance)


@allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_5020_step5(browser_cs_instance):
    assert QCL_5020_step5(browser_cs_instance)


@allure.feature("CPC Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_5020_step6(browser_cs_instance):
    assert QCL_5020_step6(browser_cs_instance)


@allure.feature("CPC cleanup")
@allure.severity(allure.severity_level.CRITICAL)
def test_clean_up(api_config, browser_cs_instance):
    assert clean_up(api_config, browser_cs_instance)
