###########################################################
# Test Case ID : QCL-4438
# Title        : Post Session Command Validation
#
# Description :
# Validate enabling post session command for applications
# via profile configuration and applying it to device.
#
# Steps:
# Step 0 → Device Precheck + Registration + SSH Validation
# Step 1 → Create Profile + Update Config + Assign Profile
#
# Author : Sai Arokala
# Version: 1.0
###########################################################
import time
import os
import yaml
import pytest
import allure
import json
import pyautogui
import requests
from core.api.wums_api import UMSWUMSApi
from core.ssh.ssh_client import SSHClientIGEL
from core.utils.logger import get_logger, step_log_context
from core.utils.ocr_utils import screen_contains_text
from core.utils.vnc_client import open_vnc, capture_vnc_screenshot

log = get_logger(__name__)

# ==========================================================
# YAML LOADER
# ==========================================================
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)


def load_yaml():
    yaml_path = os.path.join(PROJECT_ROOT, "testdata", "tc_qcl_data.yaml")

    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


# ==========================================================
# STEP HELPERS
# ==========================================================
def step_start(step):
    log.info(f"[STEP {step} START]")


def step_end(step):
    log.info(f"[STEP {step} END]")


# ==========================================================
# PROFILE HELPER
# ==========================================================
def get_profile_id(ctx):
    if ctx.get("profile_id"):
        return ctx["profile_id"]

    api = ctx["api"]
    name = ctx["profile_cfg"]["name"]

    resp = api._request("get", "/umsapi/v3/profiles")
    data = resp.json()

    profiles = data.get("items") if isinstance(data, dict) else data

    matched = [p for p in profiles if p.get("name") == name]

    if not matched:
        raise RuntimeError(f"Profile not found: {name}")

    latest = max(matched, key=lambda x: int(x.get("id")))
    ctx["profile_id"] = int(latest["id"])

    return ctx["profile_id"]


def wait_for_ssh(dev, attempts=12, delay=15):
    ssh = SSHClientIGEL(
        host=dev["device_ip"],
        port=22,
        username="root"
    )

    assert ssh.reconnect_with_retry(attempts, delay), \
        "SSH not reachable"

    return ssh


# ==========================================================
# Journalctl log helper
# ==========================================================
def wait_for_log(
        ssh,
        command,
        expected_text,
        retries=12,
        delay=10,
        match_last_line=False
):
    """
    Execute command over SSH and wait until expected_text appears.

    Args:
        ssh: SSHClientIGEL instance (connected)
        command: command to execute
        expected_text: text to search in output
        retries: number of attempts
        delay: wait between attempts (seconds)
        match_last_line: if True → only check last line

    Returns:
        True if found, else False
    """

    for attempt in range(retries):

        stdin, stdout, stderr = ssh.client.exec_command(command)
        output = stdout.read().decode()

        log.info(f"[LOG CHECK] Attempt {attempt + 1}")
        print(f"\n--- LOG OUTPUT (Attempt {attempt + 1}) ---\n{output}")

        # --------------------------------------------------
        # MATCH LOG
        # --------------------------------------------------
        if match_last_line:
            lines = output.strip().splitlines()
            if lines and expected_text in lines[-1]:
                return True
        else:
            if expected_text in output:
                return True

        time.sleep(delay)

    return False


# ==========================================================
# CONTEXT
# ==========================================================
@pytest.fixture(scope="session")
def tc4438_context():
    # -----------------------------
    # LOAD MAIN CONFIG (UMS creds)
    # -----------------------------
    config_path = os.path.join(PROJECT_ROOT, "testdata", "tc_qcl_data.yaml")

    with open(config_path, "r") as f:
        CFG = yaml.safe_load(f)

    # -----------------------------
    # LOAD TEST DATA YAML
    # -----------------------------
    yaml_data = load_yaml()

    device_cfg = yaml_data["QCL_4438_device"]
    profile_cfg = yaml_data["QCL_4438_profile"]

    # -----------------------------
    # INIT API
    # -----------------------------
    api = UMSWUMSApi(
        base_url=CFG["ums"]["base_url"],
        username=CFG["ums"]["username"],
        password=CFG["ums"]["password"]
    )

    return {
        "CFG": CFG,
        "api": api,
        "device_cfg": device_cfg,
        "profile_cfg": profile_cfg,
        "device_id": None,
        "profile_id": None,
        "directory_id": None
    }


# ==========================================================
# Vmware power-on VM helper
# ==========================================================
def power_on_vm_vcenter(ctx):
    vcenter = ctx["CFG"]["vcenter"]

    base_url = vcenter["base_url"]
    username = vcenter["username"]
    password = vcenter["password"]
    vm_id = vcenter["vm_id"]

    requests.packages.urllib3.disable_warnings()

    # --------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------
    session_resp = requests.post(
        f"{base_url}/api/session",
        auth=(username, password),
        verify=False
    )

    assert session_resp.status_code in (200, 201), \
        f"Failed to create vCenter session: {session_resp.text}"

    session_id = session_resp.text.strip('"')

    # --------------------------------------------------
    # POWER ON VM
    # --------------------------------------------------
    power_resp = requests.post(
        f"{base_url}/api/vcenter/vm/{vm_id}/power?action=start",
        headers={
            "vmware-api-session-id": session_id
        },
        verify=False
    )

    assert power_resp.status_code in (200, 201, 204), \
        f"VM power ON failed: {power_resp.text}"

    log.info("VM powered ON successfully")


# ==========================================================
# HELPERS
# ==========================================================
def get_device_id(ctx):
    if ctx.get("device_id"):
        return ctx["device_id"]

    ctx["device_id"] = ctx["api"].get_device_id(
        ctx["device_cfg"]["device_name"]
    )
    return ctx["device_id"]


