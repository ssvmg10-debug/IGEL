"""
############################################################
## Test Case ID : QCL-3912
## Title        : Open ID SSO Login Validation on IGEL OS
##
## Description:
# Validates Open ID SSO authentication on IGEL OS and ensures
# credentials are successfully passed to applications running
# on the IGEL OS platform.
#
## Prerequisites:
# - Required UMS profiles must be created and available.
#
## Test Scope:
# - Assign UMS profile to the device
# - Verify successful Open SSO login
# - Validate behavior without internet connectivity
# - Verify screen lock enabled and disabled scenarios
# - Validate auto-login functionality
#
## Author       : pooja.swadi
## Email        : pooja.swadi_ext@igel.com
## Created On   : 20-Jan-2026
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
from config.read_config import ums_cred, device_cred, otp_secrets_cred
from core.ssh.my_logger import logger
from core.api.auth_token import UMSAuthTokenService
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
@allure.step("Step 1: Assign profile and verify password screen")
def QCL_3912_step1(api_config, browser):
    """ 
        Assigns the Open ID SSO UMS profile to the device (if required) 
        and verifies the Open password screen.  
        Returns: 
            bool: True if the password screen is detected, else False. 
    """
    try:
        logger.info("Step 1: Assigns the Open ID SSO UMS profile to the device (if required) verifies the Open password screen.")
        logger.error("Step 1: Assigns the Open ID SSO UMS profile to the device (if required) verifies the Open password screen.")
        browser.reload_page()
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        profile_sso = api_config["profile_sso_openid"]
        profile_details = ums.get_profile_details(profile_sso)
        profile_id = profile_details["id"]
        browser.reload_page()
        assigned_list = ums.get_profile_assigned_device(device_details)
        already_assigned = any(item.get("assignee", {}).get("id") == profile_id for item in assigned_list)

        ssh = get_ssh()

        if already_assigned:
            logger.info("Profile already assigned, refreshing device")
            browser.reload_page()
            time.sleep(8)
            return click.is_text_present_on_screen("okta", refresh_before_check=True)
        else:
            
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
            print(device_details, profile_id)
            api.assign_profile( device_details["id"],profile_id)

            found_text_ok = click.click_text_on_screen("ok", refresh_after_click=True)
            logger.info(f"Found 'ok' text after profile assignment: {found_text_ok}")
            found_text_ok = click.click_text_on_screen("restart now", refresh_after_click=True)
            assigned_list = ums.get_profile_assigned_device(device_details)
            assigned_now = any(item.get("assignee", {}).get("id") == profile_id for item in assigned_list)
            logger.info(f"Profile assigned now: {assigned_now}")
            if assigned_now and ssh:
                if ssh.reboot():
                    time.sleep(1)
                    browser.reload_page()
                    return click.is_text_present_on_screen("okta", refresh_before_check=True)
                return False
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step1 Info: ")
        logger.error(f"Exception in step 1 Assign SSO Profile: {e}")
        return False

@allure.step("Step 2: Login using username and password")
def QCL_3912_step2(api_config,browser):
    """ 
        Performs Open ID SSO login using username and password 
        and verifies successful login to the local terminal. 
        Returns: 
            bool: True if login is successful, else False. 
    """
    try:
        logger.info("Step 2: Performs Open ID SSO login using username and password and verifies successful login to the local terminal.")
        logger.error("Step 2: Performs Open ID SSO login using username and password and verifies successful login to the local terminal.")
        Openid_username = api_config["openid_username"]
        Openid_password = api_config["openid_password"]
        browser.reload_page()
        time.sleep(8)
        if click.click_text_on_screen("Username", refresh_after_click=True):
            pyautogui.write(Openid_username, interval=0.05)
            time.sleep(1)
            click.click_text_on_screen("Password", refresh_after_click=False)
            time.sleep(2)
        pyautogui.write(Openid_password, interval=0.05)
        time.sleep(1)
        click.click_text_on_screen_strict("Sign in", refresh_after_click=True)
        pyautogui.press('tab', presses=2, interval=0.5)
        pyautogui.press('enter')
        time.sleep(7)
        return click.is_text_present_on_screen("local terminal", refresh_before_check=True)
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step2 Info: ")
        logger.error(f"Exception in QCL-3912 step2 Login: {e}")
        return False

@allure.step("Step 3: Verify login fails without internet")
def QCL_3912_step3(browser):
    """ 
        Disables network connectivity on the device and verifies 
        that Open ID SSO login fails with a network error. 
        Returns: 
            bool: True if the expected network error is displayed, 
        else False. 
    """
    try:
        logger.info("Step 3: Disables network connectivity on the device and verifies that Open ID SSO login fails with a network error.")
        logger.error("Step 3: Disables network connectivity on the device and verifies that Open ID SSO login fails with a network error.")
        ssh = get_ssh()
        if ssh:
            ssh.exec("export DISPLAY=:0 && xdotool key super+q")
            time.sleep(2)
            ip = ssh.exec("echo $SSH_CLIENT").strip().split()[0]
            time.sleep(2)
            route = ssh.exec("ip route show default | awk '{print $3, \"dev\", $5}'").strip()
            time.sleep(2)
            ssh.exec(f"ip route add {ip} via {route}")
            time.sleep(2)
            ssh.exec("ip route del default")
            time.sleep(5)
            browser.reload_page()
            time.sleep(5)
            click.click_text_on_screen("restart single sign-on", refresh_after_click=True)
            click.click_text_on_screen("restart single sign-on", refresh_after_click=False)
            click.click_text_on_screen("restart single sign-on", refresh_after_click=False)
            time.sleep(15)
            return click.is_text_present_on_screen("Could not connect: Network is unreachable", refresh_before_check=True)
        return False
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step3 Info: ")
        logger.error(f"Exception in step3 check no internet: {e}")      
        return False

@allure.step("Step 4: Verify login works with internet")
def QCL_3912_step4(browser):
    """ 
        Restores internet connectivity on the device and verifies 
        that the Open ID SSO login screen is displayed. 
        Returns: 
            bool: True if the password screen is shown, else False. 
    """
    try:
        logger.info("Step 4: Restores internet connectivity on the device and verifies that the Open ID SSO login screen is displayed.")
        logger.error("Step 4: Restores internet connectivity on the device and verifies that the Open ID SSO login screen is displayed.")
        ssh = get_ssh()
        if ssh:
            # ssh.exec("ip route add default via 192.168.10.254 dev ens192")
            route = ssh.exec("ip route show | awk '{print $3, \"dev\", $5}'").strip()
            time.sleep(1)
            ssh.exec(f"ip route add default via {route}")
            time.sleep(5)
            browser.reload_page()
            time.sleep(2)
            click.click_text_on_screen("restart single sign-on", refresh_after_click=True)
            time.sleep(5)
            return click.is_text_present_on_screen("password", refresh_before_check=True)
        return False
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step4 Info: ")
        logger.error(f"Exception in Step4 check with internet: {e}")
        return False

@allure.step("Step 5: Enable password screenlock")
def QCL_3912_step5(api_config,browser):
    """ 
        Enables password-based screen lock and verifies that 
        the password screen is displayed after locking. 
        Returns: 
            bool: True if the password screen is shown, else False. 
    """
    try:
        logger.info("Step 5: Enables password-based screen lock and verifies that the password screen is displayed after locking.")
        logger.error("Step 5: Enables password-based screen lock and verifies that the password screen is displayed after locking.")
        Openid_password = api_config["openid_password"]
        ssh = get_ssh()
        browser.reload_page()
        click.click_text_on_screen_strict("password", refresh_after_click=True)
        pyautogui.write(Openid_password)
        pyautogui.press("enter")
        time.sleep(5)
        ssh.exec("export DISPLAY=:0 && xdotool key super+q")
        time.sleep(5)
        pyautogui.press("enter")
        time.sleep(5)
        return click.is_text_present_on_screen("password", refresh_before_check=True)
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step5 Info: ")
        logger.error(f"Exception in Step5 password enable screenlock: {e}")
        return False

@allure.step("Step 6: Disable password screenlock")
def QCL_3912_step6(api_config, browser):
    """ 
        Disables the password-based screen lock by assigning the 
        appropriate UMS profile and verifies that auto-login to the 
        local terminal works as expected. 
        Returns: 
            bool: True if auto-login is successful and the local terminal 
            is accessible, else False. 
    """
    try:
        logger.info("Step 6: Disables the password-based screen lock by assigning the appropriate UMS profile and verifies that auto-login to the local terminal works as expected.")
        logger.info("Step 6: Disables the password-based screen lock by assigning the appropriate UMS profile and verifies that auto-login to the local terminal works as expected.")
        openid_username = api_config["openid_username"]
        openid_password = api_config["openid_password"]
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        profile_disabled = api_config["profile_sso_disabled_openid"]
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
        profile_details = ums.get_profile_details(profile_disabled)
        api.assign_profile( device_details["id"],profile_details["id"])

        click.click_text_on_screen("ok", refresh_after_click=True)

        ssh = get_ssh()
        time.sleep(30)
        browser.reload_page()
        click.click_text_on_screen("Username", refresh_after_click=True)
        pyautogui.write(openid_username, interval=0.05)
        click.click_text_on_screen("Password", refresh_after_click=False)
        time.sleep(2)
        pyautogui.write(openid_password, interval=0.05)

        click.click_text_on_screen_strict("Sign in", refresh_after_click=True)
        pyautogui.press('tab', presses=2, interval=0.5)
        pyautogui.press('enter')        
        time.sleep(5)
        ssh.exec("export DISPLAY=:0 && xdotool key super+q")
        time.sleep(8)
        pyautogui.press('enter')
        found=click.is_text_present_on_screen("local terminal")
        return found
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step6 Info: ")
        logger.error(f"Exception in Step6 password disable screenlock: {e}")
        return False


@allure.step("Step 7: Open browser and verify")
def QCL_3912_step7( browser):
    try:
        logger.info("Step 7: Opens the browser on the remote device via SSH and navigates to the  portal, then verifies that the expected user element is visible.")
        logger.error("Step 7: Opens the browser on the remote device via SSH and navigates to the  portal, then verifies that the expected user element is visible. - Error details")
        time.sleep(10)
        click.click_text_on_screen("Open ID Test URL", refresh_after_click=True)
        pyautogui.press('tab', presses=2, interval=0.5)
        pyautogui.press('enter')
        return click.is_text_present_on_screen("Shashi", refresh_before_check=True)
        return False
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Step-7 Info: ")
        logger.error(f"Exception in Step7 open browser: {e}")
        return False



@allure.step("Clean all assigned profiles")
def clean_up(api_config,browser):
    try:
        logger.info("Info on SSO functionality using Open-ID: UnAssign SSO profile and device config")
        logger.error("UnAssign SSO profile and device config: Errors")
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
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        ssh = get_ssh()
        for profile_key in ["profile_sso_openid", "profile_sso_disabled_openid"]:

            browser.reload_page()
            profile_details = ums.get_profile_details(api_config[profile_key])
            api.detach_profile(device_details["id"], profile_details["id"])
            click.click_text_on_screen("ok", refresh_after_click=True)
            time.sleep(10)


        ssh = get_ssh()
        if ssh:
            ssh.reboot()
        return True
    except Exception as e:
        logger.info(f"QCL-3912 Testcase Clean_up Info: ")
        logger.error(f"Exception in clean_up: {e}")
        return False

# ------------------------
# QCL-3912 Scenarios
# ------------------------
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_instance")
def test_QCL_3912_step1(api_config, browser_instance):
    assert QCL_3912_step1(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step2(api_config,browser_instance):
    assert QCL_3912_step2(api_config,browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step3(browser_instance):
    assert QCL_3912_step3(browser_instance) 

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step4(browser_instance):
    assert QCL_3912_step4(browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step5(api_config,browser_instance):
    assert QCL_3912_step5(api_config,browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step6(api_config, browser_instance):
    assert QCL_3912_step6(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3912_step7(browser_instance):
    assert QCL_3912_step7(browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_clean_up(api_config,browser_instance):
    assert clean_up(api_config,browser_instance)


 