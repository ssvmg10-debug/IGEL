###########################################################
# Test Case ID : QCL-3119
# Title        : Install / Upgrade / Downgrade Applications
#                Including Base System
#
# Description :
# End-to-end validation of application lifecycle operations
# (install, upgrade, downgrade) including the IGEL base
# system. Operations are performed both locally on the
# device and via UMS.
#
# Prerequisites:
# - Fresh IGEL OS virtual machine
# - Device and UMS must be in the same network
#
# Test Scope :
# - Validate fresh IGEL OS device provisioning
# - Install / upgrade / downgrade applications locally
# - Install / upgrade / downgrade applications via UMS
# - Install / upgrade / downgrade base_system locally
# - Install / upgrade / downgrade base_system via UMS
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : 6th Feb-2026
# Version      : 1.2
############################################################


import logging
import time
import uuid
import allure
import pytest
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.ssh.ssh_client import SSHClientIGEL
from core.ssh.igel_pkg import verify_apps_installed, verify_os_version
from core.utils.setup_ini import read_setup, write_setup, add_qa_repo, add_browser_session
from core.utils.vnc_client import vnc_validate_desktop
from core.api.wums_api import UMSWUMSApi
from core.utils.logger import get_logger, step_log_context

log = get_logger(__name__)
logger = logging.getLogger(__name__)


# ==========================================================
# STEP HELPERS
# ==========================================================
def step_start(step):
    log.info(f"[STEP {step} START]")


def step_end(step):
    log.info(f"[STEP {step} END]")


# ==========================================================
# SHARED TEST CONTEXT (USED BY STEP 1 → STEP 20)
# ==========================================================
@pytest.fixture(scope="session")
def tc3119_context(config):

    CFG = config
    ums_cfg = CFG["ums"]
    dev_cfg = CFG["device"]

    log.info("[CTX] Initializing API client (PKCE)")

    api = UMSWUMSApi(
        base_url=ums_cfg["base_url"],
        username=ums_cfg["username"],
        password=ums_cfg["password"]
    )

    log.info("[CTX] Auth initialized successfully")

    return {
        "CFG": CFG,
        "api": api,
        "device_cfg": dev_cfg,
        "ums_cfg": ums_cfg,
        "device_id": None,
        "baseline_apps": None,
    }


# ==========================================================
# STEP 1–2 : DEVICE REGISTRATION + SSH ENABLEMENT
# ==========================================================
def step_1_2_device_registration(context):
    CFG = context["CFG"]
    api = context["api"]
    ums_cfg = context["ums_cfg"]
    dev_cfg = context["device_cfg"]

    step_start("1–2 Device Registration")

    # --------------------------------------------------
    # device reset check (intentional outside step logging)
    # --------------------------------------------------
    api.cleanup_device_if_exists(
        device_name=dev_cfg["name"]
    )

    with allure.step("STEP 1–2 Device Registration Flow"):

        try:
            # --------------------------------------------------
            # Resolve directory
            # --------------------------------------------------
            with allure.step("Resolve target directory"):
                with step_log_context("Resolve target directory"):
                    log.debug("Resolving target directory")
                    directory_id = api.get_directory_id(dev_cfg["target_folder"])
                    log.info(f"Target directory resolved: {directory_id}")

            # --------------------------------------------------
            # Scan devices
            # --------------------------------------------------
            with allure.step("Trigger device scan"):
                with step_log_context("Trigger device scan"):
                    log.debug("Triggering device scan")
                    api.scan_devices()
                    log.info("Device scan triggered")

                    time.sleep(CFG["timeouts"]["scan_wait"])

            # --------------------------------------------------
            # Register device
            # --------------------------------------------------
            with allure.step("Register device"):
                with step_log_context("Register device"):
                    log.debug("Registering device")
                    api.register_device(
                        directory_id=directory_id,
                        mac=dev_cfg["mac"],
                        ip=dev_cfg["ip"]
                    )

                    log.info("Device registration triggered")
                    time.sleep(10)

            # --------------------------------------------------
            # Resolve device ID
            # --------------------------------------------------
            with allure.step("Resolve registered device ID"):
                with step_log_context("Resolve device ID"):
                    device_id = api.get_device_id(dev_cfg["name"])
                    context["device_id"] = device_id

                    log.info(f"Device registered with ID: {device_id}")

            # --------------------------------------------------
            # Enable SSH / VNC with retry
            # --------------------------------------------------
            MAX_SSH_ENABLE_ATTEMPTS = 3
            SSH_RETRY_DELAY = 20
            ssh_enabled = False
            last_error = None

            for attempt in range(1, MAX_SSH_ENABLE_ATTEMPTS + 1):

                with allure.step(f"Enable SSH/VNC attempt {attempt}"):
                    with step_log_context(f"Enable SSH/VNC attempt {attempt}"):

                        log.info(
                            f"Enable SSH/VNC attempt "
                            f"{attempt}/{MAX_SSH_ENABLE_ATTEMPTS}"
                        )

                        try:
                            log.debug("Enabling SSH, VNC and Shadow")
                            api.enable_ssh_vnc(device_id)

                            log.debug("Rebooting device")
                            api.reboot_device(device_id)

                        except Exception as e:
                            last_error = str(e)
                            log.error(f"Enable SSH failed: {last_error}")

                            if "403" in last_error:
                                log.warning("403 detected, refreshing auth")
                                time.sleep(5)
                                continue

                            time.sleep(SSH_RETRY_DELAY)
                            continue

                        time.sleep(CFG["timeouts"]["reboot_wait"])

                        # ------------------------------------------
                        # SSH validation
                        # ------------------------------------------
                        with allure.step("Validate SSH connectivity"):
                            with step_log_context("Validate SSH connectivity"):
                                ssh = SSHClientIGEL(
                                    host=dev_cfg["ip"],
                                    port=22, username="root"
                                )

                                if ssh.reconnect_with_retry(attempts=12, delay_sec=15):
                                    ssh.close()
                                    log.info("SSH validated successfully")
                                    ssh_enabled = True
                                    break

                                log.warning("SSH not reachable after reboot")
                                ssh.close()
                                time.sleep(SSH_RETRY_DELAY)

            assert ssh_enabled, (
                f"SSH could not be enabled after "
                f"{MAX_SSH_ENABLE_ATTEMPTS} attempts. "
                f"Last error: {last_error}"
            )

        except Exception:
            log.error(
                "Fatal error during device registration",
                exc_info=True
            )
            raise

    step_end("1–2 Device Registration")


# ==========================================================
# STEP 3 : ADD QA REPOSITORY
# ==========================================================
def step_3_add_qa_repo(context):
    import uuid
    import time

    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("3 Add QA Repo")

    ssh = SSHClientIGEL(
        host=dev_cfg["ip"],
        port=22, username="root"
    )

    MAX_REPO_ATTEMPTS = 3
    VERIFY_TIMEOUT = 180
    VERIFY_INTERVAL = 5

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                log.info("[STEP 3] Connecting to device")
                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "SSH did not come up after reboot"
                log.info("[STEP 3] SSH connected successfully")

        # --------------------------------------------------
        # READ CURRENT SETUP
        # --------------------------------------------------
        with allure.step("Read setup.ini from device"):
            with step_log_context("Read setup.ini from device"):
                setup = read_setup(ssh)

                allure.attach(
                    setup,
                    "setup.ini BEFORE",
                    allure.attachment_type.TEXT
                )

        qa_url = CFG["qa_repo"]["url"]

        # --------------------------------------------------
        # IF REPO ALREADY EXISTS → SKIP
        # --------------------------------------------------
        if qa_url in setup:
            log.info("[STEP 3] QA repo already present — skipping add")

        else:
            log.info("[STEP 3] QA repo missing — starting add + reboot retry loop")

            repo_added = False

            # ==================================================
            # RETRY LOOP
            # ==================================================
            for attempt in range(1, MAX_REPO_ATTEMPTS + 1):

                log.info(f"[STEP 3] Repo add attempt {attempt}/{MAX_REPO_ATTEMPTS}")

                qa_uuid = uuid.uuid4().hex
                context["qa_repo_uuid"] = qa_uuid

                # --------------------------------------------------
                # ADD REPO
                # --------------------------------------------------
                with allure.step(f"Add QA repo attempt {attempt}"):
                    with step_log_context(f"Add QA repo attempt {attempt}"):
                        current_setup = read_setup(ssh)
                        new_setup = add_qa_repo(current_setup, qa_uuid, qa_url)
                        write_setup(ssh, new_setup)

                        written = read_setup(ssh)

                        allure.attach(
                            written,
                            f"setup.ini after write (attempt {attempt})",
                            allure.attachment_type.TEXT
                        )

                # --------------------------------------------------
                # REBOOT DEVICE
                # --------------------------------------------------
                with allure.step("Reboot device to apply repo"):
                    with step_log_context("Reboot device to apply repo"):
                        log.info("[STEP 3] Rebooting device")
                        assert ssh.run_command("reboot"), "Device reboot failed"
                        log.info("[STEP 3] Device rebooted")

                # --------------------------------------------------
                # VERIFY AFTER REBOOT (POLL)
                # --------------------------------------------------
                with allure.step("Verify QA repo after reboot"):
                    with step_log_context("Verify QA repo after reboot"):

                        log.info("[STEP 3] Waiting for repo persistence")

                        start = time.time()
                        repo_found = False

                        while time.time() - start < VERIFY_TIMEOUT:
                            setup_after = read_setup(ssh)

                            if qa_url in setup_after:
                                repo_found = True
                                break

                            log.info("[STEP 3] Repo not ready yet, waiting...")
                            time.sleep(VERIFY_INTERVAL)

                        allure.attach(
                            setup_after,
                            f"setup.ini after reboot (attempt {attempt})",
                            allure.attachment_type.TEXT
                        )

                        if repo_found:
                            log.info("[STEP 3] QA repo verified successfully")
                            repo_added = True
                            break
                        else:
                            log.warning(
                                f"[STEP 3] Repo missing after reboot (attempt {attempt})"
                            )

            # --------------------------------------------------
            # FAIL AFTER MAX RETRIES
            # --------------------------------------------------
            assert repo_added, (
                f"[STEP 3] QA repo not persisted after "
                f"{MAX_REPO_ATTEMPTS} attempts"
            )

        # --------------------------------------------------
        # UPDATE PACKAGE INDEX
        # --------------------------------------------------
        with allure.step("Run igelpkgctl update"):
            with step_log_context("Run igelpkgctl update"):
                log.info("[STEP 3] Running igelpkgctl update")
                time.sleep(20)
                ssh.run_command("igelpkgctl update")
                log.info("[STEP 3] Package index updated")

        log.info("[STEP 3] QA repo step completed successfully")

    except AssertionError as ae:
        log.error(f"[STEP 3] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 3] Unexpected error during QA repo step",
            exc_info=True
        )
        raise

    finally:
        ssh.close()
        log.debug("[STEP 3] SSH connection closed")

    step_end("3 Add QA Repo")