# ==========================================================
# STEP 0 → DEVICE PRECHECK + REGISTRATION
# ==========================================================
def step_0_device_precheck(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    CFG = ctx["CFG"]

    with allure.step("Device precheck + registration"):
        # cleanup if exists
        api.cleanup_device_if_exists(dev["device_name"])

        # directory
        directory_id = api.get_directory_id(dev["target_folder"])

        # scan
        api.scan_devices()
        time.sleep(CFG["timeouts"]["scan_wait"])

        # register
        api.register_device(
            directory_id=directory_id,
            mac=dev["mac"],
            ip=dev["device_ip"]
        )

        time.sleep(10)

        # resolve device
        device_id = get_device_id(ctx)
        log.info(f"Device ID: {device_id}, device registered successfully")

        # enable ssh/vnc + reboot
        api.enable_ssh_vnc(device_id)
        api.reboot_device(device_id)

        time.sleep(CFG["timeouts"]["reboot_wait"])

        # validate ssh
        ssh = wait_for_ssh(dev)

        ssh.close()


# ==========================================================
# STEP 1 → PROFILE CREATE + CONFIG UPDATE + ASSIGN
# ==========================================================
def step_1_profile_post_session(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]
    step_start("1 Create profile + enable post session command")

    with allure.step("Create profile + enable post session command"):
        # --------------------------------------------------
        # Create profile
        # --------------------------------------------------
        parent_id = profile_cfg["parent_directory_id"]
        directory_name = profile_cfg["profile_directory"]

        directory_id = api.get_or_create_profile_directory(
            directory_name=directory_name,
            parent_directory_id=parent_id
        )

        apps = [
            {
                "appLineId": app["appLineId"],
                "appVersionId": None
            }
            for app in profile_cfg["applications"]
        ]

        resp = api.create_profile(
            name=profile_cfg["name"],
            description=profile_cfg["description"],
            directory_id=directory_id,
            apps=apps
        )

        print("CREATE PROFILE RESPONSE:", resp)

        profile_id = resp.get("id") or resp.get("data", {}).get("id")
        assert profile_id, f"Profile creation failed: {resp}"

        ctx["profile_id"] = profile_id  # CACHE

        assert profile_id, f"Profile creation failed: {resp}"

        # --------------------------------------------------
        # UPDATE PROFILE CONFIG (POST SESSION ENABLE)
        # --------------------------------------------------
        device_id = get_device_id(ctx)

        data_payload = """
        {
          "app.chromium.sessions.chromium":{
            "instancesToAdd":{
              "1773808018887ac711b01-6cdb-49bb-8003-c893ef36ebae":{}
            },
            "instancesToRemove":[],
            "instances":{},
            "type":1
          },
          "app.horizon.sessions.vdm_client":{
            "instancesToAdd":{
              "17738080382648762ab0c-6984-434a-b76f-eada34d0e4ed":{}
            },
            "instancesToRemove":[],
            "instances":{},
            "type":1
          },
          "app.horizon.postsession.enabled":{
            "uiType":"bool",
            "value":true,
            "type":2
          },
          "app.horizon.postsession.command":{
            "uiType":"editable",
            "value":"custom",
            "type":2
          },
          "app.chromium.postsession.enabled":{
            "uiType":"bool",
            "value":true,
            "type":2
          },
          "app.chromium.postsession.command":{
            "uiType":"editable",
            "value":"custom",
            "type":2
          }
        }
        """

        api.update_profile_configuration(
            profile_id=profile_id,
            data_payload=data_payload,
            send_now=False
        )

        log.info("Post session command enabled in profile")

        # --------------------------------------------------
        # ASSIGN PROFILE
        # --------------------------------------------------
        max_retries = 3
        apps_to_validate = [app["appname"] for app in profile_cfg["applications"]]

        for attempt in range(1, max_retries + 1):
            log.info(f"Attempt {attempt}: Assign → SSH reboot → validate apps")

            # --------------------------------------------------
            # ASSIGN PROFILE
            # --------------------------------------------------
            api.assign_profile(
                device_id=device_id,
                profile_id=profile_id
            )
            log.info("Profile assigned")

            # --------------------------------------------------
            # WAIT AFTER ASSIGN
            # --------------------------------------------------
            time.sleep(30)

            # --------------------------------------------------
            # SSH CONNECT (BEFORE REBOOT)
            # --------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            if not ssh.reconnect_with_retry(attempts=6, delay_sec=10):
                log.warning("SSH not reachable before reboot, retrying...")
                continue

            # --------------------------------------------------
            # REBOOT USING SSH COMMAND (IMPORTANT CHANGE)
            # --------------------------------------------------
            log.info("Rebooting device using SSH command")
            ssh.run_command("reboot")
            ssh.close()
            time.sleep(40)

            # --------------------------------------------------
            # SSH CONNECT AFTER REBOOT
            # --------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            if not ssh.reconnect_with_retry(attempts=12, delay_sec=15):
                log.warning("SSH not reachable after reboot, retrying...")
                continue

            # --------------------------------------------------
            # VALIDATE INSTALLED APPS
            # --------------------------------------------------
            time.sleep(20)
            rc, stdout, stderr = ssh.run_command("igelpkgctl list installed")
            ssh.close()

            log.info(f"[INSTALLED PACKAGES]\n{stdout}")

            all_present = True
            for app in apps_to_validate:
                if app.lower() not in stdout.lower():
                    log.warning(f"App NOT found: {app}")
                    all_present = False
                    break
                else:
                    log.info(f"App found: {app}")

            if all_present:
                log.info("All apps validated successfully")
                break

            if attempt == max_retries:
                assert False, f"Apps not installed after {max_retries} attempts"

            log.info("Retrying full flow...")

    step_end("completed Create profile + enable post session command")


# ==========================================================
# STEP 2 → VALIDATE POST SESSION LOG
# ==========================================================
def step_2_validate_post_session_log(ctx):
    dev = ctx["device_cfg"]

    step_start("2 Validate 'Waiting for sessions to start...' in logs")

    with allure.step("Validate 'Waiting for sessions to start...' in logs"):
        ssh = wait_for_ssh(dev)

        assert wait_for_log(
            ssh,
            command="journalctl -eu igel-pcomd",
            expected_text="Waiting for sessions to start...",
            retries=12,
            delay=10,
            match_last_line=True  # optional strict check
        ), "Expected log not found"

        ssh.close()
    step_end("2 Successfully Validated 'Waiting for sessions to start...' in logs")


# ==========================================================
# STEP 3 → UPDATE PROFILE (SHUTDOWN) + APPLY + REBOOT
# ==========================================================
def step_3_update_profile_shutdown(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]

    step_start("3 Update profile → postsession command = shutdown")

    with allure.step("Update profile → postsession command = shutdown"):
        # --------------------------------------------------
        # GET PROFILE ID
        # --------------------------------------------------
        profile_id = get_profile_id(ctx)

        log.info(f"Resolved profile ID: {profile_id}")

        # --------------------------------------------------
        # UPDATE PAYLOAD (SHUTDOWN)
        # --------------------------------------------------
        data_payload = json.dumps({
            "app.chromium.postsession.command": {
                "uiType": "editable",
                "value": "shutdown",
                "type": 2
            },
            "app.horizon.postsession.command": {
                "uiType": "editable",
                "value": "shutdown",
                "type": 2
            }
        })

        api.update_profile_configuration(
            profile_id=profile_id,
            data_payload=data_payload,
            send_now=True  # IMPORTANT
        )

        log.info("Profile updated with shutdown command")

        # --------------------------------------------------
        # WAIT FOR APPLY
        # --------------------------------------------------
        time.sleep(20)

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        ssh = SSHClientIGEL(
            host=dev["device_ip"],
            port=22,
            username="root"
        )

        if not ssh.reconnect_with_retry(attempts=6, delay_sec=10):
            log.warning("SSH not reachable before reboot, retrying...")

        # --------------------------------------------------
        # REBOOT USING SSH COMMAND (IMPORTANT CHANGE)
        # --------------------------------------------------
        log.info("Rebooting device using SSH command")
        ssh.run_command("reboot")
        ssh.close()

        # --------------------------------------------------
        # WAIT FOR REBOOT
        # --------------------------------------------------
        time.sleep(20)

        # --------------------------------------------------
        # SSH RECONNECT VALIDATION
        # --------------------------------------------------
        ssh = wait_for_ssh(dev)

        log.info("SSH reconnected successfully after shutdown config")

        ssh.close()

    step_start("3 completed Update profile → postsession command = shutdown")


# ==========================================================
# STEP 4 → POST SESSION EXECUTION VALIDATION
# ==========================================================
def step_4_validate_shutdown_flow(ctx):
    dev = ctx["device_cfg"]
    CFG = ctx["CFG"]
    vcenter = CFG["vcenter"]

    log.info("STEP 4 started: VNC + SSH validation")

    vnc_proc = None
    ssh_log = None
    ssh_cmd = None

    try:
        # ==================================================
        # STEP A → OPEN VNC
        # ==================================================
        with allure.step("Open TigerVNC session"):
            ssh = wait_for_ssh(dev)

            vnc_proc = open_vnc(dev["device_ip"])

            log.info("VNC launched")
            time.sleep(10)

            pyautogui.click(500, 400)
            time.sleep(2)

        # ==================================================
        # STEP B → SSH LOG SESSION
        # ==================================================
        with allure.step("Start journalctl monitoring"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)

            shell = ssh_log.client.invoke_shell()
            time.sleep(1)

            # clear buffer
            while shell.recv_ready():
                shell.recv(4096)

            shell.send("journalctl -efu igel-pcomd -n 0\n")
            time.sleep(2)

        # ==================================================
        # STEP C → SSH COMMAND SESSION
        # ==================================================
        with allure.step("Start Chromium session"):

            ssh_cmd = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_cmd.reconnect_with_retry(12, 15)

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
            )

            log.info("Chromium launched")

            time.sleep(3)

        # ==================================================
        # STEP D → VALIDATE LOGS
        # ==================================================
        with allure.step("Validate Chromium session logs"):

            start_time = time.time()
            tracking_found = False
            active_found = False

            while time.time() - start_time < 20:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    print("\n--- LIVE LOG ---\n", output)

                    if "Start tracking process" in output and "chromium" in output.lower():
                        tracking_found = True

                    if tracking_found and active_found:
                        break

                time.sleep(0.5)

            assert tracking_found, "Tracking log not found"

        # ==================================================
        # STEP E → WMCTRL VALIDATION
        # ==================================================
        with allure.step("Validate Chromium window"):

            _, output, _ = ssh_cmd.run_command(
                "su user -c 'DISPLAY=:0 wmctrl -lx'"
            )

            log.info(f"wmctrl output:\n{output}")

            assert "chromium" in output.lower(), \
                "Chromium window not detected"

        # ==================================================
        # STEP F → KILL CHROMIUM (FRESH SESSION)
        # ==================================================
        with allure.step("Kill Chromium (fresh session)"):

            ssh_kill = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill.reconnect_with_retry(12, 10), \
                "SSH kill session failed"

            ssh_kill.run_command("pkill -9 -f chromium")

            log.info("Chromium terminated from SSH session")

            ssh_kill.close()

        # ==================================================
        # STEP G → VALIDATE SHUTDOWN
        # ==================================================
        with allure.step("Validate device shutdown"):

            ssh_cmd.close()
            ssh_log.close()

            time.sleep(10)

            ssh_check = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert not ssh_check.reconnect_with_retry(
                attempts=2,
                delay_sec=10
            ), "Device did NOT shutdown"

            log.info("Device shutdown confirmed")

        # ==================================================
        # STEP H → POWER ON VM
        # ==================================================
        with allure.step("Power ON VM"):

            requests.packages.urllib3.disable_warnings()

            session_resp = requests.post(
                f"{vcenter['base_url']}/api/session",
                auth=(vcenter["username"], vcenter["password"]),
                verify=False
            )

            assert session_resp.status_code in (200, 201)

            session_id = session_resp.text.strip('"')

            power_resp = requests.post(
                f"{vcenter['base_url']}/api/vcenter/vm/{vcenter['vm_id']}/power?action=start",
                headers={"vmware-api-session-id": session_id},
                verify=False
            )

            assert power_resp.status_code in (200, 201, 202, 204)

            log.info("VM powered ON")

        # ==================================================
        # STEP I → SSH VALIDATION
        # ==================================================
        with allure.step("Validate SSH after power ON"):

            time.sleep(30)

            ssh_final = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_final.reconnect_with_retry(12, 15)

            ssh_final.close()

    except Exception:
        log.error("STEP 4 failed", exc_info=True)
        raise

    finally:
        log.info("STEP 4 cleanup")

        if ssh_cmd:
            try:
                ssh_cmd.close()
            except:
                pass

        if ssh_log:
            try:
                ssh_log.close()
            except:
                pass

        if vnc_proc:
            try:
                vnc_proc.terminate()
            except:
                pass


