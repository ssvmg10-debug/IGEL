############################################################
## Test Case ID : QCL-5022
## Title        : CIC(Corporate Identity Customization (CIC)) Profile Validation on IGEL OS
#
## Description:
# This test case handles the testing of the Corporate Identity Customization (CIC) feature. 
# Downloading and also applying the custom wallpapers on the device.
# 
## Prerequisites:
# - Required UMS CIC profiles must be created and available.
#
## Test Scope:
# - Configure and assign Corporate Identity Customizations.
# - Detach Corporate Identity Customization.
# - Assign multiple CICs, of the same type, to the same end point.
#
## Author       : Laxmikanth Ghali
## Email        : laxmikanth.ghali_ext@igel.com
## Created On   : 08-Mar-2026
## Version      : 1.0
############################################################

import time
import pyautogui
import allure
import pytest
from core.api.UMS import UMS
from core.ssh import ssh
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from bussiness.page_login import ums_login
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from bussiness.onepassword_otp import OTPGenerator
from core.api.auth_token import UMSAuthTokenService
from core.api.ums_wums_api import UMSWUMSApi
click = OcrUiInteractor()  # Shared OCR UI interactor

#  PyAutoGUI Global Settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.2

# SSH HELPER Function
def get_ssh():
    return SSHClient(
        host=device_cred["host"],
        user=device_cred["user"],
        pwd=device_cred["pwd"],
        port=device_cred["port"]
    )
    
