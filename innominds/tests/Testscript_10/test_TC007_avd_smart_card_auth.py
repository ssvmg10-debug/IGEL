import time, allure
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from core.ui.ui_automation_text import OcrUiInteractor
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

click = OcrUiInteractor()
def get_ssh(): return SSHClient(host=device_cred["host"],user=device_cred["user"],pwd=device_cred["pwd"],port=device_cred["port"])

@allure.step("TC007 S1: Verify OpenSC/smart card middleware active via SSH")
def TC007_step1():
    try:
        ssh=get_ssh(); out=ssh.exec("pkcs11-tool --list-slots 2>&1 || opensc-tool --list-readers 2>&1"); ssh.close()
        ok=bool(out and ("Slot" in out or "reader" in out.lower()))
        logger.info(f"Smart card middleware: {ok}"); return ok
    except Exception as e: logger.error(f"TC007_step1: {e}"); return False

@allure.step("TC007 S2: Assign AVD CBA profile, reboot, verify PIN prompt in VNC")
def TC007_step2(api_config, browser):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("avd_smartcard_profile","AVD-SmartCard-CBA-Profile"))
        wums.assign_object(dev["id"],prof["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        result=click.is_text_present_on_screen("PIN",refresh_before_check=True)
        logger.info(f"Smart card PIN prompt: {result}"); return result
    except Exception as e: logger.error(f"TC007_step2: {e}"); return False

@allure.step("TC007 S3: Enter smart card PIN, verify AVD session via CBA")
def TC007_step3(api_config, browser):
    try:
        click.type_text(api_config.get("smartcard_pin","")); click.press_key("Return"); time.sleep(10)
        result=(click.is_text_present_on_screen("desktop",refresh_before_check=True) or
                click.is_text_present_on_screen("Azure",refresh_before_check=True))
        logger.info(f"AVD via CBA: {result}"); return result
    except Exception as e: logger.error(f"TC007_step3: {e}"); return False

@allure.step("TC007 S4: Check journalctl for certificate errors")
def TC007_step4():
    try:
        ssh=get_ssh()
        out=ssh.exec("journalctl --no-pager -n 100 2>&1 | grep -i 'cert.*error\\|error.*cert' | tail -5"); ssh.close()
        if out and "error" in out.lower(): logger.error(f"Cert errors: {out}"); return False
        return True
    except Exception as e: logger.error(f"TC007_step4: {e}"); return False

@allure.step("TC007 Cleanup: Unassign AVD smart card profile")
def TC007_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof=ums.get_profile_details(api_config.get("avd_smartcard_profile","AVD-SmartCard-CBA-Profile"))
        wums.detach_profile(dev["id"],prof["id"]); ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC007_cleanup: {e}"); return False

@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC007_step1(): assert TC007_step1(),"Smart card middleware not active."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC007_step2(api_config,browser_instance): assert TC007_step2(api_config,browser_instance),"PIN prompt not shown."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC007_step3(api_config,browser_instance): assert TC007_step3(api_config,browser_instance),"CBA session did not launch."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.NORMAL)
def test_TC007_step4(): assert TC007_step4(),"Certificate errors in journalctl."
@allure.feature("Session Connection")
@allure.severity(allure.severity_level.MINOR)
def test_TC007_cleanup(api_config): assert TC007_cleanup(api_config),"TC007 cleanup failed."