# ==========================================================
# STEP 5 → UPDATE PROFILE (LOGOFF + LOCAL LOGIN) + REBOOT
# ==========================================================
def step_5_update_profile_logoff(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]
    CFG = ctx["CFG"]

    with allure.step("Update profile → postsession = logoff + enable local login"):
        # --------------------------------------------------
        # GET PROFILE ID
        # --------------------------------------------------
        profile_id = get_profile_id(ctx)

        log.info(f"[STEP5] Using profile ID: {profile_id}")

        # --------------------------------------------------
        # PREPARE PAYLOAD
        # --------------------------------------------------
        data_payload = json.dumps({
            "auth.login.xlock": {
                "uiType": "bool",
                "value": True,
                "type": 2
            },
            "sessions.xlock": {
                "instancesToAdd": {},
                "instancesToRemove": [],
                "instances": {
                    "0": {
                        "options.password": {
                            "uiType": "string",
                            "value": "inno121976",
                            "type": 2
                        }
                    }
                },
                "type": 1
            },
            "app.chromium.postsession.command": {
                "uiType": "editable",
                "value": "logoff",
                "type": 2
            },
            "app.horizon.postsession.command": {
                "uiType": "editable",
                "value": "logoff",
                "type": 2
            }
        })

        # --------------------------------------------------
        # CALL API
        # --------------------------------------------------
        api.update_profile_configuration(
            profile_id=profile_id,
            data_payload=data_payload,
            send_now=True  # IMPORTANT
        )

        log.info("[STEP5] Profile updated with logoff + local login")

        # --------------------------------------------------
        # WAIT FOR APPLY
        # --------------------------------------------------
        time.sleep(20)

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        device_id = get_device_id(ctx)

        api.reboot_device(device_id)

        log.info("[STEP5] Device reboot triggered")

        # --------------------------------------------------
        # WAIT FOR REBOOT
        # --------------------------------------------------
        time.sleep(CFG["timeouts"]["reboot_wait"])

        # --------------------------------------------------
        # SSH RECONNECT VALIDATION
        # --------------------------------------------------
        ssh = wait_for_ssh(dev)

        log.info("[STEP5] SSH reconnected successfully")

        time.sleep(30)

        ssh.close()


