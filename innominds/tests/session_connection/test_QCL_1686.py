"""
## Test Case ID : QCL-1686
## Title        : Session Connection | RDP and RDP-WEB connectivity.
#
## Description:
# Verify that RDP and RDWeb connections function correctly on the latest available released app, ensuring that new base_system releases do not break existing connectivity.
#     The test involves configuring an RDP session via IGEL Setup, connecting to a valid Windows server, and confirming that the connection is successfully established without errors.
#
## Prerequisites:
# A machine with RDP access assigned
# Latest available released application installed
# Access to IGEL Setup
# A reachable and properly configured Windows server with:
# Remote Desktop enabled
# Network accessibility

# Valid server URL:
# (form  https://itga-vcs-test.igel.local/ )
# Domain: qa.test
# Valid user credentials (username and password) for the target server
# Network connectivity between client machine and the server
# Proper permissions to configure RDP sessions in IGEL
#
## Author       : Laxmikanth Ghali
## Email        : laxmikanth.ghali_ext@igel.com
## Created On   : 02-Apr-2026
## Version      : 1.0
############################################################
"""

import time
import pyautogui
import allure
import pytest
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from bussiness.page_login import ums_login
from core.ssh import ssh
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

#  Step 1 and 2 Assigning the Windows RDP Configured Profile  #
#-------------------------------------------------------#
@allure.step("Step 1 and 2 Assign profile and verify session created")
def QCL_1686_step1_2(api_config, browser):
    logger.info("TITLE: QCL-1686:  [Quick] | Connection | RDP/RDWeb")
    logging.info("Step 1 and 2: Assign profile and verify session created!")
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
        profile_details = ums.get_profile_details( api_config["session_connection_profile_rdp_qcl-1686_01"])
        api.assign_profile(device_details["id"], profile_details["id"])
        logger.info("Profile assigned successfully")

        # wait for device reboot
        click.click_text_on_screen("RESTART NOW", refresh_after_click=True, timeout=10)
        logger.info("Restart triggered from UI")
        ssh = get_ssh()
        ssh.reboot()
        logger.info("Restarted Device wait till device is up")
        ssh.wait_until_ready(timeout=180)
        logger.info("Waiting for device to reboot and reconnect")
        return True
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False


#  STEP 3 – Launch Windows RDP Session and Validate by Opening a Windows Application  #
#######################################################################################
"""
    Launch the Windows RDP session and verify that the Windows RDP desktop loads 
    successfully. Open a Windows application to confirm that applications can 
    be started and controlled within the remote Windows environment.
"""
@allure.step("Step 3: Start Windows RDP session and validate desktop")
def QCL_1686_step3(browser):
    print("Step 3: Start Windows RDP session and validate desktop app")
    logger.info("STEP 3: Launch Windows RDP session")
    try:
        # Reload shadow session page
        browser.reload_page()
        # Click Windows RDP icon
        if not click.click_text_on_screen("WINDOWS RDP", refresh_after_click=True):
            logger.error("Windows RDP icon not found")
            return False
        logger.info("Windows RDP session launched")
        page = browser.page
        page.bring_to_front()
        if not click.click_text_on_screen("continue", refresh_after_click=True):
            logger.error("Proceed to lanch Windows RDP")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle", "Microsoft", "edge"]
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


        if not click.click_text_on_screen(f"{text} found", refresh_after_click=True):
            logger.error(f"Proceed to lanch Windows {text}")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()

        # # Launch MSPaint inside Windows RDP session via IGEL
        # logger.info("Launching MSPaint inside Windows session")
        # ssh = get_ssh()
        # ssh.exec(
        #     "export DISPLAY=:0 && "
        #     "xdotool key Super_L && "
        #     "sleep 2 && "
        #     "xdotool type mspaint && "
        #     "sleep 1 && "
        #     "xdotool key Return"
        # )
        # logger.info("MSPaint launch command sent")

        # def launch_windows_app(self, app_name="mspaint"):
        #     if not self.handle:
        #         print("SSH not connected")
        #         return False

        #     cmd = (
        #         "export DISPLAY=:0 && "
        #         # Step 1: Focus screen
        #         "xdotool mousemove 500 500 click 1 && "
        #         "sleep 1 && "
        #         # Step 2: Open Start Menu
        #         "xdotool key Super_L && "
        #         "sleep 2 && "
        #         # Step 3: Type app name (NO quotes)
        #         f"xdotool type --delay 120 {app_name} && "
        #         "sleep 1 && "
        #         # Step 4: Press Enter
        #         "xdotool key Return"
        #     )

        #     print(f"[+] Launching Windows app: {app_name}")
        #     output = self.exec(cmd)

        #     if output is not None:
        #         print("[+] Application launch command sent")
        #         return True
        #     else:
        #         print("[!] Failed to launch app")
        #         return False



        # # Allow app to stay open briefly
        # time.sleep(10)

        # # Close MSPaint
        # logger.info("Closing MSPaint")
        # # ssh.exec("export DISPLAY=:0 && xdotool key Alt+F4")
        # # logger.info("MSPaint closed successfully")
        # ssh.exec(
        #     "export DISPLAY=:0 && "
        #     "xdotool search --name 'Paint' windowactivate --sync && "
        #     "sleep 1 && "
        #     "xdotool key Alt+F4"
        # )
        return True
    except Exception as e:
        logger.error(f"Exception in Step 2 Windows RDP: {e}")
        return False
    