########################################################### STEP 1 #####################################################
@allure.step("Step 1: Assign CIC Profile")
def QCL_5022_step1(api_config, browser):
    logger.info("STEP 1: Assign CIC Profile to the Device")

    # Get device details
    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])
    page = browser.page

    # Capture bearer FIRST
    bearer_token = UMSAuthTokenService(page).get_bearer_token(f"{ums_cred['weburl']}/webapp/", ums_cred["username"], ums_cred["password"], settle_timeout=5000)
    api = UMSWUMSApi(ums_cred["weburl"])
    api.set_bearer(bearer_token)
    logger.info("Bearer token captured successfully")

    # Fetch CIC profile
    profile_name = api_config["cic_profile_qcl-5022_sscp"]
    profile = api.get_cic_profile_details(profile_name)
    logger.info(f"CIC profile fetched: {profile}")

    # Assign via API
    api.assign_object(device_id=device_details["id"], object_id=profile["id"], object_type=profile["type"], unassign=False)
    logger.info("Assign API call completed")

    # Verify assignment
    time.sleep(3)
    assigned_objects = api.get_direct_assigned_objects(device_details["id"])
    assigned = any(obj.get("id") == profile["id"] for obj in assigned_objects)
    logger.info(f"CIC assignment verification result: {assigned}")
    if not assigned:
        logger.error("CIC assignment verification failed")
        return False

    # Open Shadow session
    shadow_url = (ums_cred["weburl"] + "/webapp/#/device-shadow/shadow/" + str(device_details["id"]))
    logger.info(f"Opening shadow -> {shadow_url}")
    page.goto(shadow_url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    if "device-shadow" not in page.url:
        logger.error("Shadow navigation failed")
        return False
    logger.info("Shadow session loaded successfully")

    # WAIT FOR IGEL NOTIFICATION + CLICK OK (OCR)
    logger.info("Waiting 5 seconds before checking popup...")
    page.wait_for_timeout(5000)
    logger.info("Waiting for IGEL notification popup...")
    popup_handled = False
    start_time = time.time()
    timeout = 10   # increased timeout for mu validaition

    while time.time() - start_time < timeout:
        found = click.click_text_on_screen("ok", refresh_after_click=True)
        if found:
            time.sleep(2)
            pyautogui.click()
            logger.info("OK button clicked successfully")
            popup_handled = True
            break
        logger.info("Popup not found yet... retrying")
        time.sleep(3)
    if not popup_handled:
        logger.warning("OK popup not detected within timeout — continuing test")

    # IMPORTANT: WAIT after popup
    logger.info("Waiting 5 seconds after popup handling...")
    page.wait_for_timeout(5000)
    logger.info("STEP 1 COMPLETED SUCCESSFULLY")
    return True

# Reboot Device
    ssh = get_ssh()
    reboot_status = ssh.reboot()
    if not reboot_status:
        logger.error("Device reboot failed")
        return False
    logger.info(f"{assigned}: Device reboot successful")
    return True

########################################################### STEP 2 #####################################################
@allure.step("Step 2: Launch IGEL Setup and Validate Screensaver Settings")
def QCL_5022_step2(api_config, browser):
    logger.info("STEP 2: Launch IGEL Setup Application")
    page = browser.page
    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])
    shadow_url = (ums_cred["weburl"] + "/webapp/#/device-shadow/shadow/" + str(device_details["id"]))
    logger.info(f"Opening shadow -> {shadow_url}")
    page.goto(shadow_url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    if "device-shadow" not in page.url:
        logger.error("Shadow navigation failed")
        return False
    logger.info("Shadow session ready")

    # Focus Shadow screen
    screen_width, screen_height = pyautogui.size()
    page.bring_to_front()
    for _ in range(5):
        pyautogui.click(screen_width // 2, screen_height // 2)
        time.sleep(1)
    logger.info("Shadow canvas focused")

    # Launch IGEL Setup via SSH command utility
    logger.info("Launching IGEL Setup via SSH")
    ssh = get_ssh()
    try:
        ssh.exec("export DISPLAY=:0 && igel-tcsetup &")
        logger.info("SSH igel-tcsetup executed")
    except Exception as e:
        logger.error(f"SSH igel-tcsetup failed: {e}")
        return False


# Test
    # Click 'USER INTERFACE' Menu Button
    logger.info("Clicking User Interface")
    if not click.click_text_on_screen("User Interface", refresh_after_click=True):
        logger.error("User Interface not found")
        return False
    logger.info("=User Interface Clicked")
    time.sleep(2)

    # Click 'SCREENLOCK / SCREENSAVER' Menu Button
    time.sleep(2)
    logger.info("Opening Screenlock / Screensaver Menu")
    if not click.click_text_on_screen("Screenlock / Screensaver", refresh_after_click=True):
        logger.error("Screenlock / Screensaver not found")
        return False
    time.sleep(1)

    # Expand left tree    
    pyautogui.press("right")

    time.sleep(1)
    pyautogui.press("down", presses=3, interval=0.5)
    logger.info("Validating display mode")
    mode_found1 = click.click_text_on_screen("Small-sized hopping")

    # mode_found1 = click.text_exists_on_screen("Small-sized hopping")
    if mode_found1:
        logger.info("Image display mode validated successfully")
    else:
        logger.warning("Image display mode NOT found")
    time.sleep(2)

    # Validate path in the IGEL-Setup screensaver path.
    logger.info("Validating screensaver path")
    mode_found2 = click.click_text_on_screen("/custom-data/screensaver")
    if mode_found2:
        logger.info("Screensaver path validated")
    else:
        logger.warning("Screensaver path NOT found")
    time.sleep(2)

    # Click 'SYSTEM' Menu Button
    logger.info("Clicking System menu tab")
    if not click.click_text_on_screen("System", refresh_after_click=True):
        logger.error("System menu tab not found")
        return False
    logger.info("System menu tab Clicked")
    time.sleep(2)

    # Click 'Registry' Side Menu Button
    logger.info("Opening 'Registry' side Menu")
    if not click.click_text_on_screen("Registry", refresh_after_click=True):
        logger.error("Registry side menu not found")
        return False
    time.sleep(1)

    # Click 'custom_data_partition' Side Menu Button
    page.bring_to_front()
    pyautogui.click(screen_width // 2, screen_height // 2)
    logger.info("Opening 'custom_data_partition' side sub menu")

    # click.click_text_on_screen("custom_data_partition")
    if not click.click_text_on_screen("custom_data_partition", refresh_after_click=True):
        logger.error("custom_data_partition sub menu not found")
        return False
    time.sleep(1)
    logger.info("Expanded 'custom_data_partition' side sub menu")

    # Expand left tree
    pyautogui.press("right")
    time.sleep(1)
    pyautogui.press("down", presses=1, interval=0.5)
    # Validate path in the IGEL-Setup display mode.
    logger.info("Validating display mode")
    mode_found3 = click.click_text_on_screen("medium")

    # mode_found3 = click.text_exists_on_screen("Small-sized hopping")
    if mode_found3:
        logger.info("Custom_data_partition display mode validated successfully")
    else:
        logger.warning("custom_data_partition display mode NOT found")
    time.sleep(2)

    # CLOSE IGEL SETUP
    logger.info("Closing IGEL Setup")
    if not click.click_text_on_screen("Close"):
        logger.warning("Close button not detected — pressing ESC")
        pyautogui.press("esc")
    time.sleep(2)

    # Step-2 Final Result
    if mode_found1 and mode_found2:
        logger.info("STEP 2 Completed Successful with all custom validation")
        return True
    logger.error("STEP 2 FAILED Validating the custom cic info")
    return False

########################################################### STEP 3 #####################################################
@allure.step("Step 3: Assign All CIC Profiles And Validate Order In UMS")
def QCL_5022_step3(api_config, browser):
    logger.info("STEP 3: ASSIGN ALL CIC PROFILE & VALIDATE CIC PROFILE ASSIGNED ORDER")
    page = browser.page

    # Get Device Info
    ums = UMS( ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])

    # device_id = device_details["id"]
    device_id = device_details["id"]

    # Build device shadow URL to keep browser on device page
    device_shadow_url = (ums_cred["weburl"] + "/webapp/#/device-shadow/shadow/" + str(device_id))

    # Navigate to device shadow screen
    logger.info(f"Navigating to device shadow -> {device_shadow_url}")
    page.goto(device_shadow_url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    # Capture Bearer
    bearer_token = UMSAuthTokenService(page).get_bearer_token(
        f"{ums_cred['weburl']}/webapp/", ums_cred["username"], ums_cred["password"], settle_timeout=5000)
    api = UMSWUMSApi(ums_cred["weburl"])
    api.set_bearer(bearer_token)
    logger.info("Bearer token captured")

    # Define CIC Order (STRICT ORDER)
    cic_profile_keys = [
        "cic_profile_qcl-5022_wp",  # 2155
        "cic_profile_qcl-5022_bp",  # 2158
        "cic_profile_qcl-5022_ss",  # 2160
        "cic_profile_qcl-5022_sb",  # 2161
        "cic_profile_qcl-5022_sm",  # 2162
        "cic_profile_qcl-5022_tb"   # 2163
    ]
    expected_order_names = []
    for key in cic_profile_keys:

        # Ensure browser stays on device screen
        if "device-shadow" not in page.url:
            logger.warning("Browser moved away from device screen. Redirecting back.")
            page.goto(device_shadow_url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")

        profile_name = api_config[key]
        profile = api.get_cic_profile_details(profile_name)
        logger.info(f"Assigning CIC -> {profile['name']}")

        api.assign_object(device_id=device_id, object_id=profile["id"], object_type=profile["type"], unassign=False)
        expected_order_names.append(profile["name"])
        time.sleep(2)
    logger.info("All CIC profiles assigned")

    # Fetch Direct Assigned Objects
    time.sleep(5)
    assigned_objects = api.get_direct_assigned_objects(device_id)

    # Filter only CIC (Firmware Customization type)
    assigned_cic = [obj for obj in assigned_objects if obj.get("type") == "FIRMWARE_CUSTOMIZATION"]
    actual_order_names = [obj["name"] for obj in assigned_cic]
    logger.info(f"Expected Order -> {expected_order_names}")
    logger.info(f"Actual Order   -> {actual_order_names}")

    # Validate Order by CIC ID (Ascending)
    actual_cic = [
        obj for obj in assigned_objects
        if obj.get("type") == "FIRMWARE_CUSTOMIZATION"]
    actual_ids = [obj["id"] for obj in actual_cic]
    sorted_ids = sorted(actual_ids)
    logger.info(f"Actual CIC IDs  -> {actual_ids}")
    logger.info(f"Sorted CIC IDs  -> {sorted_ids}")
    assert actual_ids == sorted_ids, "CIC IDs are not in ascending order"
    logger.info("CIC IDs validated in ascending order")
    logger.info("STEP 3 COMPLETED SUCCESSFULLY")
    return True


######################################################## STEP 4 #######################################################
@allure.step("Step 4: Unassign ALL CIC Profiles")
def QCL_5022_step4(api_config, browser):
    logger.info("===== STEP 4: UNASSIGN ALL CIC =====")
    ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
    device_details = ums.get_vm_details(device_cred["hostname"])
    device_id = device_details["id"]
    page = browser.page

    # Build device shadow URL
    device_shadow_url = (ums_cred["weburl"] + "/webapp/#/device-shadow/shadow/" + str(device_id))

    # Ensure browser starts on device screen
    logger.info(f"Navigating to device shadow -> {device_shadow_url}")
    page.goto(device_shadow_url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    # Capture Bearer
    bearer_token = UMSAuthTokenService(page).get_bearer_token(f"{ums_cred['weburl']}/webapp/", ums_cred["username"], ums_cred["password"], settle_timeout=3000)
    api = UMSWUMSApi(ums_cred["weburl"])
    api.set_bearer(bearer_token)

    # Get All Direct Assignments
    assigned_objects = api.get_direct_assigned_objects(device_id)
    assigned_cic = [obj for obj in assigned_objects if obj.get("type") == "FIRMWARE_CUSTOMIZATION"]
    if not assigned_cic:
        logger.info("No CIC profiles assigned.")
        return True

    # Unassign ALL CIC
    for cic in assigned_cic:
        # Ensure browser stays on device screen
        if "device-shadow" not in page.url:
            logger.warning("Browser moved away from device screen. Redirecting back.")
            page.goto(device_shadow_url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
        logger.info(f"Unassigning CIC -> {cic['name']}")
        api.assign_object(device_id=device_id, object_id=cic["id"], object_type=cic["type"], unassign=True)
        time.sleep(2)
    logger.info("All CIC profiles unassigned")

    # Final Verification
    time.sleep(5)
    verify_objects = api.get_direct_assigned_objects(device_id)
    still_assigned = [obj for obj in verify_objects
        if obj.get("type") == "FIRMWARE_CUSTOMIZATION"]
    if still_assigned:
        logger.error("Some CIC profiles still assigned!")
        return False
    logger.info("STEP 4 COMPLETED SUCCESSFULLY")
    return True
    logger.info("All CIC profiles unassigned")
    time.sleep(30)
    logger.info("Waiting 5 seconds before finishing test to keep shadow open")
    page.wait_for_timeout(15000)
time.sleep(30)

# TEST EXECUTION CONTROL (TC STEP ENABLE)
@allure.feature("CIC Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures("api_config", "browser_cic_instance")
def test_assign_cic(api_config, browser_cic_instance):
    assert QCL_5022_step1(api_config, browser_cic_instance)

@allure.feature("CIC Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures("api_config", "browser_cic_instance")
def test_launch_igel_setup_step_2(api_config, browser_cic_instance):
    assert QCL_5022_step2(api_config, browser_cic_instance)

@allure.feature("CIC Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures("api_config", "browser_cic_instance")
def test_assign_all_cic_and_validate_order(api_config, browser_cic_instance):
    assert QCL_5022_step3(api_config, browser_cic_instance)

@allure.feature("CIC Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures("api_config", "browser_cic_instance")
def test_unassign_cic(api_config, browser_cic_instance):
    assert QCL_5022_step4(api_config, browser_cic_instance)