# ==========================================================
# STEP 6 → LOGOFF VALIDATION (VNC + JOURNALCTL + REPEAT)
# ==========================================================
def step_6_validate_logoff_flow(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    CFG = ctx["CFG"]
    profile_cfg = ctx["profile_cfg"]

    vcenter = CFG["vcenter"]

    log.info("STEP 6 started: Logoff validation")

    vnc_proc = None
    ssh_root = None
    ssh_user = None

    try:
        # ==================================================
        # STEP A → OPEN VNC + LOGIN
        # ==================================================
        with allure.step("Open VNC and login"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)
            vnc_proc = open_vnc(dev["device_ip"])
            time.sleep(10)

            pyautogui.typewrite("inno121976")
            pyautogui.press("enter")

            time.sleep(8)
            log.info("VNC login completed")

            # ==================================================
            # STEP B → SSH LOG SESSION
            # ==================================================
            with allure.step("Start journalctl monitoring"):

                ssh_log = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh_log.reconnect_with_retry(12, 15)

                shell = ssh_log.client.invoke_shell()
                time.sleep(1)

                while shell.recv_ready():
                    shell.recv(4096)

                shell.send("journalctl -efu igel-pcomd -n 0\n")
                time.sleep(5)

            # ==================================================
            # STEP C → SSH COMMAND SESSION
            # ==================================================
            with allure.step("Start Chromium session"):

                ssh_cmd = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh_cmd.reconnect_with_retry(12, 15)

                time.sleep(3)

                ssh_cmd.client.exec_command(
                    "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
                )

                log.info("Chromium launched")
                time.sleep(3)

            # ==================================================
            # STEP D → VALIDATE LOGS
            # ==================================================
            with allure.step("Validate Chromium session logs"):

                start_time = time.time()
                tracking_found = False

                while time.time() - start_time < 40:

                    if shell.recv_ready():
                        output = shell.recv(4096).decode()

                        print("\n--- LIVE LOG ---\n", output)

                        if "tracking" in output.lower() and "chromium" in output.lower():
                            tracking_found = True
                            break

                    time.sleep(0.5)

                assert tracking_found, "Tracking log not found"

            # ==================================================
            # STEP E → WMCTRL VALIDATION
            # ==================================================
            with allure.step("Validate Chromium window"):

                _, output, _ = ssh_cmd.run_command(
                    "su user -c 'DISPLAY=:0 wmctrl -lx'"
                )

                log.info(f"wmctrl output:\n{output}")

                assert "chromium" in output.lower()

            # ==================================================
            # STEP F → KILL CHROMIUM
            # ==================================================
            with allure.step("Kill Chromium (fresh session)"):

                ssh_kill = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh_kill.reconnect_with_retry(12, 10)

                ssh_kill.run_command("pkill -9 -f chromium")
                ssh_kill.close()

        # ==================================================
        # STEP G → VALIDATE SESSION DONE
        # ==================================================
        with allure.step("Validate session done log"):

            done_found = False
            start_time = time.time()

            while time.time() - start_time < 40:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    if "Session done: Chromium" in output:
                        done_found = True
                        break

                time.sleep(1)

            assert done_found, "Session done log not found"

        # ==================================================
        # STEP H → OCR LOGIN SCREEN
        # ==================================================
        with allure.step("Validate login screen via OCR"):

            time.sleep(5)

            found = False
            for i in range(5):
                if screen_contains_text("Unlock Desktop"):
                    found = True
                    break
                time.sleep(3)

            screenshot = capture_vnc_screenshot(dev["device_ip"])
            allure.attach.file(
                screenshot,
                name="login_screen_ocr",
                attachment_type=allure.attachment_type.PNG
            )

            assert found

        # ==================================================
        # DISABLE LOGIN
        # ==================================================
        with allure.step("Disable local login"):

            profile_id = get_profile_id(ctx)

            payload = json.dumps({
                "auth.login.xlock": {
                    "uiType": "bool",
                    "value": False,
                    "type": 2,
                    "deleteValue": True
                }
            })

            api.update_profile_configuration(
                profile_id=profile_id,
                data_payload=payload,
                send_now=True
            )

            time.sleep(20)

        # ==================================================
        # REBOOT
        # ==================================================
        with allure.step("Reboot after disabling login"):

            device_id = get_device_id(ctx)
            api.reboot_device(device_id)

            time.sleep(30)


            with allure.step("Open VNC and login"):

                ssh_log = SSHClientIGEL(
                    host=dev["device_ip"],
                    port=22,
                    username="root"
                )

                assert ssh_log.reconnect_with_retry(12, 15)

                vnc_proc = open_vnc(dev["device_ip"])
                time.sleep(10)

                log.info("VNC opened successfully")

                with allure.step("Start journalctl monitoring"):

                    ssh_log = SSHClientIGEL(
                        host=dev["device_ip"],
                        port=22,
                        username="root"
                    )

                    assert ssh_log.reconnect_with_retry(12, 15)

                    shell = ssh_log.client.invoke_shell()
                    time.sleep(1)

                    while shell.recv_ready():
                        shell.recv(4096)

                    shell.send("journalctl -efu igel-pcomd -n 0\n")
                    time.sleep(5)

                with allure.step("Start Chromium session"):

                    ssh_cmd = SSHClientIGEL(
                        host=dev["device_ip"],
                        port=22,
                        username="root"
                    )

                    assert ssh_cmd.reconnect_with_retry(12, 15)

                    time.sleep(3)

                    ssh_cmd.client.exec_command(
                        "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
                    )

                    log.info("Chromium launched")
                    time.sleep(3)

                with allure.step("Validate Chromium session logs"):

                    start_time = time.time()
                    tracking_found = False

                    while time.time() - start_time < 40:

                        if shell.recv_ready():
                            output = shell.recv(4096).decode()

                            if "tracking" in output.lower() and "chromium" in output.lower():
                                tracking_found = True
                                break

                        time.sleep(0.5)

                    assert tracking_found, "Tracking log not found"

                # ==================================================
                # STEP E → WMCTRL VALIDATION
                # ==================================================
                with allure.step("Validate Chromium window"):

                    _, output, _ = ssh_cmd.run_command(
                        "su user -c 'DISPLAY=:0 wmctrl -lx'"
                    )

                    log.info(f"wmctrl output:\n{output}")

                    assert "chromium" in output.lower(), \
                        "Chromium window not detected"

                # ==================================================
                # STEP F → KILL CHROMIUM (FRESH SESSION)
                # ==================================================
                with allure.step("Kill Chromium (fresh session)"):

                    ssh_kill = SSHClientIGEL(
                        host=dev["device_ip"],
                        port=22,
                        username="root"
                    )

                    assert ssh_kill.reconnect_with_retry(12, 10), \
                        "SSH kill session failed"

                    ssh_kill.run_command("pkill -9 -f chromium")

                    log.info("Chromium terminated from SSH session")

                    ssh_kill.close()

            # ==================================================
            # VALIDATE SESSION DONE
            # ==================================================
            with allure.step("Validate session done log"):

                done_found = False
                start_time = time.time()

                while time.time() - start_time < 40:

                    if shell.recv_ready():
                        output = shell.recv(4096).decode()

                        print("\n--- LOG ---\n", output)

                        if "Session done: Chromium" in output:
                            done_found = True
                            break

                    time.sleep(10)

                assert done_found, "Session done log not found"

            # ==================================================
            # STEP H → VALIDATE desktop SCREEN (OCR)
            # ==================================================
            with allure.step("Validate desktop screen via OCR (strict)"):

                # ==================================================
                # OPEN VNC
                # ==================================================
                vnc_proc = open_vnc(dev["device_ip"])
                log.info("VNC opened for OCR validation")

                time.sleep(10)  # allow screen to fully load

                keywords = ["Chromium", "Horizon"]
                found_keywords = set()

                # ==================================================
                # VALIDATE ALL KEYWORDS
                # ==================================================
                for attempt in range(5):

                    log.info(f"[OCR] Attempt {attempt + 1}")

                    for keyword in keywords:

                        # skip already found keywords
                        if keyword in found_keywords:
                            continue

                        if screen_contains_text(keyword):
                            log.info(f"[OCR] Found keyword: {keyword}")
                            found_keywords.add(keyword)

                    # check if all found
                    if len(found_keywords) == len(keywords):
                        log.info("[OCR] All keywords detected")
                        break

                    time.sleep(3)

                # ==================================================
                # ASSERT ALL KEYWORDS FOUND
                # ==================================================
                missing = set(keywords) - found_keywords

                assert not missing, \
                    f"Missing keywords on screen: {missing}"

                # ==================================================
                # SCREENSHOT (ONLY AFTER SUCCESS)
                # ==================================================
                screenshot = capture_vnc_screenshot(dev["device_ip"])

                allure.attach.file(
                    screenshot,
                    name="desktop_screen_ocr",
                    attachment_type=allure.attachment_type.PNG
                )

                log.info("Desktop screen validated via OCR")
    finally:

        log.info("STEP 6 cleanup")

        try:
            if ssh_root:
                ssh_root.close()
        except:
            pass

        try:
            if ssh_user:
                ssh_user.close()
        except:
            pass

        try:
            if vnc_proc:
                vnc_proc.terminate()
        except:
            pass


def step_7_set_user_defined_command(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]

    log.info("STEP 7 started: User-defined post-session command")

    try:
        # ==================================================
        # GET PROFILE ID
        # ==================================================
        with allure.step("Resolve profile ID"):

            profile_id = get_profile_id(ctx)

            log.info(f"[STEP7] Profile ID: {profile_id}")

        # ==================================================
        # UPDATE PROFILE → USER DEFINED COMMAND
        # ==================================================
        with allure.step("Set user-defined post-session command"):

            command = (
                'notify-send-message '
                '"Congratulations Dude!" '
                '"Your app was successfully closed! Here is your Nobel Prize!"'
            )

            payload = json.dumps({
                "app.chromium.postsession.command": {
                    "uiType": "editable",
                    "value": command,
                    "type": 2
                },
                "app.horizon.postsession.command": {
                    "uiType": "editable",
                    "value": command,
                    "type": 2
                }
            })

            api.update_profile_configuration(
                profile_id=profile_id,
                data_payload=payload,
                send_now=True
            )

            log.info("[STEP7] User-defined command applied")

            # wait for config apply
            time.sleep(20)

        # ==================================================
        # REBOOT DEVICE
        # ==================================================
        with allure.step("Reboot device"):

            device_id = get_device_id(ctx)

            api.reboot_device(device_id)

            log.info("[STEP7] Reboot triggered")

            time.sleep(30)

        # ==================================================
        # SSH VALIDATION
        # ==================================================
        with allure.step("Validate SSH after reboot"):

            ssh = wait_for_ssh(dev)

            log.info("[STEP7] SSH reconnected successfully")

            ssh.close()

        log.info("STEP 7 completed successfully")

    except Exception:
        log.error("STEP 7 failed", exc_info=True)
        raise


def step_8_validate_user_defined_notification(ctx):
    dev = ctx["device_cfg"]

    log.info("STEP 8 started: User-defined notification validation")

    ssh_cmd = None
    ssh_log = None
    vnc_proc = None

    try:

        # ==================================================
        # STEP A → OPEN VNC + LOGIN
        # ==================================================
        with allure.step("Open VNC and login"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)

            vnc_proc = open_vnc(dev["device_ip"])
            time.sleep(10)

            log.info("VNC opened successfully")

        # ==================================================
        # SSH LOG SESSION
        # ==================================================
        with allure.step("Start journalctl monitoring"):

            shell = ssh_log.client.invoke_shell()
            time.sleep(1)

            # clear buffer
            while shell.recv_ready():
                shell.recv(4096)

            shell.send("journalctl -efu igel-pcomd -n 0\n")
            time.sleep(2)

        # ==================================================
        # SSH COMMAND SESSION
        # ==================================================
        with allure.step("Start Chromium session"):

            ssh_cmd = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_cmd.reconnect_with_retry(12, 15)

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
            )

            log.info("Chromium launched")

            time.sleep(3)

        # ==================================================
        # VALIDATE LOGS
        # ==================================================
        with allure.step("Validate Chromium session logs"):

            start_time = time.time()
            tracking_found = False
            active_found = False

            while time.time() - start_time < 20:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    print("\n--- LIVE LOG ---\n", output)

                    if "Start tracking process" in output and "chromium" in output.lower():
                        tracking_found = True

                    if tracking_found and active_found:
                        break

                time.sleep(0.5)

            assert tracking_found, "Tracking log not found"

        # ==================================================
        # STEP E → WMCTRL VALIDATION
        # ==================================================
        with allure.step("Validate Chromium window"):

            _, output, _ = ssh_cmd.run_command(
                "su user -c 'DISPLAY=:0 wmctrl -lx'"
            )

            log.info(f"wmctrl output:\n{output}")

            assert "chromium" in output.lower(), \
                "Chromium window not detected"

        # ==================================================
        # STEP F → KILL CHROMIUM (FRESH SESSION)
        # ==================================================
        with allure.step("Kill Chromium (fresh session)"):

            ssh_kill = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill.reconnect_with_retry(12, 10), \
                "SSH kill session failed"

            ssh_kill.run_command("pkill -9 -f chromium")

            log.info("Chromium terminated from SSH session")

            ssh_kill.close()

        # ==================================================
        # VALIDATE SESSION DONE
        # ==================================================
        with allure.step("Validate session done log"):

            done_found = False
            start_time = time.time()

            while time.time() - start_time < 40:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    print("\n--- LOG ---\n", output)

                    if "Session done: Chromium" in output:
                        done_found = True
                        break

                time.sleep(10)

            assert done_found, "Session done log not found"

        # ==================================================
        # STEP H → VALIDATE desktop SCREEN (OCR)
        # ==================================================
        with allure.step("Validate desktop screen via OCR (strict)"):

            keywords = [
                "Congratulations Dude ! Your app was successfully closed! Nobel Prize"
            ]

            found_keywords = set()

            for attempt in range(5):

                log.info(f"[OCR] Attempt {attempt + 1}")

                for keyword in keywords:

                    if keyword in found_keywords:
                        continue

                    if screen_contains_text(keyword):
                        log.info(
                            "Found message after application closed: "
                            "Congratulations Dude! Your app was successfully closed! "
                            "Here is your Nobel Prize!"
                        )
                        found_keywords.add(keyword)

                if len(found_keywords) == len(keywords):
                    log.info("[OCR] All keywords detected")
                    break

                time.sleep(3)

            missing = set(keywords) - found_keywords

            assert not missing, \
                f"Missing keywords on screen: {missing}"

            screenshot = capture_vnc_screenshot(dev["device_ip"])

            allure.attach.file(
                screenshot,
                name="desktop_screen_ocr",
                attachment_type=allure.attachment_type.PNG
            )

            log.info("Desktop screen validated via OCR")

    except Exception:
        log.error("STEP 8 failed", exc_info=True)
        raise

    finally:

        log.info("STEP 8 cleanup")

        try:
            if ssh_cmd:
                ssh_cmd.close()
        except:
            pass

        try:
            if ssh_log:
                ssh_log.close()
        except:
            pass

        try:
            if vnc_proc:
                vnc_proc.terminate()
        except:
            pass