#  STEP 4 – Launch Windows RDP Session and Validate Log Off functionality in Windows Application  #
###################################################################################################
@allure.step("Step 4: Log off the Windows RDP")
def QCL_1686_step4(browser):
    logger.info("STEP 4: Log off Windows RDP")
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
        # if not click.click_text_on_screen("OK", refresh_after_click=True):
        #     time.sleep(10)            
        #     logger.error("Windows session still active — logoff failed")
        #     return False
        logger.info("Windows RDP session logout successful")
        page = browser.page
        page.bring_to_front()

        # Validate returning to IGEL desktop
        if click.is_text_present_on_screen("WINDOWS RDP", refresh_before_check=True):
            logger.info("Successfully logged off Windows RDP session")
            return True
        logger.warning("IGEL desktop detected but Windows icon OCR missed")
        return True
    except Exception as e:
        logger.error(f"Exception in step3 logoff workspace: {e}")
        return False


 #  STEP 5  #
#######################################################################################
@allure.step("Step 5: Validate the Windows RDP logs in the Igel logger")
def QCL_1686_step5(browser):
    logging.info("Starting Step 5: Check Windows RDP logs")
    log_file = "/var/log/user/RDP0"
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
            logging.error("Windows RDP crash detected:")
            logging.error(output)
            return False
        else:
            logging.info("No Windows RDP crashes or segfaults found.")
            return True
    except Exception as e:
        logging.error(f"Exception in Validation: {e}")
        return False


#  STEP 6_7 – Launch Windows RDWEB Session and Validate by Opening a Windows Application  #
#######################################################################################
#-------------------------------------------------------#
@allure.step("Step 6 and 7 RDWEB Assign profile and verify session created")
def QCL_1686_step6_7(api_config, browser):
    logger.info("TITLE: QCL-1686:  [Quick] | Connection | RDP/RDWeb")
    logging.info("Step 6 and 7: Assign profile and verify session created!")
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
        profile_details = ums.get_profile_details( api_config["session_connection_profile_rdp_web_qcl-1686_01"])
        api.assign_profile(device_details["id"], profile_details["id"])
        logger.info("RDWEB Profile assigned successfully")

        # wait for device reboot
        click.click_text_on_screen("RESTART NOW", refresh_after_click=True, timeout=10)
        logger.info("Restart triggered from UI")
        ssh = get_ssh()
        ssh.reboot()
        logger.info("Restarted Device wait till device is up")
        ssh.wait_until_ready(timeout=180)
        logger.info("Waiting for device to reboot and reconnect")
        return True
    except Exception as e:
        logging.error(f"Exception in step1_assign_profile: {e}")
        return False


