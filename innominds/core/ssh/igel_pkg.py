###########################################################
# Title        : SSH Helpers & Verification Utilities
# Description  : Helper functions used during automated
#                device provisioning to maintain SSH
#                connectivity, verify application
#                installation status, and validate the
#                base system OS version on IGEL devices.
#
# Prerequisites:
#   - Python 3.10+
#   - core.ssh_client.SSHClientIGEL
#   - core.logger.get_logger
#   - SSH access to IGEL device
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.1
############################################################






import time
import re
from core.ssh.ssh_client import SSHClientIGEL
from core.utils.logger import get_logger

log = get_logger(__name__)


# ==========================================================
# HELPERS (USED BY STEP 3–11)
# ==========================================================

def ensure_ssh_alive(ssh: SSHClientIGEL):
    """
    Prevent SSH timeout during long app installs.
    """
    try:
        ssh.run("true")
    except Exception:
        log.warning("[SSH] Connection dropped, reconnecting")
        ssh.reboot_and_reconnect()


def verify_apps_installed(
        ssh: SSHClientIGEL,
        app_names: list[str],
        timeout_sec: int = 300
):
    """
    Poll until all expected apps appear.
    """
    start = time.time()

    while time.time() - start < timeout_sec:
        output = ssh.run("igelpkgctl list installed")
        missing = [
            app for app in app_names
            if app.lower() not in output.lower()
        ]

        if not missing:
            log.info("[VERIFY] All apps installed")
            return

        log.info(f"[VERIFY] Missing apps: {missing}")
        time.sleep(20)

    raise AssertionError(
        f"Apps not installed after timeout: {missing}"
    )


# ==========================================================
# BASE SYSTEM OS VERSION VERIFICATION (NEW)
# ==========================================================

def verify_os_version(
    ssh: SSHClientIGEL,
    expected_version: str
):
    """
    Verify /etc/os-release VERSION_ID matches expected version.

    Example expected_version: "12.7.4"
    """

    log.info("[VERIFY] Checking base system OS version")

    output = ssh.run("cat /etc/os-release")
    log.info(f"[VERIFY] /etc/os-release output:\n{output}")

    match = re.search(r'VERSION="?([^"\n]+)"?', output)

    if not match:
        raise AssertionError(
            "VERSION_ID not found in /etc/os-release"
        )

    actual_version = match.group(1)

    if actual_version != expected_version:
        raise AssertionError(
            f"Base system version mismatch: "
            f"expected={expected_version}, actual={actual_version}"
        )

    log.info(
        f"[VERIFY] Base system version verified successfully "
        f"(VERSION_ID={actual_version})"
    )