def step_9_validate_multi_app_notification(ctx):
    dev = ctx["device_cfg"]

    log.info("STEP 9 started: Multi-app notification validation")

    ssh_cmd = None
    ssh_log = None
    vnc_proc = None

    try:

        # ==================================================
        # STEP A → OPEN VNC
        # ==================================================
        with allure.step("Open VNC"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)

            vnc_proc = open_vnc(dev["device_ip"])
            time.sleep(10)

            log.info("VNC opened successfully")

        # ==================================================
        # SSH LOG SESSION
        # ==================================================
        with allure.step("Start journalctl monitoring"):

            shell = ssh_log.client.invoke_shell()
            time.sleep(1)

            while shell.recv_ready():
                shell.recv(4096)

            shell.send("journalctl -efu igel-pcomd -n 0\n")
            time.sleep(2)

        # ==================================================
        # SSH COMMAND SESSION → START BOTH APPS
        # ==================================================
        with allure.step("Start Chromium and Horizon session"):

            ssh_cmd = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_cmd.reconnect_with_retry(12, 15)

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
            )

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap vdm_client0 horizon &'"
            )

            log.info("Chromium and Horizon launched")

            time.sleep(5)

            # ==================================================
            # STEP D → VALIDATE LOGS
            # ==================================================
            with allure.step("Validate Chromium session logs"):

                start_time = time.time()
                tracking_found = False
                active_found = False

                while time.time() - start_time < 20:

                    if shell.recv_ready():
                        output = shell.recv(4096).decode()

                        print("\n--- LIVE LOG ---\n", output)

                        if "Start tracking process" in output and "chromium" in output.lower():
                            tracking_found = True

                        if tracking_found and active_found:
                            break

                    time.sleep(0.5)

                assert tracking_found, "Tracking log not found"

        # ==================================================
        # STEP E → KILL HORIZON (NO MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill Horizon → No notification expected"):

            ssh_kill = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill.reconnect_with_retry(12, 10)

            ssh_kill.run_command("pkill -9 -f horizon")

            log.info("Horizon terminated")

            ssh_kill.close()

            time.sleep(5)

            # OCR → ensure NO message
            message_found = False

            for attempt in range(2):

                if screen_contains_text(
                        "Congratulations Dude! Your app was successfully closed! Here is your Nobel Prize"):
                    message_found = False
                    break

                time.sleep(2)

            assert not message_found, \
                "Notification appeared after Horizon kill (should NOT)"

            log.info("No notification after Horizon kill (expected)")

        # ==================================================
        # STEP F → KILL CHROMIUM (MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill Chromium → Notification expected"):

            ssh_kill2 = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill2.reconnect_with_retry(12, 10)

            ssh_kill2.run_command("pkill -9 -f chromium")

            log.info("Chromium terminated")

            ssh_kill2.close()

        # ==================================================
        # VALIDATE SESSION DONE LOG
        # ==================================================
        with allure.step("Validate session done log"):

            done_found = False
            start_time = time.time()

            while time.time() - start_time < 40:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    print("\n--- LOG ---\n", output)

                    if "Session done: Chromium" in output:
                        done_found = True
                        break

                time.sleep(5)

            assert done_found, "Session done log not found"

        # ==================================================
        # STEP H → VALIDATE NOTIFICATION (OCR)
        # ==================================================
        with allure.step("Validate notification via OCR"):

            keywords = [
                "Congratulations Dude! Your app was successfully closed! Here is your Nobel Prize"
            ]

            found_keywords = set()

            for attempt in range(5):

                log.info(f"[OCR] Attempt {attempt + 1}")

                for keyword in keywords:

                    if keyword in found_keywords:
                        continue

                    if screen_contains_text(keyword):
                        log.info(
                            "Found message after application closed: "
                            "Congratulations Dude! Your app was successfully closed! "
                            "Here is your Nobel Prize!"
                        )
                        found_keywords.add(keyword)

                if len(found_keywords) == len(keywords):
                    log.info("[OCR] All keywords detected")
                    break

                time.sleep(3)

            missing = set(keywords) - found_keywords

            assert not missing, \
                f"Notification not detected after Chromium kill: {missing}"

            screenshot = capture_vnc_screenshot(dev["device_ip"])

            allure.attach.file(
                screenshot,
                name="step9_notification",
                attachment_type=allure.attachment_type.PNG
            )

            log.info("Notification validated successfully")

    except Exception:
        log.error("STEP 9 failed", exc_info=True)
        raise

    finally:

        log.info("STEP 9 cleanup")

        try:
            if ssh_cmd:
                ssh_cmd.close()
        except:
            pass

        try:
            if ssh_log:
                ssh_log.close()
        except:
            pass

        try:
            if vnc_proc:
                vnc_proc.terminate()
        except:
            pass


