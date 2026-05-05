"""
############################################################
## Test Case ID : QCL-3839
## Title        : Pingone SSO Login Validation on IGEL OS
##
## Description:
# Validates Pingone SSO authentication on IGEL OS and ensures
# credentials are successfully passed to applications running
# on the IGEL OS platform.
#
## Prerequisites:
# - Required UMS profiles must be created and available.
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
## Created On   : 16-Jan-2026
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
def QCL_3839_step1(api_config, browser):
    """ 
        Assigns the Pingone SSO UMS profile to the device (if required) 
        and verifies the pingone password screen.  
        Returns: 
            bool: True if the password screen is detected, else False. 
    """
    logger.info("step1: assigning profile and verifying password screen")

    try:
        
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        profile_sso = api_config["profile_sso_pingone"]
        profile_details = ums.get_profile_details(profile_sso)
        profile_id = profile_details["id"]
        browser.reload_page()
        assigned_list = ums.get_profile_assigned_device(device_details)
        already_assigned = any(item.get("assignee", {}).get("id") == profile_id for item in assigned_list)

        ssh = get_ssh()

        if already_assigned:
            logger.info("sso profile already assigned, verifying password screen")
            browser.reload_page()
            return click.is_text_present_on_screen("password", refresh_before_check=True)
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
            if assigned_now and ssh:
                if ssh.reboot():
                    time.sleep(1)
                    browser.reload_page()
                    logger.info("verifying password screen after reboot")
                    return click.is_text_present_on_screen("password", refresh_before_check=True)
                return False
    except Exception as e:
        logger.error(f"Exception in step1_assign_profile: {e}")
        return False


@allure.step("Step 2: Login using username and password")
def QCL_3839_step2(api_config , browser):
    """ 
        Performs Pingone SSO login using username and password 
        and verifies successful login to the local terminal. 
        Returns: 
            bool: True if login is successful, else False. 
    """
    logger.info("step2: login using username and password")
    try:
        pingone_username = api_config["pingone_username"]
        pingone_password = api_config["pingone_password"]
        browser.reload_page()
        click.click_text_on_screen("username", refresh_after_click=True)
        pyautogui.write(pingone_username, interval=0.05)
        time.sleep(1)
        click.click_text_on_screen("password", refresh_after_click=False)
        time.sleep(2)
        pyautogui.write(pingone_password, interval=0.05)
        time.sleep(1)
        click.click_text_on_screen("Sign On", refresh_after_click=True)
        time.sleep(7)
        return click.is_text_present_on_screen("local terminal", refresh_before_check=True)
    except Exception as e:
        logger.error(f"Exception in step2_login: {e}")
        return False


@allure.step("Step 3: Verify login fails without internet")
def QCL_3839_step3(browser):
    """ 
        Disables network connectivity on the device and verifies 
        that Pingone SSO login fails with a network error. 
        Returns: 
            bool: True if the expected network error is displayed, 
        else False. 
    """
    logger.info("step3: verify login fails without internet")
    try:
        ssh = get_ssh()
        if ssh:
            ssh.exec("export DISPLAY=:0 && xdotool key super+q")
            logger.info("locking the screen")
            time.sleep(1)
            ip = ssh.exec("echo $SSH_CLIENT").strip().split()[0]
            time.sleep(1)
            route = ssh.exec("ip route show default | awk '{print $3, \"dev\", $5}'").strip()
            time.sleep(1)
            ssh.exec(f"ip route add {ip} via {route}")
            time.sleep(1)
            ssh.exec("ip route del default")
            logger.info("internet connectivity disabled")
            time.sleep(5)
            browser.reload_page()
            click.click_text_on_screen("restart single sign-on", refresh_after_click=True)
            click.click_text_on_screen("restart single sign-on", refresh_after_click=False)
            time.sleep(5)
            return click.is_text_present_on_screen("Could not connect: Network is unreachable", refresh_before_check=True)
        return False
    except Exception as e:
        print(f"Exception in step3_check_no_internet: {e}")
        return False


@allure.step("Step 4: Verify login works with internet")
def QCL_3839_step4(browser):
    """ 
        Restores internet connectivity on the device and verifies 
        that the Pingone SSO login screen is displayed. 
        Returns: 
            bool: True if the password screen is shown, else False. 
    """
    logger.info("step4: verify login works with internet")
    try:
        ssh = get_ssh()
        if ssh:
            # ssh.exec("ip route add default via 192.168.10.254 dev ens192")
            route = ssh.exec("ip route show | awk '{print $3, \"dev\", $5}'").strip()
            time.sleep(1)
            ssh.exec(f"ip route add default via {route}")
            logger.info("internet connectivity restored")
            time.sleep(5)
            browser.reload_page()
            click.click_text_on_screen("restart single sign-on", refresh_after_click=True)
            return click.is_text_present_on_screen("password", refresh_before_check=True)
        return False
    except Exception as e:
        logger.error(f"Exception in step4_check_with_internet: {e}")
        return False


@allure.step("Step 5: Enable password screenlock")
def QCL_3839_step5(api_config, browser):
    """ 
        Enables password-based screen lock and verifies that 
        the password screen is displayed after locking. 
        Returns: 
            bool: True if the password screen is shown, else False. 
    """
    logger.info("step5: enable password screenlock")
    try:
        pingone_username = api_config["pingone_username"]
        pingone_password = api_config["pingone_password"]
        ssh = get_ssh()
        browser.reload_page()
        click.click_text_on_screen_strict("password", refresh_after_click=True)
        pyautogui.write(pingone_password)
        pyautogui.press("enter")
        time.sleep(5)
        ssh.exec("export DISPLAY=:0 && xdotool key super+q")
        time.sleep(5)
        pyautogui.press("enter")
        return click.is_text_present_on_screen("password", refresh_before_check=True)
    except Exception as e:
        print(f"Exception in step5_password_enable_screenlock: {e}")
        return False


@allure.step("Step 6: Disable password screenlock")
def QCL_3839_step6(api_config, browser):
    """ 
        Disables the password-based screen lock by assigning the 
        appropriate UMS profile and verifies that auto-login to the 
        local terminal works as expected. 
        Returns: 
            bool: True if auto-login is successful and the local terminal 
            is accessible, else False. 
    """
    logger.info("step6: disable password screenlock")
    try:
        pingone_username = api_config["pingone_username"]
        pingone_password = api_config["pingone_password"]
    
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        profile_disabled = api_config["profile_sso_disabled_pingone"]

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
        logger.info("disabled screen lock profile assigned and clicked ok")
        ssh = get_ssh()
        time.sleep(30)
        browser.reload_page()
        found=click.is_text_present_on_screen(pingone_username, refresh_before_check=True)
        if not found:
            click.click_text_on_screen("username", refresh_after_click=True)
            pyautogui.write(pingone_username, interval=0.05)
            time.sleep(1)
        click.click_text_on_screen("password", refresh_after_click=False)
        time.sleep(1)
        pyautogui.write(pingone_password, interval=0.05)
        time.sleep(1)
        click.click_text_on_screen("Sign On", refresh_after_click=True)
        time.sleep(5)
        ssh.exec("export DISPLAY=:0 && xdotool key super+q")
        time.sleep(8)
        pyautogui.press('enter')
        found=click.is_text_present_on_screen("local terminal")
        return found
    except Exception as e:
        logger.error(f"Exception in step6_password_disable_screenlock: {e}")
        return False


@allure.step("Step 7: Verify auto-login")
def QCL_3839_step7(api_config, browser):
    """ 
        Assigns the auto-login UMS profile if not already assigned 
        and verifies that auto-login to the local terminal works. 
        Returns: 
            bool: True if auto-login is successful and the local terminal 
            is accessible, else False. 
    """
    logger.info("step7: verify auto-login")
    try:
        ums = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        device_details = ums.get_vm_details(device_cred["hostname"])
        profile_auto = api_config["profile_sso_autologin_pingone"]
        profile_details = ums.get_profile_details(profile_auto)
        profile_id = profile_details["id"]
        
        assigned_list = ums.get_profile_assigned_device(device_details)
        already_assigned = any(item.get("assignee", {}).get("id") == profile_id for item in assigned_list)

        if not already_assigned:
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
            api.assign_profile( device_details["id"],profile_details["id"])
            time.sleep(2)
            click.click_text_on_screen("ok", refresh_after_click=True)
            time.sleep(15)
            browser.reload_page()
        return click.is_text_present_on_screen("local terminal")
    except Exception as e:
        print(f"Exception in step7_auto_login: {e}")
        return False


@allure.step("Step 8: Open browser and verify")
def QCL_3839_step8( browser):
    """ 
        Opens the browser on the remote device via SSH and navigates 
        to the pingone portal, then verifies that the expected user 
        element is visible. 
        Returns: 
            bool: True if the expected user element is found in the browser, 
            else False. 
    """
    logger.info("Starting Step 8: Open browser and verify")
    try:
        browser.reload_page()
        ssh = get_ssh()
        if ssh:
            click.click_text_on_screen("chromium browser", refresh_after_click=True)
            time.sleep(10)
            return click.is_text_present_on_screen("test user2", refresh_before_check=True)
        return False
    except Exception as e:
        logger.error(f"Exception in step8_open_browser: {e}")
        return False


@allure.step("Clean all assigned profiles")
def clean_up(api_config,browser):
    """ 
        Detaches all assigned UMS profiles from the device 
        and reboots the device to restore default state. 
        Returns: 
            bool: True if cleanup is successful, else False. 
    """
    logger.info("Cleaning up: detaching all assigned profiles")
    try:
        logger.info("Cleaning up: detaching all assigned profiles")
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
        # page.goto(target_hash_url, wait_until="load")
        page.goto(target_hash_url, wait_until="domcontentloaded")

        logger.info("page goto target")
        api= UMSWUMSApi(ums_cred["weburl"])
        api.set_bearer(bearer_token)
        ssh = get_ssh()
        for profile_key in ["profile_sso_pingone", "profile_sso_autologin_pingone", "profile_sso_disabled_pingone"]:

            browser.reload_page()
            profile_details = ums.get_profile_details(api_config[profile_key])
            api.detach_profile(device_details["id"], profile_details["id"])
            logger.info(f"Detached profile: {api_config[profile_key]}")
            click.click_text_on_screen("ok", refresh_after_click=True)
            time.sleep(10)

        ssh = get_ssh()
        if ssh:
            ssh.reboot()
            logger.info("device rebooted after cleanup")
            
        return True
    except Exception as e:
        logger.error(f"Exception in clean_up: {e}")
        return False


# ------------------------
# Tests
# ------------------------
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.usefixtures( "api_config", "browser_instance")
def test_QCL_3839_step1(api_config, browser_instance):
    assert QCL_3839_step1(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step2(api_config, browser_instance):
    assert QCL_3839_step2(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step3(browser_instance):
    assert QCL_3839_step3(browser_instance) 

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step4(browser_instance):
    assert QCL_3839_step4(browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step5(api_config, browser_instance):
    assert QCL_3839_step5(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step6(api_config, browser_instance):
    assert QCL_3839_step6(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step7(api_config, browser_instance):
    assert QCL_3839_step7(api_config, browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_QCL_3839_step8(browser_instance):
    assert QCL_3839_step8(browser_instance)

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_clean_up(api_config, browser_instance):
    assert clean_up(api_config, browser_instance)