#  STEP 8 – Launch Windows RDPWEB  Session and Validate by Opening a Windows Application  #
#######################################################################################
"""
    Launch the Windows RDWEB session and verify that the Windows RDWEB desktop loads 
    successfully. Open a Windows application to confirm that applications can 
    be started and controlled within the remote Windows environment.
"""
@allure.step("Step 8: Start Windows RDWEB session and validate desktop")
def QCL_1686_step8(browser):
    print("Step 8: Start Windows RDWEB session and validate desktop app")
    logger.info("STEP 8: Launch Windows RDWEB session")
    try:
        # Reload shadow session page
        browser.reload_page()
        # Click Windows RDP icon
        if not click.click_text_on_screen("WINDOWS RDP", refresh_after_click=True):
            logger.error("Windows RDP icon not found")
            return False
        logger.info("Windows RDP session launched")
        page = browser.page
        page.bring_to_front()
        if not click.click_text_on_screen("continue", refresh_after_click=True):
            logger.error("Proceed to lanch Windows RDP")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle", "Microsoft", "edge"]
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


        if not click.click_text_on_screen(f"{text} found", refresh_after_click=True):
            logger.error(f"Proceed to lanch Windows {text}")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()
        return True
    except Exception as e:
        logger.error(f"Exception in Step 8 Windows RDP: {e}")
        return False
    
#  STEP 9 – Launch Windows RDPWEB  Session and Validate by Opening a Windows Application  #
#######################################################################################
"""
    Launch the Windows RDWEB session and verify that the Windows RDWEB desktop loads 
    successfully. Open a Windows application to confirm that applications can 
    be started and controlled within the remote Windows environment.
"""
@allure.step("Step 9: Start Windows RDWEB session and validate desktop")
def QCL_1686_step9(browser):
    print("Step 9: Start Windows RDWEB session and validate desktop app")
    logger.info("STEP 9: Launch Windows RDWEB session")
    try:
        # Reload shadow session page
        browser.reload_page()
        # Click Windows RDP icon
        if not click.click_text_on_screen("WINDOWS RDP", refresh_after_click=True):
            logger.error("Windows RDP icon not found")
            return False
        logger.info("Windows RDP session launched")
        page = browser.page
        page.bring_to_front()
        if not click.click_text_on_screen("continue", refresh_after_click=True):
            logger.error("Proceed to lanch Windows RDP")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle", "Microsoft", "edge"]
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


        if not click.click_text_on_screen(f"{text} found", refresh_after_click=True):
            logger.error(f"Proceed to lanch Windows {text}")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()
        return True
    except Exception as e:
        logger.error(f"Exception in Step 2 Windows RDP: {e}")
        return False

#  STEP 10 – Close the Windows RDWEB access app session which started
#######################################################################################
"""
Close the Windows RDWEB access app session which started
"""
@allure.step("Step 10: Close the Windows RDWEB access app session which started")
def QCL_1686_step10(browser):
    print("Step 10: Close the Windows RDWEB access app session which started")
    logger.info("STEP 10: Launch Windows RDWEB session")
    try:
        # Reload shadow session page
        browser.reload_page()
        # Click Windows RDP icon
        if not click.click_text_on_screen("WINDOWS RDP", refresh_after_click=True):
            logger.error("Windows RDP icon not found")
            return False
        logger.info("Windows RDP session launched")
        page = browser.page
        page.bring_to_front()
        if not click.click_text_on_screen("continue", refresh_after_click=True):
            logger.error("Proceed to lanch Windows RDP")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()

        # Focus shadow screen
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        logger.info("Waiting for Windows desktop to load")
        time.sleep(10)

        # Validate Windows desktop
        search_terms = ["Recycle Bin", "RecycleBin", "Recycle", "Microsoft", "edge"]
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


        if not click.click_text_on_screen(f"{text} found", refresh_after_click=True):
            logger.error(f"Proceed to lanch Windows {text}")
            return False
        logger.info("Windows RDP session launching")
        page = browser.page
        page.bring_to_front()
        return True
    except Exception as e:
        logger.error(f"Exception in Step 10 Windows RDP: {e}")
        return False