def step_10_set_base_system_postsession(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]

    log.info("STEP 10 started: Base system post-session configuration")

    try:
        # ==================================================
        # GET PROFILE ID
        # ==================================================
        with allure.step("Resolve profile ID"):

            profile_id = get_profile_id(ctx)

            log.info(f"[STEP10] Profile ID: {profile_id}")

        # ==================================================
        # UPDATE PROFILE → BASE SYSTEM POST-SESSION
        # ==================================================
        with allure.step("Set base system post-session command"):

            command = (
                'notify-send-message '
                '"Step10-13 Testing !" '
                '"Your app was successfully closed! Here is your Nobel Prize!"'
            )

            payload = json.dumps({

                # Disable app-level post session
                "app.chromium.postsession.enabled": {
                    "uiType": "bool",
                    "value": False,
                    "type": 2,
                    "deleteValue": True
                },
                "app.horizon.postsession.enabled": {
                    "uiType": "bool",
                    "value": False,
                    "type": 2,
                    "deleteValue": True
                },

                # Enable base system post session
                "userinterface.postsession.enabled": {
                    "uiType": "bool",
                    "value": True,
                    "type": 2
                },
                "userinterface.postsession.command": {
                    "uiType": "editable",
                    "value": command,
                    "type": 2
                },

                # Process tracking (VERY IMPORTANT)
                "userinterface.postsession.process": {
                    "instancesToAdd": {
                        "chromium_process": {
                            "name": {
                                "uiType": "string",
                                "value": "chromium",
                                "type": 2
                            },
                            "validrcs": {
                                "uiType": "string",
                                "value": "0",
                                "type": 2
                            },
                            "ignoredargs": {
                                "uiType": "string",
                                "value": "--help,--version",
                                "type": 2
                            }
                        },
                        "horizon_process": {
                            "name": {
                                "uiType": "string",
                                "value": "horizon-client",
                                "type": 2
                            },
                            "validrcs": {
                                "uiType": "string",
                                "value": "0",
                                "type": 2
                            },
                            "ignoredargs": {
                                "uiType": "string",
                                "value": "--help,--version",
                                "type": 2
                            }
                        }
                    },
                    "instancesToRemove": [],
                    "instances": {},
                    "type": 1
                }
            })

            api.update_profile_configuration(
                profile_id=profile_id,
                data_payload=payload,
                send_now=True
            )

            log.info("[STEP10] Base system post-session configured")

            # wait for apply
            time.sleep(20)

        # ==================================================
        # REBOOT DEVICE
        # ==================================================
        with allure.step("Reboot device"):

            device_id = get_device_id(ctx)

            api.reboot_device(device_id)

            log.info("[STEP10] Reboot triggered")

            time.sleep(ctx["CFG"]["timeouts"]["reboot_wait"])

        # ==================================================
        # SSH VALIDATION
        # ==================================================
        with allure.step("Validate SSH after reboot"):

            ssh = wait_for_ssh(dev)

            log.info("[STEP10] SSH reconnected successfully")
            time.sleep(20)
            ssh.close()

        log.info("STEP 10 completed successfully")

    except Exception:
        log.error("STEP 10 failed", exc_info=True)
        raise