# ==========================================================
# STEP 4 : INSTALL APPS + SHADOW EULA + BROWSER SESSIONS
# ==========================================================
def step_4_install_apps(context):
    import uuid

    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("4 Install Apps")

    all_apps = CFG["apps"]["browser"] + CFG["apps"]["non_browser"]
    app_names = [a["name"] for a in all_apps]

    ssh = None
    shadow_proc = None

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )
                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "SSH did not come up after reboot"
                log.info("[STEP 4] SSH connected")
                time.sleep(30)

        # --------------------------------------------------
        # INSTALL APPLICATIONS
        # --------------------------------------------------
        with allure.step("Install applications locally"):
            with step_log_context("Install applications locally"):
                for app in all_apps:
                    name = app["name"]
                    version = app["install_version"]

                    with allure.step(f"Install {name}"):
                        with step_log_context(f"Install {name}"):
                            log.info(f"[STEP 4] Installing {name}")
                            time.sleep(20)

                            ssh.run_command(
                                f"igelpkgctl install {name} -y",
                                timeout=1800
                            )

                            log.info(f"[STEP 4] Installed {name}")
                            time.sleep(10)


        # --------------------------------------------------
        # REBOOT AFTER INSTALL
        # --------------------------------------------------
        with allure.step("Reboot device after installation"):
            with step_log_context("Reboot device after installation"):
                ssh.run_command("reboot")
                ssh.close()

                time.sleep(CFG["timeouts"]["reboot_wait"])

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )
                assert ssh.reconnect_with_retry()
                log.info("[STEP 4] Device rebooted after install")

        # --------------------------------------------------
        # ADD BROWSER SESSIONS (UPDATED UUID LOGIC)
        # --------------------------------------------------
        with allure.step("Create browser sessions"):
            with step_log_context("Create browser sessions"):
                setup = read_setup(ssh)

                allure.attach(
                    setup,
                    "setup.ini BEFORE browser sessions",
                    allure.attachment_type.TEXT
                )

                # store generated UUIDs (optional but useful)
                context["browser_session_uuids"] = {}

                for app in CFG["apps"]["browser"]:
                    with allure.step(f"Add browser session: {app['name']}"):
                        with step_log_context(f"Add browser session: {app['name']}"):
                            #  generate new UUID per session
                            session_uuid = uuid.uuid4().hex
                            context["browser_session_uuids"][app["name"]] = session_uuid

                            log.info(
                                f"[STEP 4] Generated session UUID for "
                                f"{app['name']}: {session_uuid}"
                            )

                            setup = add_browser_session(
                                setup,
                                app["name"],
                                session_uuid
                            )

                write_setup(ssh, setup)

                setup_after = read_setup(ssh)
                allure.attach(
                    setup_after,
                    "setup.ini AFTER browser session write",
                    allure.attachment_type.TEXT
                )

        # --------------------------------------------------
        # REBOOT AFTER SESSION CREATION
        # --------------------------------------------------
        with allure.step("Reboot after session creation"):
            with step_log_context("Reboot after session creation"):
                ssh.run_command("reboot")
                ssh.close()

                time.sleep(CFG["timeouts"]["reboot_wait"])

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )
                assert ssh.reconnect_with_retry()
                log.info("[STEP 4] Device rebooted after creating sessions")

        # --------------------------------------------------
        # VNC VALIDATION
        # --------------------------------------------------
        with allure.step("Validate VNC desktop"):
            with step_log_context("Validate VNC desktop"):
                vnc_validate_desktop(dev_cfg["ip"], app_names)
                log.info("[STEP 4] VNC validation passed")

    except AssertionError as ae:
        log.error(f"[STEP 4] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 4] Unexpected error during app install / session creation",
            exc_info=True
        )
        raise

    finally:
        # if shadow_proc:
        #     shadow_proc.terminate()

        if ssh:
            ssh.close()

    step_end("4 Install Apps")


