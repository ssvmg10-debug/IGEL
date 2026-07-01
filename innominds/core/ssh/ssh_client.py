###########################################################
# Title        : IGEL SSH Client Utility
# Description  : Lightweight SSH client wrapper built on
#                Paramiko to manage SSH connectivity to
#                IGEL devices, execute remote commands,
#                handle reconnection logic, and perform
#                device reboot with automatic SSH recovery.
#
# Prerequisites:
#   - Python 3.10+
#   - paramiko
#   - Network connectivity to IGEL device
#   - Valid SSH credentials
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.1
############################################################


import logging

import paramiko
import time

log = logging.getLogger(__name__)


class SSHClientIGEL:
    def __init__(self, host: str, port: int, username: str, password: str | None = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = ""
        self.client: paramiko.SSHClient | None = None

    def connect(self, timeout: int = 10) -> bool:
        log.info("SSH connecting to %s:%d as %s", self.host, self.port, self.username)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self.client = ssh
            log.info("SSH connection successful.")
            return True
        except (paramiko.SSHException, OSError) as e:
            log.error("SSH connection error: %s", e)
            try:
                ssh.close()
            except Exception:
                pass
            self.client = None
            return False

    def run_command(self, command: str, timeout: int = 60) -> tuple[int, str, str]:
        if not self.client:
            raise ConnectionError("SSH not connected")

        log.debug("Executing: %s", command)
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="ignore")
            err = stderr.read().decode("utf-8", errors="ignore")
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, out, err
        except (paramiko.SSHException, OSError) as e:
            log.error("SSH command execution failed: %s", e)
            raise RuntimeError(f"SSH exec_command error: {e}") from e

    def reconnect_with_retry(self, attempts: int = 12, delay_sec: int = 15) -> bool:
        if self.client:
            try:
                print("[SSH] Closing connection before reconnect...")
                self.client.close()
            except Exception:
                pass
            self.client = None

        for i in range(1, attempts + 1):
            print(f"[SSH] Reconnect attempt {i}/{attempts}...")
            if self.connect():
                print("[SSH] Reconnection successful.")
                return True
            time.sleep(delay_sec)

        print("[SSH] Reconnection failed after all attempts.")
        return False

    def close(self):
        if self.client:
            print("[SSH] Closing connection.")
            self.client.close()
            self.client = None

    def reboot_and_reconnect(
            self,
            reboot_wait: int = 10,
            reconnect_attempts: int = 12,
            reconnect_delay: int = 15,
    ):
        """
        Reboot device via SSH and wait until it comes back.
        """
        print("[SSH] Rebooting device")

        # send reboot
        self.run_command("reboot")
        self.close()

        print(f"[SSH] Waiting {reboot_wait}s before reconnect attempts")
        time.sleep(reboot_wait)

        # reconnect loop
        success = self.reconnect_with_retry(
            attempts=reconnect_attempts,
            delay_sec=reconnect_delay,
        )

        if not success:
            raise RuntimeError("[SSH] Device did not come back after reboot")

        print("[SSH] Device rebooted and SSH reconnected successfully")

    def run(self, command: str, timeout: int = 60) -> str:
        """
        Backward-compatible wrapper for run_command().
        Returns STDOUT only (like legacy IGELSSH.run()).
        """
        exit_code, out, err = self.run_command(command, timeout=timeout)
        if exit_code != 0:
            raise RuntimeError(f"SSH command failed: {err}")
        return out