def step_11_validate_multi_app_notification_base_system(ctx):
    dev = ctx["device_cfg"]

    log.info("STEP 11 started: Multi-app notification validation based on base system config")

    ssh_cmd = None
    ssh_log = None
    vnc_proc = None

    try:

        # ==================================================
        # STEP A → OPEN VNC
        # ==================================================
        with allure.step("Open VNC"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)

            vnc_proc = open_vnc(dev["device_ip"])
            time.sleep(10)

            log.info("VNC opened successfully")

        # ==================================================
        # SSH LOG SESSION
        # ==================================================
        with allure.step("Start journalctl monitoring"):

            shell = ssh_log.client.invoke_shell()
            time.sleep(1)

            while shell.recv_ready():
                shell.recv(4096)

            shell.send("journalctl -efu igel-pcomd -n 0\n")
            time.sleep(2)

        # ==================================================
        # SSH COMMAND SESSION → START BOTH APPS
        # ==================================================
        with allure.step("Start Chromium and Horizon session"):

            ssh_cmd = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_cmd.reconnect_with_retry(12, 15)

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
            )

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap vdm_client0 horizon &'"
            )

            log.info("Chromium and Horizon launched")

            time.sleep(5)

            # ==================================================
            # STEP D → VALIDATE LOGS
            # ==================================================
            with allure.step("Validate applications session logs"):

                start_time = time.time()
                tracking_found = False
                active_found = False

                while time.time() - start_time < 20:

                    if shell.recv_ready():
                        output = shell.recv(4096).decode()

                        print("\n--- LIVE LOG ---\n", output)

                        if "Start tracking process" in output and "chromium" in output.lower():
                            tracking_found = True

                        if "Start tracking process" in output and "horizon-client" in output.lower():
                            tracking_found = True

                        if tracking_found and active_found:
                            break

                    time.sleep(0.5)

                assert tracking_found, "Tracking log not found"

        # ==================================================
        # STEP E → KILL chromium (NO MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill Chromium → No notification expected"):

            ssh_kill = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill.reconnect_with_retry(12, 10)

            ssh_kill.run_command("pkill -9 -f chromium")

            log.info("first application terminated")

            ssh_kill.close()

            time.sleep(5)

            # OCR → ensure NO message
            message_found = False

            for attempt in range(2):

                if screen_contains_text(
                        "Step10-13 Testing! Your app was successfully closed! Here is your Nobel Prize"):
                    message_found = False
                    break

                time.sleep(2)

            assert not message_found, \
                "Notification appeared after first application kill (should NOT)"

            log.info("No notification after first application kill (expected)")

        # ==================================================
        # STEP F → KILL horizon (MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill horizon → Notification expected"):

            ssh_kill2 = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill2.reconnect_with_retry(12, 10)

            ssh_kill2.run_command("pkill -9 -f horizon")

            log.info("Last application terminated")

            ssh_kill2.close()

        # ==================================================
        # VALIDATE SESSION DONE LOG
        # ==================================================
        with allure.step("Validate session done log"):

            done_found = False
            start_time = time.time()

            while time.time() - start_time < 40:

                if shell.recv_ready():
                    output = shell.recv(4096).decode()

                    print("\n--- LOG ---\n", output)

                    if "Session done: base_system" in output:
                        done_found = True
                        break

                time.sleep(5)

            assert done_found, "Session done log not found"

        # ==================================================
        # STEP H → VALIDATE NOTIFICATION (OCR)
        # ==================================================
        with allure.step("Validate notification via OCR"):

            keywords = [
                "Step10-13 Testing! Your app was successfully closed! Here is your Nobel Prize"
            ]

            found_keywords = set()

            for attempt in range(5):

                log.info(f"[OCR] Attempt {attempt + 1}")

                for keyword in keywords:

                    if keyword in found_keywords:
                        continue

                    if screen_contains_text(keyword):
                        log.info(
                            "Found message after application closed: "
                            "Step10-13 Testing! Your app was successfully closed! "
                            "Here is your Nobel Prize!"
                        )
                        found_keywords.add(keyword)

                if len(found_keywords) == len(keywords):
                    log.info("[OCR] All keywords detected")
                    break

                time.sleep(3)

            missing = set(keywords) - found_keywords

            assert not missing, \
                f"Notification not detected after horizon kill: {missing}"

            screenshot = capture_vnc_screenshot(dev["device_ip"])

            allure.attach.file(
                screenshot,
                name="step11_notification",
                attachment_type=allure.attachment_type.PNG
            )

            log.info("Notification validated successfully")

    except Exception:
        log.error("STEP 11 failed", exc_info=True)
        raise

    finally:

        log.info("STEP 11 cleanup")

        try:
            if ssh_cmd:
                ssh_cmd.close()
        except:
            pass

        try:
            if ssh_log:
                ssh_log.close()
        except:
            pass

        try:
            if vnc_proc:
                vnc_proc.terminate()
        except:
            pass


def step_12_enable_force_postsession(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]
    profile_cfg = ctx["profile_cfg"]

    log.info("STEP 12 started: Enable base system post-session priority")

    try:
        # ==================================================
        # GET PROFILE ID
        # ==================================================
        with allure.step("Resolve profile ID"):

            profile_id = get_profile_id(ctx)
            log.info(f"[STEP12] Profile ID: {profile_id}")

        # ==================================================
        # UPDATE PROFILE → ENABLE FORCE OPTION
        # ==================================================
        with allure.step("Enable 'force post-session' option"):

            payload = json.dumps({
                "userinterface.postsession.force": {
                    "uiType": "bool",
                    "value": True,
                    "type": 2
                }
            })

            api.update_profile_configuration(
                profile_id=profile_id,
                data_payload=payload,
                send_now=True
            )

            log.info("[STEP12] Force post-session enabled")

            # wait for config apply
            time.sleep(20)

        # ==================================================
        # REBOOT DEVICE
        # ==================================================
        with allure.step("Reboot device"):

            device_id = get_device_id(ctx)

            api.reboot_device(device_id)

            log.info("[STEP12] Reboot triggered")

            time.sleep(ctx["CFG"]["timeouts"]["reboot_wait"])

        # ==================================================
        # SSH VALIDATION
        # ==================================================
        with allure.step("Validate SSH after reboot"):

            ssh = wait_for_ssh(dev)

            log.info("[STEP12] SSH reconnected successfully")
            time.sleep(20)
            ssh.close()

        log.info("STEP 12 completed successfully")

    except Exception:
        log.error("STEP 12 failed", exc_info=True)
        raise


