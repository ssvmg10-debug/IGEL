import time, allure
from core.api.UMS import UMS
from core.ssh.ssh import SSHClient
from config.read_config import ums_cred, device_cred
from core.ssh.my_logger import logger
from core.api.ums_wums_api import UMSWUMSApi

def get_ssh(): return SSHClient(host=device_cred["host"],user=device_cred["user"],pwd=device_cred["pwd"],port=device_cred["port"])

@allure.step("TC010 S1: Install Chromium version A via UMS profile, verify via igelpkgctl")
def TC010_step1(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof_a=ums.get_profile_details(api_config.get("chromium_profile_a","Chromium-VersionA-Profile"))
        wums.assign_object(dev["id"],prof_a["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        ssh=get_ssh(); out=ssh.exec("igelpkgctl list installed 2>&1 | grep -i chromium"); ssh.close()
        ok=bool(out and "chromium" in out.lower())
        logger.info(f"Chromium A installed: {ok} — {(out or '')[:100]}"); return ok
    except Exception as e: logger.error(f"TC010_step1: {e}"); return False

@allure.step("TC010 S2: Upgrade to Chromium version B, verify new version active via SSH")
def TC010_step2(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof_b=ums.get_profile_details(api_config.get("chromium_profile_b","Chromium-VersionB-Profile"))
        wums.assign_object(dev["id"],prof_b["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        ssh=get_ssh(); out=ssh.exec("igelpkgctl list installed 2>&1 | grep -i chromium"); ssh.close()
        ver_b=api_config.get("chromium_version_b","")
        ok=bool(out and (ver_b in out if ver_b else "chromium" in out.lower()))
        logger.info(f"Chromium B installed: {ok}"); return ok
    except Exception as e: logger.error(f"TC010_step2: {e}"); return False

@allure.step("TC010 S3: Downgrade to Chromium version A, verify downgrade via SSH")
def TC010_step3(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        prof_b=ums.get_profile_details(api_config.get("chromium_profile_b","Chromium-VersionB-Profile"))
        wums.detach_profile(dev["id"],prof_b["id"])
        prof_a=ums.get_profile_details(api_config.get("chromium_profile_a","Chromium-VersionA-Profile"))
        wums.assign_object(dev["id"],prof_a["id"],"profile"); ums.device_reboot(dev); time.sleep(90)
        ssh=get_ssh(); out=ssh.exec("igelpkgctl list installed 2>&1 | grep -i chromium"); ssh.close()
        ver_a=api_config.get("chromium_version_a","")
        ok=bool(out and (ver_a in out if ver_a else "chromium" in out.lower()))
        logger.info(f"Chromium downgraded to A: {ok}"); return ok
    except Exception as e: logger.error(f"TC010_step3: {e}"); return False

@allure.step("TC010 Cleanup: Unassign all Chromium profiles")
def TC010_cleanup(api_config):
    try:
        ums=UMS(ums_cred["base_url"],ums_cred["username"],ums_cred["password"])
        wums=UMSWUMSApi(ums_cred["weburl"],ums_cred["username"],ums_cred["password"])
        dev=ums.get_vm_details(device_cred["hostname"])
        for key,default in [("chromium_profile_a","Chromium-VersionA-Profile"),("chromium_profile_b","Chromium-VersionB-Profile")]:
            try: prof=ums.get_profile_details(api_config.get(key,default)); wums.detach_profile(dev["id"],prof["id"])
            except: pass
        ums.device_reboot(dev); time.sleep(60); return True
    except Exception as e: logger.error(f"TC010_cleanup: {e}"); return False

@allure.feature("App Lifecycle")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC010_step1(api_config): assert TC010_step1(api_config),"Chromium version A not installed."
@allure.feature("App Lifecycle")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC010_step2(api_config): assert TC010_step2(api_config),"Chromium upgrade to B failed."
@allure.feature("App Lifecycle")
@allure.severity(allure.severity_level.CRITICAL)
def test_TC010_step3(api_config): assert TC010_step3(api_config),"Chromium downgrade to A failed."
@allure.feature("App Lifecycle")
@allure.severity(allure.severity_level.MINOR)
def test_TC010_cleanup(api_config): assert TC010_cleanup(api_config),"TC010 cleanup failed."
