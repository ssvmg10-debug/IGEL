import time, allure
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()

def get_ssh():
    return SSHClient(host=device_cred["host"], user=device_cred["user"],
                     pwd=device_cred["pwd"], port=device_cred["port"])

def _assign(ums, wums, device, profile_key, default_name, api_config):
    profile = ums.get_profile_details(api_config.get(profile_key, default_name))
    wums.assign_object(device["id"], profile["id"], "profile")
    return profile

def _detach(ums, wums, device, profile_key, default_name, api_config):
    profile = ums.get_profile_details(api_config.get(profile_key, default_name))
    wums.detach_profile(device["id"], profile["id"])
from bussiness.onepassword_otp import OTPGenerator
from config.read_config import otp_secrets_cred

@allure.step("TC001 S1: Assign Entra ID profile, reboot, verify Microsoft login screen")
def TC001_step1(api_config, browser):
    try:
        ums  = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        wums = UMSWUMSApi(ums_cred["weburl"], ums_cred["username"], ums_cred["password"])
        dev  = ums.get_vm_details(device_cred["hostname"])
        _assign(ums, wums, dev, "entra_id_profile", "Entra-ID-SSO-Profile", api_config)
        ums.device_reboot(dev)
        logger.info("Waiting 90s for reboot…")
        time.sleep(90)
        result = click.is_text_present_on_screen("Microsoft", refresh_before_check=True)
        logger.info(f"Entra login screen: {result}")
        return result
    except Exception as e:
        logger.error(f"TC001_step1: {e}"); return False

@allure.step("TC001 S2: Authenticate with Entra ID creds + TOTP if required")
def TC001_step2(api_config, browser):
    try:
        click.type_text(api_config.get("entra_username", ""))
        click.press_key("Return")
        time.sleep(2)
        click.type_text(api_config.get("entra_password", ""))
        click.press_key("Return")
        time.sleep(3)
        secret = otp_secrets_cred.get("entra_otp_secret", "")
        if secret:
            click.type_text(OTPGenerator(secret).get_otp())
            click.press_key("Return")
            time.sleep(5)
        result = click.is_text_present_on_screen("desktop", refresh_before_check=True)
        logger.info(f"Desktop after Entra SSO: {result}")
        return result
    except Exception as e:
        logger.error(f"TC001_step2: {e}"); return False

@allure.step("TC001 S3: Verify Kerberos ticket via SSH klist")
def TC001_step3():
    try:
        ssh = get_ssh()
        out = ssh.exec("klist 2>&1"); ssh.close()
        ok = bool(out and ("Credentials cache" in out or "Ticket cache" in out))
        logger.info(f"Kerberos ticket present: {ok}")
        return ok
    except Exception as e:
        logger.error(f"TC001_step3: {e}"); return False

@allure.step("TC001 Cleanup: Unassign Entra ID profile")
def TC001_cleanup(api_config):
    try:
        ums  = UMS(ums_cred["base_url"], ums_cred["username"], ums_cred["password"])
        wums = UMSWUMSApi(ums_cred["weburl"], ums_cred["username"], ums_cred["password"])
        dev  = ums.get_vm_details(device_cred["hostname"])
        _detach(ums, wums, dev, "entra_id_profile", "Entra-ID-SSO-Profile", api_config)
        ums.device_reboot(dev); time.sleep(60)
        return True
    except Exception as e:
        logger.error(f"TC001_cleanup: {e}"); return False

@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC001_step1(api_config, browser_instance): assert TC001_step1(api_config, browser_instance)
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC001_step2(api_config, browser_instance): assert TC001_step2(api_config, browser_instance)
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.NORMAL)
def test_TC001_step3(): assert TC001_step3()
@allure.feature("SSO Validation")
@allure.severity(allure.severity_level.MINOR)
def test_TC001_cleanup(api_config): assert TC001_cleanup(api_config)