def step_13_validate_force_postsession_behavior(ctx):
    dev = ctx["device_cfg"]

    log.info("STEP 13 started: Force post-session priority validation")

    ssh_cmd = None
    ssh_log = None
    vnc_proc = None

    try:

        # ==================================================
        # STEP A → OPEN VNC
        # ==================================================
        with allure.step("Open VNC"):

            ssh_log = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_log.reconnect_with_retry(12, 15)

            vnc_proc = open_vnc(dev["device_ip"])
            time.sleep(10)

            log.info("VNC opened successfully")

        # ==================================================
        # SSH COMMAND SESSION → START BOTH APPS
        # ==================================================
        with allure.step("Start All applications session"):

            ssh_cmd = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_cmd.reconnect_with_retry(12, 15)

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap chromium0 chromium'"
            )

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap vdm_client0 horizon &'"
            )

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap firefox0 firefox &'"
            )

            ssh_cmd.client.exec_command(
                "su user -c 'DISPLAY=:0 appwrap edge0 edge &'"
            )

            log.info("All applications launched")

            time.sleep(8)

        # ==================================================
        # STEP E → KILL chromium (NO MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill firefox FIRST (should NOT trigger command)"):

            ssh_kill = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill.reconnect_with_retry(12, 10)

            ssh_kill.run_command("pkill -9 -f firefox")

            log.info("KILL NON-PRIORITY application terminated")

            ssh_kill.close()

            time.sleep(8)

            # OCR → ensure NO message
            message_found = False

            for attempt in range(2):

                if screen_contains_text(
                        "Step10-13 Testing! Your app was successfully closed! Here is your Nobel Prize"):
                    message_found = False
                    break

                time.sleep(2)

            assert not message_found, \
                "Notification appeared after non-priority application kill (should NOT)"

            screenshot = capture_vnc_screenshot(dev["device_ip"])

            allure.attach.file(
                screenshot,
                name="step13_no_notification",
                attachment_type=allure.attachment_type.PNG
            )

            log.info("No notification after non-priority application kill (expected)")

        # ==================================================
        # STEP F → KILL horizon (MESSAGE EXPECTED)
        # ==================================================
        with allure.step("Kill priority app → Notification expected"):

            ssh_kill2 = SSHClientIGEL(
                host=dev["device_ip"],
                port=22,
                username="root"
            )

            assert ssh_kill2.reconnect_with_retry(12, 10)

            ssh_kill2.run_command("pkill -9 -f horizon")

            log.info("priority application terminated")

            ssh_kill2.close()

        # ==================================================
        # VALIDATE NOTIFICATION (OCR)
        # ==================================================
        with allure.step("Validate notification via OCR"):

            keywords = [
                "Step10-13 Testing! Your app was successfully closed! Here is your Nobel Prize"
            ]

            found_keywords = set()

            for attempt in range(5):

                log.info(f"[OCR] Attempt {attempt + 1}")

                for keyword in keywords:

                    if keyword in found_keywords:
                        continue

                    if screen_contains_text(keyword):
                        log.info(
                            "Found message after priority application closed: "
                            "Step10-13 Testing! Your app was successfully closed! "
                            "Here is your Nobel Prize!"
                        )
                        found_keywords.add(keyword)

                if len(found_keywords) == len(keywords):
                    log.info("[OCR] All keywords detected")
                    break

                time.sleep(8)

            missing = set(keywords) - found_keywords

            assert not missing, \
                f"Notification not detected after priority app kill: {missing}"

            screenshot = capture_vnc_screenshot(dev["device_ip"])

            allure.attach.file(
                screenshot,
                name="step13_notification",
                attachment_type=allure.attachment_type.PNG
            )

            log.info("Priority application notification validated successfully")

    except Exception:
        log.error("STEP 13 failed", exc_info=True)
        raise

    finally:

        log.info("STEP 13 cleanup")

        try:
            if ssh_cmd:
                ssh_cmd.close()
        except:
            pass

        try:
            if ssh_log:
                ssh_log.close()
        except:
            pass

        try:
            if vnc_proc:
                vnc_proc.terminate()
        except:
            pass

# ==========================================================
# CLEANUP → UNASSIGN PROFILE + REBOOT + VALIDATE (FINAL)
# ==========================================================
def step_cleanup_unassign_profile(ctx):
    api = ctx["api"]
    dev = ctx["device_cfg"]

    log.info("CLEANUP started: Unassign profile")

    MAX_RETRIES = 3
    SETTLE_TIME = 40

    try:
        # --------------------------------------------------
        # GET IDS
        # --------------------------------------------------
        with allure.step("Resolve device and profile IDs"):

            device_id = get_device_id(ctx)
            profile_id = get_profile_id(ctx)

            log.info(f"[CLEANUP] Device ID: {device_id}")
            log.info(f"[CLEANUP] Profile ID: {profile_id}")

        # --------------------------------------------------
        # UNASSIGN LOOP (USING YOUR API)
        # --------------------------------------------------
        for attempt in range(1, MAX_RETRIES + 1):

            log.info(
                f"[CLEANUP] Profile unassign attempt {attempt}/{MAX_RETRIES}"
            )

            with allure.step(f"Unassign profile (attempt {attempt})"):

                try:
                    status, text = api.unassign_object(
                        device_id=device_id,
                        object_id=profile_id,
                        object_type="PROFILE",
                        unassign=True
                    )

                    log.info(f"[CLEANUP] API response: {status} | {text}")

                    # Optional: basic success check
                    if status not in (200, 204):
                        log.warning(f"[CLEANUP] Unexpected status: {status}")

                except Exception as e:
                    log.warning(f"[CLEANUP] Unassign API error: {e}")

            # --------------------------------------------------
            # WAIT FOR BACKEND SETTLE
            # --------------------------------------------------
            log.info(f"[CLEANUP] Waiting {SETTLE_TIME}s for backend settle")
            time.sleep(SETTLE_TIME)

            # --------------------------------------------------
            # VALIDATE UNASSIGN
            # --------------------------------------------------
            with allure.step("Validate profile is unassigned"):

                try:
                    resp = api._request(
                        "get",
                        f"/umsapi/v3/devices/{device_id}/profiles"
                    )

                    data = resp.json()
                    assigned_profiles = data.get("items") if isinstance(data, dict) else data

                    still_assigned = any(
                        int(p.get("id")) == int(profile_id)
                        for p in assigned_profiles or []
                    )

                    if not still_assigned:
                        log.info("[CLEANUP] Profile successfully unassigned")
                        break

                    log.warning("[CLEANUP] Profile still assigned, retrying...")

                except Exception as e:
                    log.warning(f"[CLEANUP] Validation error: {e}")

            if attempt == MAX_RETRIES:
                raise AssertionError(
                    f"[CLEANUP] Failed to unassign profile after {MAX_RETRIES} attempts"
                )

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        with allure.step("Reboot device after unassign"):

            api.reboot_device(device_id)

            log.info("[CLEANUP] Reboot triggered after unassign")

            time.sleep(ctx["CFG"]["timeouts"]["reboot_wait"])

        # --------------------------------------------------
        # VALIDATE SSH
        # --------------------------------------------------
        with allure.step("Validate SSH after reboot"):

            ssh = wait_for_ssh(dev)

            log.info("[CLEANUP] SSH reachable after cleanup reboot")
            ssh.close()

        log.info("CLEANUP completed successfully")

    except Exception:
        log.error("CLEANUP failed", exc_info=True)
        raise

# ==========================================================
# TEST EXECUTION
# ==========================================================
@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 0: Device Precheck")
def test_tc4438_step01(tc4438_context):
    step_0_device_precheck(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 1: Profile Post Session Command")
def test_tc4438_step02(tc4438_context):
    step_1_profile_post_session(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 2: Validate Post Session Log")
def test_tc4438_step03(tc4438_context):
    step_2_validate_post_session_log(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 3: Update Profile to shut down Command")
def test_tc4438_step04(tc4438_context):
    step_3_update_profile_shutdown(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 4: Validate Shutdown via Post Session Command")
def test_tc4438_step05(tc4438_context):
    step_4_validate_shutdown_flow(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 5: Update Profile to Logoff + Local Login")
def test_tc4438_step06(tc4438_context):
    step_5_update_profile_logoff(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 6: Logoff Validation")
def test_tc4438_step07(tc4438_context):
    step_6_validate_logoff_flow(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 7: User Defined Post Session Command")
def test_tc4438_step08(tc4438_context):
    step_7_set_user_defined_command(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 8: User Defined Notification Validation")
def test_tc4438_step09(tc4438_context):
    step_8_validate_user_defined_notification(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 9: Multi App Notification Validation")
def test_tc4438_step10(tc4438_context):
    step_9_validate_multi_app_notification(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 10: Base System Post Session Configuration")
def test_tc4438_step11(tc4438_context):
    step_10_set_base_system_postsession(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 11: Multi App Notification Validation after basesystem config")
def test_tc4438_step12(tc4438_context):
    step_11_validate_multi_app_notification_base_system(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 12: Enable Base System Post Session Priority")
def test_tc4438_step13(tc4438_context):
    step_12_enable_force_postsession(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 13: Validate Base System Priority Execution")
def test_tc4438_step14(tc4438_context):
    step_13_validate_force_postsession_behavior(tc4438_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-4438")
@allure.title("Step 14: Cleanup - Unassign Profile")
def test_tc4438_step15(tc4438_context):
    step_cleanup_unassign_profile(tc4438_context)