# ==========================================================
# STEP 5 : APPLICATION DOWNGRADE
# ==========================================================
def step_5_app_downgrade(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("5 App Downgrade")

    log.info("[STEP 5] Starting application downgrade")

    all_apps = CFG["apps"]["browser"] + CFG["apps"]["non_browser"]
    app_names = [a["name"] for a in all_apps]

    ssh = None

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 5] SSH did not come up before downgrade"

                log.info("[STEP 5] SSH connected")
                time.sleep(20)

        # --------------------------------------------------
        # DOWNGRADE APPLICATIONS
        # --------------------------------------------------
        with allure.step("Downgrade installed applications"):
            with step_log_context("Downgrade installed applications"):
                for app in all_apps:
                    name = app["name"]
                    version = app["downgrade_version"]

                    with allure.step(f"Downgrade {name}-{version}"):
                        with step_log_context(f"Downgrade {name}-{version}"):
                            log.info(f"[STEP 5] Downgrading {name}")

                            ssh.run_command(
                                f"printf 'y\\n' | igelpkgctl install {name}-{version} -y",
                                timeout=1800
                            )

                            log.info(f"[STEP 5] Downgrade completed for {name}")

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        with allure.step("Reboot device after downgrade"):
            with step_log_context("Reboot device after downgrade"):
                ssh.run_command("reboot")
                ssh.close()

                time.sleep(CFG["timeouts"]["reboot_wait"])

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.reconnect_with_retry(), \
                    "[STEP 5] SSH did not come up after app downgrade reboot"

                log.info("[STEP 5] Device rebooted successfully")

        # --------------------------------------------------
        # VERIFY APPLICATIONS
        # --------------------------------------------------
        with allure.step("Verify downgraded applications"):
            with step_log_context("Verify downgraded applications"):
                verify_apps_installed(ssh, app_names)
                log.info("[STEP 5] All applications verified after downgrade")

    except AssertionError as ae:
        log.error(f"[STEP 5] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 5] Unexpected error occurred during app downgrade",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("5 App Downgrade")


# ==========================================================
# STEP 6 : BASE SYSTEM DOWNGRADE
# ==========================================================
# ==========================================================
# STEP 6 : BASE SYSTEM DOWNGRADE (WITH RETRY)
# ==========================================================
def step_6_base_downgrade(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("6 Base System Downgrade")

    log.info("[STEP 6] Starting base system downgrade")

    ssh = None

    MAX_DOWNGRADE_ATTEMPTS = 3
    STAGING_WAIT = 25
    POST_REBOOT_SETTLE = 20

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 6] SSH not reachable before downgrade"

                log.info("[STEP 6] SSH connected")

        downgrade_version = CFG["base_system"]["downgrade_version"]
        expected_version = CFG["base_system"]["lower_version"]["expected"]

        log.debug(f"[STEP 6] Downgrade package: {downgrade_version}")
        log.debug(f"[STEP 6] Expected OS version: {expected_version}")

        # ==================================================
        # RETRY LOOP
        # ==================================================
        for attempt in range(1, MAX_DOWNGRADE_ATTEMPTS + 1):

            log.info(
                f"[STEP 6] Downgrade attempt "
                f"{attempt}/{MAX_DOWNGRADE_ATTEMPTS}"
            )

            # --------------------------------------------------
            # INSTALL DOWNGRADE
            # --------------------------------------------------
            log.info("[STEP 6] Installing base system downgrade")

            ssh.run_command(
                f"igelpkgctl install {downgrade_version} -y",
                timeout=1800,
            )

            log.info(
                f"[STEP 6] Waiting {STAGING_WAIT}s for downgrade staging"
            )
            time.sleep(STAGING_WAIT)

            # --------------------------------------------------
            # REBOOT
            # --------------------------------------------------
            log.info("[STEP 6] Rebooting device to apply downgrade")

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            # --------------------------------------------------
            # RECONNECT
            # --------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22,
                username="root"
            )

            assert ssh.reconnect_with_retry(
                attempts=12,
                delay_sec=15
            ), "[STEP 6] SSH did not come up after reboot"

            log.info("[STEP 6] Device reachable after reboot")

            log.info(
                f"[STEP 6] Waiting {POST_REBOOT_SETTLE}s for system settle"
            )
            time.sleep(POST_REBOOT_SETTLE)

            # --------------------------------------------------
            # VERIFY
            # --------------------------------------------------
            try:
                log.info("[STEP 6] Verifying OS version")

                verify_os_version(
                    ssh=ssh,
                    expected_version=expected_version,
                )

                log.info(
                    "[STEP 6] Base system downgrade verified successfully"
                )
                break

            except AssertionError as verify_error:
                log.warning(
                    f"[STEP 6] Version not applied yet: {verify_error}"
                )

                if attempt == MAX_DOWNGRADE_ATTEMPTS:
                    log.error(
                        "[STEP 6] Downgrade failed after max attempts"
                    )
                    raise

                log.info("[STEP 6] Retrying downgrade cycle...")

        # END RETRY LOOP

    except AssertionError as ae:
        log.error(f"[STEP 6] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 6] Unexpected error during base system downgrade",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("6 Base System Downgrade")

# ==========================================================
# STEP 7 : SYSTEM VALIDATION AFTER DOWNGRADE
# ==========================================================
def step_7_validate_after_downgrade(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("7 Validate After Downgrade")

    log.info("[STEP 7] Starting system validation after downgrade")

    ssh = None

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 7] SSH not reachable for validation"

                log.info("[STEP 7] SSH connected")

        # --------------------------------------------------
        # RESOLVE EXPECTED APPLICATIONS
        # --------------------------------------------------
        with allure.step("Resolve expected applications from configuration"):
            with step_log_context("Resolve expected applications from configuration"):
                all_apps = CFG["apps"]["browser"] + CFG["apps"]["non_browser"]
                app_names = [a["name"] for a in all_apps]

                log.debug(f"[STEP 7] Expected installed apps: {app_names}")

        # --------------------------------------------------
        # VERIFY INSTALLED APPLICATIONS
        # --------------------------------------------------
        with allure.step("Verify installed applications on device"):
            with step_log_context("Verify installed applications on device"):
                verify_apps_installed(ssh, app_names)
                log.info("[STEP 7] Application installation verification successful")

        # --------------------------------------------------
        # VALIDATE VNC DESKTOP
        # --------------------------------------------------
        with allure.step("Validate VNC desktop sessions"):
            with step_log_context("Validate VNC desktop sessions"):
                vnc_validate_desktop(dev_cfg["ip"], app_names)
                log.info("[STEP 7] VNC desktop validation passed")

    except AssertionError as ae:
        log.error(f"[STEP 7] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 7] Unexpected error during system validation",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("7 Validate After Downgrade")


# ==========================================================
# STEP 8 : BASE SYSTEM UPGRADE (WITH RETRY)
# ==========================================================
def step_8_base_upgrade(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("8 Base System Upgrade")

    log.info("[STEP 8] Starting base system upgrade")

    ssh = None

    MAX_UPGRADE_ATTEMPTS = 3
    STAGING_WAIT = 30  # wait after install before reboot
    POST_REBOOT_SETTLE = 20  # wait after reconnect before verify

    try:
        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 8] SSH not reachable before upgrade"

                log.info("[STEP 8] SSH connected")

        # --------------------------------------------------
        # RESOLVE CONFIG
        # --------------------------------------------------
        upgrade_version = CFG["base_system"]["upgrade_version"]
        expected_version = CFG["base_system"]["upper_version"]["expected"]

        log.debug(f"[STEP 8] Upgrade package: {upgrade_version}")
        log.debug(f"[STEP 8] Expected OS version: {expected_version}")

        # ==================================================
        # RETRY LOOP
        # ==================================================
        for attempt in range(1, MAX_UPGRADE_ATTEMPTS + 1):

            log.info(
                f"[STEP 8] Upgrade attempt "
                f"{attempt}/{MAX_UPGRADE_ATTEMPTS}"
            )

            # --------------------------------------------------
            # INSTALL UPGRADE
            # --------------------------------------------------
            log.info("[STEP 8] Installing base system upgrade")

            ssh.run_command(
                f"printf 'y\\n' | igelpkgctl install {upgrade_version} -y"
            )

            log.info(
                f"[STEP 8] Waiting {STAGING_WAIT}s for upgrade staging"
            )
            time.sleep(STAGING_WAIT)

            # --------------------------------------------------
            # REBOOT
            # --------------------------------------------------
            log.info("[STEP 8] Rebooting device to apply upgrade")

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            # --------------------------------------------------
            # RECONNECT
            # --------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22,
                username="root"
            )

            assert ssh.reconnect_with_retry(
                attempts=12,
                delay_sec=15
            ), "[STEP 8] SSH did not come up after reboot"

            log.info("[STEP 8] Device reachable after reboot")

            log.info(
                f"[STEP 8] Waiting {POST_REBOOT_SETTLE}s "
                f"for system settle"
            )
            time.sleep(POST_REBOOT_SETTLE)

            # --------------------------------------------------
            # VERIFY
            # --------------------------------------------------
            try:
                log.info("[STEP 8] Verifying OS version")
                verify_os_version(
                    ssh=ssh,
                    expected_version=expected_version
                )

                log.info(
                    "[STEP 8] Base system upgrade verified successfully"
                )
                break

            except AssertionError as verify_error:
                log.warning(
                    f"[STEP 8] Version not applied yet: {verify_error}"
                )

                if attempt == MAX_UPGRADE_ATTEMPTS:
                    log.error(
                        "[STEP 8] Upgrade failed after max attempts"
                    )
                    raise

                log.info(
                    "[STEP 8] Retrying upgrade cycle..."
                )

        # END RETRY LOOP

    except AssertionError as ae:
        log.error(f"[STEP 8] Verification failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 8] Unexpected error during base system upgrade",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("8 Base System Upgrade")


# ==========================================================
# STEP 9 : SYSTEM CHECK AFTER BASE SYSTEM UPGRADE
# ==========================================================
def step_9_validate_after_upgrade(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("9 Validate After Upgrade")

    log.info("[STEP 9] Validating applications after base system upgrade")

    ssh = None

    try:
        # --------------------------------------------------
        # BUILD EXPECTED APP LIST
        # --------------------------------------------------
        with allure.step("Build expected application list"):
            with step_log_context("Build expected application list"):
                all_apps = CFG["apps"]["browser"] + CFG["apps"]["non_browser"]
                app_names = [a["name"] for a in all_apps]

                log.debug(f"[STEP 9] Expected installed apps: {app_names}")

        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 9] SSH not reachable for validation"

                log.info("[STEP 9] SSH connected")

        # --------------------------------------------------
        # VERIFY INSTALLED APPLICATIONS
        # --------------------------------------------------
        with allure.step("Verify installed applications"):
            with step_log_context("Verify installed applications"):
                verify_apps_installed(ssh, app_names)
                log.info("[STEP 9] Application installation verification passed")

        # --------------------------------------------------
        # VALIDATE VNC DESKTOP
        # --------------------------------------------------
        with allure.step("Validate VNC desktop sessions"):
            with step_log_context("Validate VNC desktop sessions"):
                vnc_validate_desktop(dev_cfg["ip"], app_names)
                log.info("[STEP 9] VNC desktop validation passed")

    except AssertionError as ae:
        log.error(f"[STEP 9] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 9] Unexpected error during system validation",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("9 Validate After Upgrade")


# ==========================================================
# STEP 10 : DEPENDENCY NEGATIVE TEST
# ==========================================================
def step_10_dependency_negative(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("10 Dependency Negative Test")

    log.info("[STEP 10] Starting dependency negative test")

    ssh = None

    try:
        # --------------------------------------------------
        # RESOLVE DEPENDENCY TEST TARGET
        # --------------------------------------------------
        with allure.step("Resolve dependency test app"):
            with step_log_context("Resolve dependency test app"):
                dep_app = CFG["dependency_test"]["app"]
                dep_version = CFG["dependency_test"]["version"]

                log.debug(
                    f"[STEP 10] Attempting to install dependency app: "
                    f"{dep_app}-{dep_version}"
                )

        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 10] SSH not reachable"

                log.info("[STEP 10] SSH connected")

        # --------------------------------------------------
        # ATTEMPT INSTALL (EXPECTED FAILURE)
        # --------------------------------------------------
        with allure.step("Attempt dependency install (expected to fail)"):
            with step_log_context("Attempt dependency install (expected to fail)"):
                ssh.run_command(
                    f"igelpkgctl install {dep_app}-{dep_version}"
                )

                log.info("[STEP 10] Install attempt completed")

        # --------------------------------------------------
        # VERIFY NOT INSTALLED
        # --------------------------------------------------
        with allure.step("Verify dependency app is NOT installed"):
            with step_log_context("Verify dependency app is NOT installed"):
                _, output, _ = ssh.run_command("igelpkgctl list installed")

                allure.attach(
                    output,
                    "Installed apps after dependency test",
                    allure.attachment_type.TEXT
                )

                assert dep_app not in output, (
                    f"[STEP 10] Dependency app '{dep_app}' should NOT be installed"
                )

                log.info("[STEP 10] Dependency negative test passed")

    except AssertionError as ae:
        log.error(f"[STEP 10] Dependency validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 10] Unexpected error during dependency negative test",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("10 Dependency Negative Test")


# ==========================================================
# STEP 11 : UNINSTALL ALL APPS
# ==========================================================
def step_11_uninstall_all(context):
    CFG = context["CFG"]
    dev_cfg = context["device_cfg"]

    step_start("11 Uninstall All Apps")

    log.info("[STEP 11] Starting uninstall of all applications")

    ssh = None

    try:
        # --------------------------------------------------
        # RESOLVE APPS
        # --------------------------------------------------
        with allure.step("Resolve installed applications to uninstall"):
            with step_log_context("Resolve installed applications to uninstall"):
                all_apps = CFG["apps"]["browser"] + CFG["apps"]["non_browser"]
                app_names = [a["name"] for a in all_apps]

                log.debug(f"[STEP 11] Applications to uninstall: {app_names}")

        # --------------------------------------------------
        # CONNECT SSH
        # --------------------------------------------------
        with allure.step("Connect to device via SSH"):
            with step_log_context("Connect to device via SSH"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 11] SSH not reachable"

                log.info("[STEP 11] SSH connected")

        # --------------------------------------------------
        # UNINSTALL APPS
        # --------------------------------------------------
        with allure.step("Uninstall all applications"):
            with step_log_context("Uninstall all applications"):
                for app in all_apps:
                    log.info(f"[STEP 11] Uninstalling app: {app['name']}")
                    ssh.run_command(
                        f"printf 'y\\n' | igelpkgctl uninstall {app['name']}"
                    )

                log.info("[STEP 11] All uninstall commands executed")

        # --------------------------------------------------
        # REBOOT DEVICE
        # --------------------------------------------------
        with allure.step("Reboot device after uninstall"):
            with step_log_context("Reboot device after uninstall"):
                log.info("[STEP 11] Rebooting device after uninstall")
                ssh.run_command("reboot")
                ssh.close()
                ssh = None

                time.sleep(CFG["timeouts"]["reboot_wait"])

        # --------------------------------------------------
        # VERIFY DEVICE BACK ONLINE
        # --------------------------------------------------
        with allure.step("Verify SSH after uninstall reboot"):
            with step_log_context("Verify SSH after uninstall reboot"):
                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "[STEP 11] SSH did not come up after uninstall reboot"

                log.info("[STEP 11] Device reachable after uninstall reboot")

    except AssertionError as ae:
        log.error(f"[STEP 11] Uninstall verification failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 11] Unexpected error during uninstall process",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("11 Uninstall All Apps")


# ==========================================================
# STEP 12 : WUMS APP INSTALL (PROFILE SAFE)
# ==========================================================
def step_12_wums_app_install(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]

    step_start("12 WUMS App Install (Profile Safe)")

    MAX_RETRIES = 3
    RETRY_DELAY = 30

    for attempt in range(1, MAX_RETRIES + 1):
        ssh = None

        try:
            log.info(f"[STEP 12] FULL attempt {attempt}/{MAX_RETRIES}")

            # ------------------------------------------------------
            # RESOLVE
            # ------------------------------------------------------
            device_id = api.get_device_id(dev_cfg["name"])
            context["device_id"] = device_id

            app = CFG["app"]

            # ------------------------------------------------------
            # ASSIGN
            # ------------------------------------------------------
            try:
                api.assign_app(
                    device_id=device_id,
                    app_id=app["id"]
                )
                log.info("[STEP 12] WUMS assign accepted")

            except AssertionError as e:
                msg = str(e).lower()

                if "409" in msg or "already" in msg:
                    log.warning("[STEP 12] App already assigned, continuing")
                else:
                    raise

            # ------------------------------------------------------
            # WAIT
            # ------------------------------------------------------
            log.info("[STEP 12] Waiting for backend settle")
            time.sleep(45)

            # ------------------------------------------------------
            # SINGLE REBOOT (no retry loop here)
            # ------------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22,
                username="root"
            )

            assert ssh.connect(), "[STEP 12] SSH connect failed"

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            # ------------------------------------------------------
            # VERIFY
            # ------------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22,
                username="root"
            )

            assert ssh.reconnect_with_retry(
                attempts=12,
                delay_sec=15
            ), "[STEP 12] SSH reconnect failed"

            _, output, _ = ssh.run_command("igelpkgctl list installed")

            allure.attach(
                output,
                f"Installed Apps (Attempt {attempt})",
                allure.attachment_type.TEXT
            )

            assert app["name"].lower() in output.lower(), \
                f"[STEP 12] App '{app['name']}' not installed"

            #  SUCCESS
            log.info(f"[STEP 12] SUCCESS on attempt {attempt}")
            break

        except Exception as e:
            log.error(
                f"[STEP 12] Attempt {attempt} FAILED: {e}",
                exc_info=True
            )

            if attempt == MAX_RETRIES:
                log.error("[STEP 12] All retries exhausted")
                raise

            log.warning(f"[STEP 12] Retrying full step in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

        finally:
            if ssh:
                ssh.close()

    step_end("12 WUMS App Install (Profile Safe)")


# ==========================================================
# STEP 13 : APP VERSION DOWNGRADE & UPGRADE
# ==========================================================
def step_13_app_version_change(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    step_start("13 App Version Downgrade & Upgrade")

    ssh = None

    try:
        # ------------------------------------------------------
        # RESOLVE DEVICE + APP
        # ------------------------------------------------------
        with allure.step("Resolve device and application"):
            with step_log_context("Resolve device and application"):
                app = CFG["app"]
                dev = CFG["device"]

                device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
                context["device_id"] = device_id

        max_reboots = 2

        # ======================================================
        # PROCESS BOTH PHASES
        # ======================================================
        for phase in ("lower", "upper"):

            version = app["versions"][phase]

            with allure.step(f"{phase.upper()} phase → assign and verify {version['label']}"):
                with step_log_context(f"{phase.upper()} phase → assign and verify {version['label']}"):

                    version_applied = False

                    log.info(f"[STEP 13] {phase.upper()} → Assigning {version['label']}")

                    # --------------------------------------------------
                    # ASSIGN VERSION
                    # --------------------------------------------------
                    MAX_ASSIGN_ATTEMPTS = 3
                    ASSIGN_RETRY_DELAY = 15
                    assigned = False
                    last_error = None

                    for attempt in range(1, MAX_ASSIGN_ATTEMPTS + 1):
                        try:
                            log.info(
                                f"[STEP 13] {phase.upper()} assign attempt "
                                f"{attempt}/{MAX_ASSIGN_ATTEMPTS}"
                            )

                            api.assign_object(
                                device_id=device_id,
                                object_id=version["id"],
                                object_type="INSTALLED_APP_VERSION",
                                unassign=False
                            )

                            assigned = True
                            log.info(f"[STEP 13] {phase.upper()} assignment accepted")
                            break

                        except AssertionError as e:
                            msg = str(e).lower()
                            last_error = msg

                            log.error(
                                f"[STEP 13] Assign failed "
                                f"({phase.upper()}, attempt {attempt}): {msg}"
                            )

                            if "403" in msg:
                                log.warning(f"[STEP 13] {phase.upper()} 403 → refreshing auth")
                                time.sleep(5)
                                continue

                            if "409" in msg or "already" in msg or "conflict" in msg:
                                log.warning(f"[STEP 13] {phase.upper()} already applied")
                                assigned = True
                                break

                            log.warning(f"[STEP 13] Backend not ready ({msg}), retrying")
                            time.sleep(ASSIGN_RETRY_DELAY)

                    assert assigned, (
                        f"[STEP 13] Failed to assign {version['label']} "
                        f"after retries. Last error: {last_error}"
                    )

                    # --------------------------------------------------
                    # BACKEND SETTLE
                    # --------------------------------------------------
                    with allure.step("Wait for backend settle"):
                        with step_log_context("Wait for backend settle"):
                            log.info("[STEP 13] Waiting for backend settle")
                            time.sleep(10)

                    # --------------------------------------------------
                    # VERIFY ON DEVICE (REBOOT LOOP)
                    # --------------------------------------------------
                    with allure.step("Verify version on device"):
                        with step_log_context("Verify version on device"):

                            for attempt in range(1, max_reboots + 1):

                                log.info(
                                    f"[STEP 13] {phase.upper()} reboot attempt "
                                    f"{attempt}/{max_reboots}"
                                )

                                ssh = SSHClientIGEL(
                                    host=dev_cfg["ip"],
                                    port=22, username="root"
                                )
                                assert ssh.connect(), "[STEP 13] SSH connect failed before reboot"

                                time.sleep(30)
                                ssh.run_command("reboot")
                                ssh.close()
                                ssh = None

                                time.sleep(CFG["timeouts"]["reboot_wait"])

                                ssh = SSHClientIGEL(
                                    host=dev_cfg["ip"],
                                    port=22, username="root"
                                )
                                assert ssh.reconnect_with_retry(
                                    attempts=12,
                                    delay_sec=15
                                ), "[STEP 13] SSH did not come up after reboot"

                                _, out, _ = ssh.run_command("igelpkgctl list installed")

                                allure.attach(
                                    out,
                                    f"{phase} installed apps (Attempt {attempt})",
                                    allure.attachment_type.TEXT
                                )

                                if version["label"].lower() in out.lower():
                                    log.info(f"[STEP 13] {version['label']} applied successfully")
                                    version_applied = True
                                    break

                                log.warning(
                                    f"[STEP 13] {version['label']} not found after reboot {attempt}"
                                )

                                ssh.close()
                                ssh = None

                    assert version_applied, (
                        f"{version['label']} not found after {max_reboots} reboots "
                        f"during {phase} phase"
                    )

    except AssertionError as ae:
        log.error(f"[STEP 13] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 13] Unexpected error during version change",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("13 App Version Downgrade & Upgrade")


# ==========================================================
# STEP 14–15 : BASE SYSTEM DOWNGRADE & UPGRADE
# ==========================================================
def step_14_15_base_system_change(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    step_start("14–15 Base System Downgrade & Upgrade")

    ssh = None

    try:
        base = CFG["base_system"]
        dev = CFG["device"]

        # ----------------------------------------------------------
        # Resolve device
        # ----------------------------------------------------------
        with allure.step("Resolve device"):
            with step_log_context("Resolve device"):
                device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
                context["device_id"] = device_id

        # ----------------------------------------------------------
        # Helper (UNCHANGED)
        # ----------------------------------------------------------
        def get_installed_apps_excluding_base(ssh):
            _, output, _ = ssh.run_command("igelpkgctl list installed")

            apps = set()
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("Repository"):
                    continue
                if line.startswith("base_system"):
                    continue
                apps.add(line)

            return apps, output

        # ----------------------------------------------------------
        # Capture baseline
        # ----------------------------------------------------------
        with allure.step("Capture baseline installed apps"):
            with step_log_context("Capture baseline installed apps"):
                log.info("[STEP 14–15] Capturing baseline installed apps")

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )
                assert ssh.connect()

                baseline_apps, baseline_raw = get_installed_apps_excluding_base(ssh)
                ssh.close()
                ssh = None

                context["baseline_apps"] = baseline_apps

                allure.attach(
                    baseline_raw,
                    "Baseline Installed Apps",
                    allure.attachment_type.TEXT
                )

        # ==========================================================
        # PROCESS LOWER + UPPER BASE SYSTEM (WITH RETRY)
        # ==========================================================
        for phase in ("lower_version", "upper_version"):

            cfg = base[phase]

            MAX_PHASE_ATTEMPTS = 3
            PHASE_RETRY_DELAY = 20
            POST_REBOOT_SETTLE =20

            for attempt in range(1, MAX_PHASE_ATTEMPTS + 1):

                log.info(
                    f"[STEP 14–15] {phase} attempt "
                    f"{attempt}/{MAX_PHASE_ATTEMPTS}"
                )

                try:
                    with allure.step(f"{phase} attempt {attempt}"):

                        # --------------------------------------------------
                        # Assign base system
                        # --------------------------------------------------
                        MAX_ASSIGN_ATTEMPTS = 3
                        ASSIGN_RETRY_DELAY = 20
                        assigned = False
                        last_error = None

                        for assign_attempt in range(1, MAX_ASSIGN_ATTEMPTS + 1):
                            try:
                                log.info(
                                    f"[STEP 14–15] Assign attempt "
                                    f"{assign_attempt}/{MAX_ASSIGN_ATTEMPTS}"
                                )

                                api.assign_object(
                                    device_id=device_id,
                                    object_id=cfg["id"],
                                    object_type="INSTALLED_APP_VERSION",
                                    unassign=False
                                )

                                assigned = True
                                break

                            except AssertionError as e:
                                msg = str(e).lower()
                                last_error = msg

                                log.error(f"[STEP 14–15] Assign failed: {msg}")

                                if "403" in msg:
                                    log.warning("[STEP 14–15] 403 → refreshing auth")
                                    time.sleep(5)
                                    continue

                                if "409" in msg or "already" in msg or "conflict" in msg:
                                    assigned = True
                                    break

                                time.sleep(ASSIGN_RETRY_DELAY)

                        assert assigned, (
                            f"[STEP 14–15] Failed to assign base system {phase}. "
                            f"Last error: {last_error}"
                        )

                        # --------------------------------------------------
                        # Backend settle
                        # --------------------------------------------------
                        time.sleep(40)

                        # --------------------------------------------------
                        # Reboot
                        # --------------------------------------------------
                        ssh = SSHClientIGEL(
                            host=dev_cfg["ip"],
                            port=22,
                            username="root"
                        )
                        assert ssh.connect()

                        ssh.run_command("reboot")
                        ssh.close()
                        ssh = None

                        time.sleep(CFG["timeouts"]["reboot_wait"])

                        # --------------------------------------------------
                        # Reconnect
                        # --------------------------------------------------
                        ssh = SSHClientIGEL(
                            host=dev_cfg["ip"],
                            port=22,
                            username="root"
                        )

                        assert ssh.reconnect_with_retry(
                            attempts=12,
                            delay_sec=15
                        ), "[STEP 14–15] SSH did not come up after reboot"

                        log.info("[STEP 14–15] Device reachable after reboot")

                        time.sleep(POST_REBOOT_SETTLE)

                        # --------------------------------------------------
                        # VERIFY OS VERSION (NOW MANDATORY + RETRY DRIVER)
                        # --------------------------------------------------
                        log.info("[STEP 14–15] Verifying OS version")

                        verify_os_version(
                            ssh=ssh,
                            expected_version=cfg["expected"]
                        )

                        log.info("[STEP 14–15] OS version verified")

                        # --------------------------------------------------
                        # Validate installed apps unchanged
                        # --------------------------------------------------
                        baseline_apps = context["baseline_apps"]
                        after_apps, after_raw = get_installed_apps_excluding_base(ssh)

                        allure.attach(
                            after_raw,
                            f"Installed Apps after {phase}",
                            allure.attachment_type.TEXT
                        )

                        assert baseline_apps == after_apps, (
                            f"Installed apps changed after base system {phase}\n"
                            f"Before: {baseline_apps}\n"
                            f"After : {after_apps}"
                        )

                        ssh.close()
                        ssh = None

                        log.info(f"[STEP 14–15] {phase} validated successfully")

                        # SUCCESS → break retry loop
                        break

                except AssertionError as e:
                    log.warning(
                        f"[STEP 14–15] Attempt {attempt} failed: {e}"
                    )

                    if ssh:
                        ssh.close()
                        ssh = None

                    if attempt == MAX_PHASE_ATTEMPTS:
                        log.error(
                            f"[STEP 14–15] {phase} failed after max attempts"
                        )
                        raise

                    log.info("[STEP 14–15] Retrying full phase cycle...")
                    time.sleep(PHASE_RETRY_DELAY)

    except AssertionError as ae:
        log.error(f"[STEP 14–15] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 14–15] Unexpected error during base system change",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("14–15 Base System Downgrade & Upgrade")


# ==========================================================
# STEP 16 : REMOVE ASSIGNED APP (WITH RETRY)
# ==========================================================
def step_16_remove_assigned_app(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    step_start("16 Remove Assigned App")

    ssh = None

    MAX_REMOVE_ATTEMPTS = 3
    BACKEND_SETTLE = 25
    POST_REBOOT_SETTLE = 20

    try:
        app = CFG["app"]
        dev = CFG["device"]

        # ----------------------------------------------------------
        # Resolve device
        # ----------------------------------------------------------
        with allure.step("Resolve device"):
            with step_log_context("Resolve device"):
                device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
                context["device_id"] = device_id

        # ==========================================================
        # RETRY REMOVE LOOP
        # ==========================================================
        for attempt in range(1, MAX_REMOVE_ATTEMPTS + 1):

            log.info(
                f"[STEP 16] Remove attempt "
                f"{attempt}/{MAX_REMOVE_ATTEMPTS}"
            )

            # ------------------------------------------------------
            # UNASSIGN APPLICATION
            # ------------------------------------------------------
            with allure.step(f"Unassign app '{app['name']}' from device"):
                with step_log_context(f"Unassign app '{app['name']}' from device"):

                    MAX_UNASSIGN_ATTEMPTS = 3
                    UNASSIGN_RETRY_DELAY = 15
                    unassigned = False
                    last_error = None

                    for ua_attempt in range(1, MAX_UNASSIGN_ATTEMPTS + 1):
                        try:
                            log.info(
                                f"[STEP 16] Unassign attempt "
                                f"{ua_attempt}/{MAX_UNASSIGN_ATTEMPTS}"
                            )

                            status, text = api.unassign_object(
                                device_id=device_id,
                                object_id=app["id"],
                                object_type="INSTALLED_APP",
                                unassign=True
                            )
                            if status in (200, 204):
                                log.info(
                                    f"[STEP 16] App '{app['name']}' unassigned successfully "
                                    f"(status {status})"
                                )
                                unassigned = True
                                break

                                # ALREADY REMOVED (IMPORTANT FIX)
                            elif status == 404:
                                log.warning(
                                    f"[STEP 16] App '{app['name']}' already unassigned "
                                    f"(404 → treating as success)"
                                )
                                unassigned = True
                                break

                                # Unexpected status → retry
                            else:
                                last_error = f"Unexpected status: {status}, response: {text}"
                                log.error(f"[STEP 16] {last_error}")

                        except AssertionError as e:
                            msg = str(e).lower()
                            last_error = msg

                            log.error(f"[STEP 16] Unassign failed: {msg}")

                            if "403" in msg:
                                log.warning("[STEP 16] 403 → refreshing auth")
                                time.sleep(5)
                                continue

                            if "409" in msg or "already" in msg or "conflict" in msg:
                                log.warning("[STEP 16] App already unassigned")
                                unassigned = True
                                break

                            log.warning(
                                f"[STEP 16] Backend not ready → retrying in "
                                f"{UNASSIGN_RETRY_DELAY}s"
                            )
                            time.sleep(UNASSIGN_RETRY_DELAY)

                    assert unassigned, (
                        f"[STEP 16] Failed to unassign app '{app['name']}'. "
                        f"Last error: {last_error}"
                    )

            # ------------------------------------------------------
            # BACKEND SETTLE
            # ------------------------------------------------------
            log.info(
                f"[STEP 16] Waiting {BACKEND_SETTLE}s for backend settle"
            )
            time.sleep(BACKEND_SETTLE)

            # ------------------------------------------------------
            # REBOOT DEVICE
            # ------------------------------------------------------
            log.info("[STEP 16] Rebooting device to apply removal")

            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22, username="root"
            )
            assert ssh.connect()

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            # ------------------------------------------------------
            # RECONNECT
            # ------------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22, username="root"
            )
            assert ssh.reconnect_with_retry(
                attempts=12,
                delay_sec=15
            )

            log.info(
                f"[STEP 16] Waiting {POST_REBOOT_SETTLE}s "
                f"for system settle"
            )
            time.sleep(POST_REBOOT_SETTLE)

            # ------------------------------------------------------
            # VERIFY REMOVAL
            # ------------------------------------------------------
            _, out, _ = ssh.run_command("igelpkgctl list installed")

            allure.attach(
                out,
                "Installed Apps after removal attempt",
                allure.attachment_type.TEXT
            )

            def is_app_present(output):
                return app["name"].lower() in output.lower()

            # ------------------------------------------------------
            # FIRST CHECK
            # ------------------------------------------------------
            if not is_app_present(out):
                log.info(f"[STEP 16] App '{app['name']}' removed successfully")
                break

            log.warning(f"[STEP 16] App still present after reboot → retrying reboot once more")

            # ------------------------------------------------------
            # SECOND REBOOT (NEW BEHAVIOR)
            # ------------------------------------------------------
            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22, username="root"
            )
            assert ssh.reconnect_with_retry(attempts=12, delay_sec=15)

            time.sleep(POST_REBOOT_SETTLE)

            _, out, _ = ssh.run_command("igelpkgctl list installed")

            allure.attach(
                out,
                "Installed Apps after second reboot",
                allure.attachment_type.TEXT
            )

            # ------------------------------------------------------
            # SECOND CHECK
            # ------------------------------------------------------
            if not is_app_present(out):
                log.info(f"[STEP 16] App '{app['name']}' removed after second reboot")
                break

            log.warning(f"[STEP 16] App still present after second reboot (attempt {attempt})")

            # ------------------------------------------------------
            # FALLBACK TO FULL RETRY LOOP
            # ------------------------------------------------------
            if attempt == MAX_REMOVE_ATTEMPTS:
                raise AssertionError(
                    f"App '{app['name']}' still present after "
                    f"{MAX_REMOVE_ATTEMPTS} removal attempts"
                )

            log.info("[STEP 16] Restarting full removal cycle...")

        # END REMOVE RETRY LOOP

        ssh.close()
        ssh = None

    except AssertionError as ae:
        log.error(f"[STEP 16] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 16] Unexpected error during app removal",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("16 Remove Assigned App")


# ==========================================================
# STEP 17 : PROFILE APP INSTALL (WITH RETRY)
# ==========================================================
def step_17_profile_app_install(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    step_start("17 Profile App Install")

    ssh = None

    MAX_INSTALL_ATTEMPTS = 3
    BACKEND_SETTLE = 40
    POST_REBOOT_SETTLE = 20

    try:
        profile_cfg = CFG["profile_app"]
        dev = CFG["device"]

        # ----------------------------------------------------------
        # Create profile directory (unchanged)
        # ----------------------------------------------------------
        with allure.step("Create profile directory"):
            with step_log_context("Create profile directory"):
                MAX_DIR_ATTEMPTS = 3
                directory_id = None
                last_error = None

                for attempt in range(1, MAX_DIR_ATTEMPTS + 1):
                    try:
                        log.info(f"[STEP 17] Directory create attempt {attempt}/{MAX_DIR_ATTEMPTS}")

                        directory_id = api.create_profile_directory(
                            parent_directory_id=profile_cfg["parent_directory_id"],
                            directory_name=profile_cfg["directory_name"]
                        )
                        break

                    except AssertionError as e:
                        msg = str(e).lower()
                        last_error = msg
                        log.error(f"[STEP 17] Directory create failed: {msg}")

                        if "403" in msg:
                            log.warning("[STEP 17] 403 → refreshing auth")
                            time.sleep(5)
                            continue

                        raise

                assert directory_id, f"[STEP 17] Failed to create profile directory. Last error: {last_error}"

                context["profile_directory_id"] = directory_id

        # ----------------------------------------------------------
        # Create profile (unchanged)
        # ----------------------------------------------------------
        with allure.step("Create profile"):
            with step_log_context("Create profile"):

                MAX_PROFILE_ATTEMPTS = 3
                profile_id = None

                for attempt in range(1, MAX_PROFILE_ATTEMPTS + 1):
                    try:
                        log.info(f"[STEP 17] Profile create attempt {attempt}/{MAX_PROFILE_ATTEMPTS}")

                        profile = api.create_profile(
                            name=profile_cfg["profile_name"],
                            description=profile_cfg["description"],
                            directory_id=directory_id,
                            apps=profile_cfg["apps"]
                        )
                        profile_id = profile["id"]
                        break

                    except AssertionError as e:
                        msg = str(e).lower()
                        log.error(f"[STEP 17] Profile create failed: {msg}")

                        if "403" in msg:
                            time.sleep(5)
                            continue

                        raise

                assert profile_id, "[STEP 17] Profile creation failed"
                context["profile_id"] = profile_id

        # ----------------------------------------------------------
        # Resolve device
        # ----------------------------------------------------------
        device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
        context["device_id"] = device_id

        # ==========================================================
        # PROFILE APPLY RETRY LOOP
        # ==========================================================
        for attempt in range(1, MAX_INSTALL_ATTEMPTS + 1):

            log.info(f"[STEP 17] Profile apply attempt {attempt}/{MAX_INSTALL_ATTEMPTS}")

            # ------------------------------------------------------
            # ASSIGN PROFILE
            # ------------------------------------------------------
            assigned = False
            for assign_attempt in range(1, 4):
                try:
                    log.info(f"[STEP 17] Profile assign attempt {assign_attempt}/3")

                    api.assign_profile(
                        device_id=device_id,
                        profile_id=profile_id
                    )
                    assigned = True
                    break

                except AssertionError as e:
                    msg = str(e).lower()
                    log.error(f"[STEP 17] Profile assign failed: {msg}")

                    if "403" in msg:
                        time.sleep(5)
                        continue

                    if "409" in msg or "already" in msg:
                        assigned = True
                        break

                    raise

            assert assigned, "[STEP 17] Profile assignment failed"

            # ------------------------------------------------------
            # BACKEND SETTLE
            # ------------------------------------------------------
            log.info(f"[STEP 17] Waiting {BACKEND_SETTLE}s for backend settle")
            time.sleep(BACKEND_SETTLE)

            # ------------------------------------------------------
            # REBOOT DEVICE
            # ------------------------------------------------------
            log.info("[STEP 17] Rebooting device to apply profile")

            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22, username="root"
            )
            assert ssh.connect()

            ssh.run_command("reboot")
            ssh.close()
            ssh = None

            time.sleep(CFG["timeouts"]["reboot_wait"])

            # ------------------------------------------------------
            # RECONNECT
            # ------------------------------------------------------
            ssh = SSHClientIGEL(
                host=dev_cfg["ip"],
                port=22, username="root"
            )
            assert ssh.reconnect_with_retry(attempts=12, delay_sec=15)

            log.info(f"[STEP 17] Waiting {POST_REBOOT_SETTLE}s for system settle")
            time.sleep(POST_REBOOT_SETTLE)

            # ------------------------------------------------------
            # VERIFY APPS
            # ------------------------------------------------------
            _, output, _ = ssh.run_command("igelpkgctl list installed")

            allure.attach(output, "Installed Apps After Profile Apply", allure.attachment_type.TEXT)

            missing_apps = [
                app["expected_label"].lower()
                for app in profile_cfg["apps"]
                if app["expected_label"].lower() not in output.lower()
            ]

            if not missing_apps:
                log.info("[STEP 17] All profile apps installed successfully")
                break

            log.warning(f"[STEP 17] Missing apps after attempt {attempt}: {missing_apps}")

            if attempt == MAX_INSTALL_ATTEMPTS:
                raise AssertionError(f"[STEP 17] Missing profile apps after retries: {missing_apps}")

            log.info("[STEP 17] Retrying profile apply cycle...")

        # END RETRY LOOP

        ssh.close()
        ssh = None

    except AssertionError as ae:
        log.error(f"[STEP 17] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error("[STEP 17] Unexpected error during profile install", exc_info=True)
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("17 Profile App Install")


# ==========================================================
# STEP 18 : PROFILE APP VERSION CHANGE
# ==========================================================
def step_18_profile_version_change(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    step_start("18 Profile App Version Change")

    try:

        profile_cfg = CFG["profile_app_versions"]

        MAX_VERIFY_RETRIES = 2
        BACKEND_SETTLE_WAIT = 20
        UNASSIGN_MAX_ATTEMPTS = 3

        # ------------------------------------------------------
        # Resolve device
        # ------------------------------------------------------
        device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
        context["device_id"] = device_id

        # ------------------------------------------------------
        # Resolve profile from assigned objects (NEW)
        # ------------------------------------------------------
        MAX_FETCH_ATTEMPTS = 3
        FETCH_RETRY_DELAY = 5

        assigned_objects = None

        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):

            log.info(
                f"[STEP 18] Fetch assigned objects attempt "
                f"{attempt}/{MAX_FETCH_ATTEMPTS}"
            )

            try:
                assigned_objects = api.get_direct_assigned_objects(device_id)
                break

            except AssertionError as e:
                msg = str(e).lower()

                if "403" in msg:
                    log.warning("[STEP 18] 403 → refreshing auth")
                    time.sleep(FETCH_RETRY_DELAY)
                    continue

                raise

        assert assigned_objects, "[STEP 18] Failed to fetch assigned objects"

        profiles = [
            o for o in assigned_objects
            if o.get("type") == "PROFILE"
        ]

        assert profiles, "[STEP 18] No profile assigned to device"

        profile_id = profiles[0]["id"]

        log.info(f"[STEP 18] Profile resolved dynamically: {profile_id}")

        # ------------------------------------------------------
        # Helper : reboot + installed apps
        # ------------------------------------------------------
        def reboot_and_get_installed():

            ssh = SSHClientIGEL(dev_cfg["ip"], 22, "root")
            assert ssh.connect()

            time.sleep(30)

            ssh.run_command("reboot")
            ssh.close()

            time.sleep(CFG["timeouts"]["reboot_wait"])

            ssh = SSHClientIGEL(dev_cfg["ip"], 22, "root")
            assert ssh.reconnect_with_retry(attempts=12, delay_sec=15)

            _, out, _ = ssh.run_command("igelpkgctl list installed")
            ssh.close()

            allure.attach(out, "Installed Apps", allure.attachment_type.TEXT)

            return out.lower()

        # ------------------------------------------------------
        # Helper : verify expected versions
        # ------------------------------------------------------
        def verify_with_retries(expected, phase):

            global missing
            for attempt in range(1, MAX_VERIFY_RETRIES + 1):

                log.info(
                    f"[STEP 18] {phase} verification attempt {attempt}/{MAX_VERIFY_RETRIES}"
                )

                time.sleep(20)

                installed = reboot_and_get_installed()

                missing = [
                    v for v in expected
                    if v.lower() not in installed
                ]

                if not missing:
                    return

            raise AssertionError(
                f"[STEP 18] {phase} missing versions: {missing}"
            )

        # ------------------------------------------------------
        # APPLY DOWNGRADE TEMPLATE
        # ------------------------------------------------------
        with allure.step("Apply downgrade template versions"):

            expected = []

            for app in profile_cfg["apps"]:

                for attempt in range(1, 4):

                    log.info(
                        f"[STEP 18] DOWNGRADE attempt {attempt}/3 for {app['name']}"
                    )

                    status, text = api.set_template_version(
                        app_id=app["app_id"],
                        version_id=app["downgrade"]["version_id"],
                        profile_fixed_version_label=app["downgrade"]["expected_label"],
                        name=app["name"],
                        return_status=True
                    )

                    if status in (200, 204, 404):
                        expected.append(app["downgrade"]["expected_label"])
                        break

                    if status == 403:
                        time.sleep(5)
                        continue

                    if status in (409, 423, 425):
                        time.sleep(10)
                        continue

                    raise AssertionError(f"DOWNGRADE failed: {status} {text}")

        # ------------------------------------------------------
        # VERIFY DOWNGRADE
        # ------------------------------------------------------
        verify_with_retries(expected, "DOWNGRADE")

        # ------------------------------------------------------
        # APPLY UPGRADE TEMPLATE
        # ------------------------------------------------------
        with allure.step("Apply upgrade template versions"):

            expected = []

            for app in profile_cfg["apps"]:

                for attempt in range(1, 4):

                    log.info(
                        f"[STEP 18] UPGRADE attempt {attempt}/3 for {app['name']}"
                    )

                    status, text = api.set_template_version(
                        app_id=app["app_id"],
                        version_id=app["upgrade"]["version_id"],
                        profile_fixed_version_label=app["upgrade"]["expected_label"],
                        name=app["name"],
                        return_status=True
                    )

                    if status in (200, 204, 404):
                        expected.append(app["upgrade"]["expected_label"])
                        break

                    if status == 403:
                        time.sleep(5)
                        continue

                    if status in (409, 423, 425):
                        time.sleep(10)
                        continue

                    raise AssertionError(f"UPGRADE failed: {status} {text}")

        # ------------------------------------------------------
        # VERIFY UPGRADE
        # ------------------------------------------------------
        verify_with_retries(expected, "UPGRADE")

        # ------------------------------------------------------
        # WAIT FOR BACKEND SETTLE
        # ------------------------------------------------------
        log.info("[STEP 18] Waiting for backend settle")
        time.sleep(BACKEND_SETTLE_WAIT)

        # ------------------------------------------------------
        # PROFILE UNASSIGN LOOP
        # ------------------------------------------------------
        apps_removed = False

        for attempt in range(1, UNASSIGN_MAX_ATTEMPTS + 1):

            log.info(
                f"[STEP 18] Profile unassign attempt {attempt}/{UNASSIGN_MAX_ATTEMPTS}"
            )

            status, text = api.unassign_object(
                device_id=device_id,
                object_id=profile_id,
                object_type="PROFILE",
                unassign=True
            )

            if status == 403:
                continue

            if status not in (200, 202, 409, 423, 425):
                raise AssertionError(f"Unassign failed: {status} {text}")

            # reboot and check
            installed = reboot_and_get_installed()

            remaining = [
                app["name"].lower()
                for app in profile_cfg["apps"]
                if app["name"].lower() in installed
            ]

            if not remaining:
                apps_removed = True
                log.info("[STEP 18] Apps removed successfully")
                break

            log.warning(
                f"[STEP 18] Apps still present after unassign: {remaining}"
            )

        assert apps_removed, (
            "[STEP 18] Apps still installed after profile unassign retries"
        )

        log.info("[STEP 18] Profile lifecycle completed successfully")

    except AssertionError as ae:

        log.error(f"[STEP 18] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:

        log.error(
            "[STEP 18] Unexpected error during profile version change",
            exc_info=True
        )
        raise

    step_end("18 Profile App Version Change")


# ==========================================================
# STEP 19 : PROFILE WITH SPECIFIC APP VERSIONS
# ==========================================================
def step_19_profile_specific_versions(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    # ----------------------------------------------------------
    # CONFIG VALIDATION
    # ----------------------------------------------------------
    step19 = CFG.get("step19_profile")
    assert step19, "[STEP 19] Missing config 'step19_profile' in YAML"

    # ----------------------------------------------------------
    # DEPENDENCY VALIDATION
    # ----------------------------------------------------------
    directory_id = context.get("profile_directory_id")
    assert directory_id, (
        "[STEP 19] profile_directory_id missing. "
        "Step-17 must run before Step-19."
    )

    dev = CFG["device"]

    device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
    context["device_id"] = device_id

    step_start("19 Profile Specific Versions")

    ssh = None

    try:
        # ----------------------------------------------------------
        # CREATE PROFILE
        # ----------------------------------------------------------
        with allure.step("Create profile with specific app versions"):
            with step_log_context("Create profile with specific app versions"):

                profile_id = None
                last_error = None

                for attempt in range(1, 4):
                    try:
                        log.info(f"[STEP 19] Creating profile (attempt {attempt}/3)")

                        profile = api.create_profile(
                            name=step19["profile_name"],
                            description=step19["description"],
                            directory_id=directory_id,
                            apps=step19["apps"]
                        )
                        profile_id = profile["id"]

                        log.info(f"[STEP 19] Profile created: {profile_id}")
                        break

                    except Exception as e:
                        msg = str(e).lower()
                        last_error = msg

                        log.error(f"[STEP 19] Profile creation failed: {e}")

                        # ---------- AUTH EXPIRED ----------
                        if "403" in msg or "forbidden" in msg or "unauthorized" in msg:
                            log.warning("[STEP 19] 403 detected → refreshing auth")
                            time.sleep(5)
                            continue

                        # ---------- ALREADY EXISTS ----------
                        if "409" in msg or "already" in msg or "conflict" in msg:
                            log.warning("[STEP 19] Profile already exists → resolving ID")

                            profile_id = api.get_profile_id(step19["profile_name"])
                            break

                        # ---------- BACKEND BUSY ----------
                        if any(code in msg for code in ["404", "423", "425", "500", "502", "503"]):
                            log.warning("[STEP 19] Backend not ready → retrying")
                            time.sleep(15)
                            continue

                        raise

                assert profile_id, (
                    f"[STEP 19] Profile creation failed. Last error: {last_error}"
                )

                context["step19_profile_id"] = profile_id

                allure.attach(
                    str(profile_id),
                    "Step-19 Profile ID",
                    allure.attachment_type.TEXT
                )

        # ----------------------------------------------------------
        # ASSIGN PROFILE
        # ----------------------------------------------------------
        with allure.step("Assign profile to device"):
            with step_log_context("Assign profile to device"):

                assigned = False
                last_error = None

                for attempt in range(1, 4):
                    try:
                        log.info(f"[STEP 19] Assign profile attempt {attempt}/3")

                        api.assign_profile(
                            device_id=device_id,
                            profile_id=profile_id
                        )

                        assigned = True
                        log.info("[STEP 19] Profile assigned successfully")
                        break

                    except Exception as e:
                        msg = str(e).lower()
                        last_error = msg

                        log.error(f"[STEP 19] Profile assign failed: {e}")

                        if "403" in msg:
                            log.warning("[STEP 19] 403 detected → refreshing auth")
                            time.sleep(5)
                            continue

                        if "409" in msg or "already" in msg or "conflict" in msg:
                            log.warning("[STEP 19] Profile already assigned")
                            assigned = True
                            break

                        time.sleep(10)

                assert assigned, (
                    f"[STEP 19] Profile assignment failed. Last error: {last_error}"
                )

        # ----------------------------------------------------------
        # BACKEND SETTLE
        # ----------------------------------------------------------
        with allure.step("Wait backend settle"):
            with step_log_context("Wait backend settle"):
                log.info("[STEP 19] Waiting for backend settle")
                time.sleep(20)

        # ----------------------------------------------------------
        # REBOOT + VERIFY
        # ----------------------------------------------------------
        with allure.step("Reboot device and verify specific app versions"):
            with step_log_context("Reboot device and verify specific app versions"):

                max_reboots = 2
                profile_applied = False

                for attempt in range(1, max_reboots + 1):
                    log.info(f"[STEP 19] Reboot attempt {attempt}/{max_reboots}")

                    ssh = SSHClientIGEL(
                        host=dev_cfg["ip"],
                        port=22, username="root"
                    )
                    assert ssh.connect(), "SSH connect failed before reboot"

                    time.sleep(20)
                    ssh.run_command("reboot")
                    ssh.close()

                    time.sleep(CFG["timeouts"]["reboot_wait"])

                    ssh = SSHClientIGEL(
                        host=dev_cfg["ip"],
                        port=22, username="root"
                    )
                    assert ssh.reconnect_with_retry(
                        attempts=12,
                        delay_sec=15
                    ), "SSH not reachable after reboot"

                    _, out, _ = ssh.run_command("igelpkgctl list installed")

                    allure.attach(
                        out,
                        f"Installed Apps After Step-19 Profile (Attempt {attempt})",
                        allure.attachment_type.TEXT
                    )

                    ssh.close()

                    missing = [
                        app["expected_label"]
                        for app in step19["apps"]
                        if app["expected_label"].lower() not in out.lower()
                    ]

                    if not missing:
                        log.info("[STEP 19] All specific versions verified")
                        profile_applied = True
                        break

                    log.warning(
                        f"[STEP 19] Missing versions after reboot {attempt}: {missing}"
                    )

                assert profile_applied, (
                    "[STEP 19] Profile-specific app versions not applied after reboot"
                )

    except AssertionError as ae:
        log.error(f"[STEP 19] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:
        log.error(
            "[STEP 19] Unexpected error during profile specific version test",
            exc_info=True
        )
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("19 Profile Specific Versions")


# ==========================================================
# STEP 20 : PROFILE VERSION LOCK
# ==========================================================
def step_20_profile_version_lock(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]
    ums_cfg = context["ums_cfg"]

    # ----------------------------------------------------------
    # CONFIG VALIDATION
    # ----------------------------------------------------------
    apps = CFG.get("step20_apps")
    assert apps, "[STEP 20] Missing config 'step20_apps' in YAML"

    dev = CFG["device"]

    step_start("20 Profile Version Lock")

    ssh = None

    try:

        # ----------------------------------------------------------
        # CAPTURE BASELINE INSTALLED APPS
        # ----------------------------------------------------------
        with allure.step("Capture baseline installed apps"):
            with step_log_context("Capture baseline installed apps"):
                log.info("[STEP 20] Capturing baseline installed apps")

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22,
                    username="root"
                )

                assert ssh.connect(), "SSH connect failed while capturing baseline"

                _, baseline_out, _ = ssh.run_command("igelpkgctl list installed")

                ssh.close()
                ssh = None

                allure.attach(
                    baseline_out,
                    "Baseline Installed Apps (Before Template Change)",
                    allure.attachment_type.TEXT
                )

        # ----------------------------------------------------------
        # CHANGE DEFAULT TEMPLATE VERSIONS
        # ----------------------------------------------------------
        with allure.step("Change default template versions"):
            with step_log_context("Change default template versions"):

                for app in apps:

                    success = False

                    for attempt in range(1, 4):

                        log.info(
                            f"[STEP 20] Setting default template version "
                            f"{app['profile_fixed_version_label']} "
                            f"(attempt {attempt}/3)"
                        )

                        status, text = api.set_template_version(
                            app_id=app["app_id"],
                            version_id=app["new_default_version_id"],
                            profile_fixed_version_label=app["profile_fixed_version_label"],
                            name=app["name"],
                            return_status=True
                        )

                        if status in (200, 204, 404):
                            log.info(
                                f"[STEP 20] Template version set successfully "
                                f"for {app['name']} (status {status})"
                            )

                            success = True
                            break

                        if status == 403:
                            log.warning("[STEP 20] 403 detected, refreshing auth")
                            time.sleep(5)
                            continue

                        if status in (409, 423, 425):
                            time.sleep(10)
                            continue

                        raise AssertionError(
                            f"[STEP 20] Failed to set template version for {app['name']}"
                        )

                    assert success, (
                        f"[STEP 20] Failed to set template version for {app['name']}"
                    )

        # ----------------------------------------------------------
        # BACKEND SETTLE
        # ----------------------------------------------------------
        with allure.step("Wait for backend settle"):
            with step_log_context("Wait for backend settle"):
                log.info("[STEP 20] Waiting for backend propagation")
                time.sleep(25)

        # ----------------------------------------------------------
        # REBOOT DEVICE
        # ----------------------------------------------------------
        with allure.step("Reboot device"):
            with step_log_context("Reboot device"):
                log.info("[STEP 20] Rebooting device")

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.connect(), "SSH connect failed before reboot"

                ssh.run_command("reboot")
                ssh.close()
                ssh = None

                time.sleep(CFG["timeouts"]["reboot_wait"])

        # ----------------------------------------------------------
        # VERIFY VERSION LOCK
        # ----------------------------------------------------------
        with allure.step("Verify profile-fixed versions remain locked"):
            with step_log_context("Verify profile-fixed versions remain locked"):

                log.info("[STEP 20] Verifying profile version lock on device")

                ssh = SSHClientIGEL(
                    host=dev_cfg["ip"],
                    port=22, username="root"
                )

                assert ssh.reconnect_with_retry(
                    attempts=12,
                    delay_sec=15
                ), "SSH did not come up after reboot"

                _, after_out, _ = ssh.run_command("igelpkgctl list installed")

                ssh.close()
                ssh = None

                allure.attach(
                    after_out,
                    "Installed Apps After Template Version Change",
                    allure.attachment_type.TEXT
                )

                failures = []

                for app in apps:

                    expected = app["profile_fixed_version_label"].lower()

                    if expected not in after_out.lower():
                        failures.append(
                            f"{app['name']} expected {expected}"
                        )

                assert not failures, (
                        "[STEP 20] Version lock verification failed:\n"
                        + "\n".join(failures)
                )

                log.info("[STEP 20] Profile version lock verified successfully")

    except AssertionError as ae:

        log.error(f"[STEP 20] Validation failed: {ae}", exc_info=True)
        raise

    except Exception:

        log.error(
            "[STEP 20] Unexpected error during profile version lock validation",
            exc_info=True
        )
        raise

    finally:

        if ssh:
            ssh.close()

    step_end("20 Profile Version Lock")

# ==========================================================
# STEP : FINAL CLEANUP (PROFILE + APPS + DEVICE RESET)
# ==========================================================
def step_cleanup(context):
    CFG = context["CFG"]
    api = context["api"]
    dev_cfg = context["device_cfg"]

    step_start(" Final Cleanup")

    MAX_RETRIES = 3
    BACKEND_SETTLE = 40
    POST_REBOOT_SETTLE = 20

    ssh = None

    try:
        # --------------------------------------------------
        # RESOLVE DEVICE
        # --------------------------------------------------
        device_id = context.get("device_id") or api.get_device_id(dev_cfg["name"])
        context["device_id"] = device_id

        log.info(f"[STEP ] Device ID: {device_id}")

        # --------------------------------------------------
        # FETCH ASSIGNED OBJECTS
        # --------------------------------------------------
        assigned_objects = api.get_direct_assigned_objects(device_id)

        profiles = [o for o in assigned_objects if o.get("type") == "PROFILE"]
        apps = [o for o in assigned_objects if o.get("type") in ("INSTALLED_APP", "INSTALLED_APP_VERSION")]

        log.info(f"[STEP] Found profiles: {profiles}")
        log.info(f"[STEP] Found apps/versions: {apps}")

        # ==================================================
        # UNASSIGN PROFILES
        # ==================================================
        for profile in profiles:

            profile_id = profile["id"]

            for attempt in range(1, MAX_RETRIES + 1):

                log.info(
                    f"[STEP] Profile unassign attempt {attempt}/{MAX_RETRIES}"
                )

                status, text = api.unassign_object(
                    device_id=device_id,
                    object_id=profile_id,
                    object_type="PROFILE",
                    unassign=True
                )

                log.info(f"[STEP] Profile unassign response: {status} | {text}")

                if status in (200, 202, 204, 404):
                    break

                if status == 403:
                    time.sleep(5)
                    continue

                time.sleep(10)

        # ==================================================
        # UNASSIGN APPS / VERSIONS
        # ==================================================
        for obj in apps:

            obj_id = obj["id"]
            obj_type = obj["type"]

            for attempt in range(1, MAX_RETRIES + 1):

                log.info(
                    f"[STEP] Unassign {obj_type} {obj_id} "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )

                status, text = api.unassign_object(
                    device_id=device_id,
                    object_id=obj_id,
                    object_type=obj_type,
                    unassign=True
                )

                log.info(f"[STEP] Unassign response: {status} | {text}")

                if status in (200, 202, 204, 404):
                    break

                if status == 403:
                    time.sleep(5)
                    continue

                time.sleep(10)

        # --------------------------------------------------
        # BACKEND SETTLE
        # --------------------------------------------------
        log.info(f"[STEP] Waiting {BACKEND_SETTLE}s for backend settle")
        time.sleep(BACKEND_SETTLE)

        # --------------------------------------------------
        # FINAL REBOOT
        # --------------------------------------------------
        log.info("[STEP 21] Rebooting device for cleanup")

        ssh = SSHClientIGEL(
            host=dev_cfg["ip"],
            port=22,
            username="root"
        )

        assert ssh.connect(), "[STEP] SSH connect failed before reboot"

        ssh.run_command("reboot")
        ssh.close()
        ssh = None

        time.sleep(CFG["timeouts"]["reboot_wait"])

        # --------------------------------------------------
        # VALIDATE DEVICE ALIVE
        # --------------------------------------------------
        ssh = SSHClientIGEL(
            host=dev_cfg["ip"],
            port=22,
            username="root"
        )

        assert ssh.reconnect_with_retry(
            attempts=12,
            delay_sec=15
        ), "[STEP] SSH not reachable after cleanup reboot"

        log.info(f"[STEP] Waiting {POST_REBOOT_SETTLE}s for system settle")
        time.sleep(POST_REBOOT_SETTLE)

        # --------------------------------------------------
        # FINAL VALIDATION (NO APPS)
        # --------------------------------------------------
        _, out, _ = ssh.run_command("igelpkgctl list installed")

        allure.attach(
            out,
            "Final Installed Apps After Cleanup",
            allure.attachment_type.TEXT
        )

        log.info("[STE] Cleanup completed successfully")

    except Exception:
        log.error("[STEP] Cleanup failed", exc_info=True)
        raise

    finally:
        if ssh:
            ssh.close()

    step_end("Final Cleanup")

@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("01–02: Device Registration")
def test_tc3119_step01(tc3119_context):
    step_1_2_device_registration(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("03: Add QA Repo")
def test_QCL_3119_step02(tc3119_context):
    step_3_add_qa_repo(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("04: Install Apps")
def test_QCL_3119_step03(tc3119_context):
    step_4_install_apps(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("05: App Downgrade")
def test_QCL_3119_step04(tc3119_context):
    step_5_app_downgrade(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("06: Base System Downgrade")
def test_QCL_3119_step05(tc3119_context):
    step_6_base_downgrade(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("07: Validate After Downgrade")
def test_QCL_3119_step06(tc3119_context):
    step_7_validate_after_downgrade(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("08: Base System Upgrade")
def test_QCL_3119_step07(tc3119_context):
    step_8_base_upgrade(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("09: Validate After Base Upgrade")
def test_QCL_3119_step08(tc3119_context):
    step_9_validate_after_upgrade(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("10: Dependency Negative Test")
def test_QCL_3119_step09(tc3119_context):
    step_10_dependency_negative(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("11: Uninstall All Apps")
def test_QCL_3119_step10(tc3119_context):
    step_11_uninstall_all(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("12: WUMS App Install")
def test_QCL_3119_step11(tc3119_context):
    step_12_wums_app_install(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("13: App Version Downgrade & Upgrade")
def test_QCL_3119_step12(tc3119_context):
    step_13_app_version_change(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("14–15: Base System via WUMS")
def test_QCL_3119_step13(tc3119_context):
    step_14_15_base_system_change(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("16: Remove Assigned App")
def test_QCL_3119_step14(tc3119_context):
    step_16_remove_assigned_app(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("17: Profile App Install")
def test_QCL_3119_step15(tc3119_context):
    step_17_profile_app_install(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("18: Profile Version Change")
def test_QCL_3119_step16(tc3119_context):
    step_18_profile_version_change(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("19: Profile Specific Versions")
def test_QCL_3119_step17(tc3119_context):
    step_19_profile_specific_versions(tc3119_context)


@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("20: Profile Version Lock")
def test_QCL_3119_step18(tc3119_context):
    step_20_profile_version_lock(tc3119_context)

@pytest.mark.device
@pytest.mark.smoke
@allure.feature("TC-3119")
@allure.title("Final Cleanup")
def test_QCL_3119_step19(tc3119_context):
    step_cleanup(tc3119_context)