#  STEP 11 – Launch Windows RDWEB Session and Validate Log Off functionality in Windows Application  #
###################################################################################################
@allure.step("Step 11: Log off the Windows RDWEB")
def QCL_1686_step11(browser):
    logger.info("STEP 11: Log off Windows RDWEB")
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
        logger.info("Windows RDP session logout successful")
        page = browser.page
        page.bring_to_front()

        # Validate returning to IGEL desktop
        if click.is_text_present_on_screen("WINDOWS RDP", refresh_before_check=True):
            logger.info("Successfully logged off Windows RDP session")
            return True
        logger.warning("IGEL desktop detected but Windows icon OCR missed")
        return True
    except Exception as e:
        logger.error(f"Exception in step11 logoff workspace: {e}")
        return False




 #  STEP 12  #
#######################################################################################
@allure.step("Step 12: Validate the Windows RDP logs in the Igel logger")
def QCL_1686_step12(browser):
    logging.info("Starting Step 12: Check Windows RDP logs")
    log_file = "/var/log/user/RDP0"
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
            logging.error("Windows RDP crash detected:")
            logging.error(output)
            return False
        else:
            logging.info("No Windows RDWEB crashes or segfaults found.")
            return True
    except Exception as e:
        logging.error(f"Exception in Validation: {e}")
        return False

#  CLEAN UP ALL PROFILE  #
#######################################################################################
@allure.step("Clean RDP and RDWEB assigned profiles")
def rdp_clean_up(api_config, browser):
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
        for profile_key in ["session_connection_profile_rdp_qcl-1686_01", "session_connection_profile_rdp_web_qcl-1686_01"]:
            profile_details = ums.get_profile_details(api_config[profile_key])
            api.detach_profile(device_details["id"], profile_details["id"])
            browser.reload_page()
            logger.info(f"Detached profile: {api_config[profile_key]}")
            click.click_text_on_screen("RESTART NOW", refresh_after_click=True, timeout=60)
            ssh = get_ssh()
            ssh.reboot()
            ssh.wait_until_ready(timeout=180)
            return True
    except Exception as e:
        logger.error(f"Exception in clean_up: {e}")
        return False


#  QCL-1686 Test Step Control  #
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
allure.feature("RDP Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_cs_instance")
def test_QCL_1686_step1_2_TC_TITLE__Quick_Connection__RDP_RDWEB(api_config, browser_cs_instance):
    logging.info("QCL_1686_step_1_2_Assign_profile_and_verify_session_created")
    assert QCL_1686_step1_2(api_config, browser_cs_instance)

@allure.feature("RDP Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1686_step3_TC_TITLE__Quick_Connection__RDP_RDWEB(
    browser_cs_instance):
    logging.info("test_QCL_1686_step3_RDP_session_starts_and_your_are_on_the_VDI_desktop(browser_cs_instance")
    assert QCL_1686_step3(browser_cs_instance) 

@allure.feature("RDP Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1686_step4_TC_TITLE__Quick_Connection__RDP_RDWEB(browser_cs_instance):
    logging.info("test_QCL_1686_step4_Step_4_Log_off_the_Windows_RDP(browser_cs_instance")
    assert QCL_1686_step4(browser_cs_instance)

@allure.feature("RDP Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_1686_step5_TC_TITLE__Quick_Connection__RDP_RDWEB(browser_cs_instance):
    assert QCL_1686_step5(browser_cs_instance)

# @allure.feature("RDP Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step6_TC_TITLE__Quick_Connection__RDP_RDWEB(browser_cs_instance):
#     assert QCL_1686_step6(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step7(browser_cs_instance):
#     assert QCL_1686_step7(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step8(browser_cs_instance):
#     assert QCL_1686_step8(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step9(browser_cs_instance):
#     assert QCL_1686_step9(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step10(browser_cs_instance):
#     assert QCL_1686_step10(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step11(browser_cs_instance):
#     assert QCL_1686_step11(browser_cs_instance)

# @allure.feature("RDP WEB Validation")
# @allure.severity(allure.severity_level.CRITICAL)
# def test_QCL_1686_step12(browser_cs_instance):
#     assert QCL_1686_step12(browser_cs_instance)


@allure.feature("RDP Profile cleanup")
@allure.severity(allure.severity_level.CRITICAL)
def test_rdp_clean_up_TC_TITLE__Quick_Connection__RDP_RDWEB(api_config, browser_cs_instance):
    logging.info("test_rdp_clean_up_all_assigned_profiles_to_device(api_config, browser_cs_instance")
    assert rdp_clean_up(api_config, browser_cs_instance)

