"""
This Python SSH code establishes a secure connection to a remote server to execute commands or transfer data.
It enables automation of remote system management tasks using authenticated SSH sessions.
"""

import logging
import paramiko
import time
import os

log = logging.getLogger(__name__)

max_retries=6

class SSHClient:
    def __init__(self, host, user, pwd=None, port=22, key_file=None):
        self.host = host
        self.port = port
        self.user = user
        self.pwd = pwd
        self.key_file = key_file
        self.handle = self._connect_()

    def _connect_(self):
        try:
            handle = paramiko.SSHClient()
            handle.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            log.info("Connecting to host: %s", self.host)

            if self.key_file:
                key = paramiko.RSAKey.from_private_key_file(self.key_file)
                handle.connect(hostname=self.host, port=self.port,
                                    username=self.user, pkey=key)
            else:
                handle.connect(hostname=self.host, port=self.port,
                                    username=self.user, password=self.pwd)

            log.info("Connected to %s", self.host)
            return handle
        except Exception as e:
            log.error("SSH connection to %s failed: %s", self.host, e)
            return None

    def reconnect(self):
        log.info("Attempting to reconnect...")
        try:
            self.handle = self._connect_()
            if self.handle:
                log.info("Reconnected successfully.")
                return self.handle
            else:
                log.error("Failed to reconnect.")
                return None
        except Exception as e:
            log.error("Exception during reconnection: %s", e)
            return None

    def exec(self, command):
        if self.handle is None:
            self.handle = self.reconnect()
        if self.handle is None:
            raise ConnectionError(f"SSH not connected to {self.host}")

        log.debug("Executing command: %s", command)
        try:
            stdin, stdout, stderr = self.handle.exec_command(command, timeout=30)
            output = stdout.read().decode()
            error = stderr.read().decode()
            return output if output else error
        except Exception as e:
            log.error("Failed to execute command '%s': %s", command, e)
            raise RuntimeError(f"SSH command execution failed: {e}") from e

    def getpid(self, process):
        pid=self.exec(f"pidof {process}")
        if not pid or not pid.strip():
            log.warning("Process not found: %s", process)
            return None
        return pid.strip()

    def boot_errors(self):
        print("== Checking dmesg for boot-time errors ==")
        dmesg_output = self.exec("dmesg --level=err,warn")
        print(dmesg_output or "No boot errors or warnings found in dmesg.\n")
        print("== Checking for failed systemd services ==")
        failed_services = self.exec("systemctl --failed")
        print(failed_services or "No failed services.\n")
        print("== Checking journalctl for current boot logs ==")
        journalctl_output = self.exec("journalctl -b -p err")
        print(journalctl_output or "No errors found in journalctl for current boot.\n")
        if dmesg_output or failed_services or journalctl_output:
            return  False
        else:
            return True

    def close(self):
        if self.handle:
            try:
                self.handle.close()
                log.info("Disconnected from %s", self.host)
            except Exception as e:
                log.warning("Error closing connection to %s: %s", self.host, e)
            finally:
                self.handle = None

    def reboot(self):
        if not self.handle:
            print("SSH client not connected.")
            return -1

        print("[+] Sending reboot command...")
        status = self.exec("reboot")

        """"'# If password is needed for sudo
        #if self.password:
        #    stdin.write(self.password + '\n')
        #    stdin.flush()"""
        print("[+] Reboot command sent.")
        self.close()
        """Wait and attempt to reconnect after reboot."""
        print("[+] Waiting for system to go down and come back online...")
        time.sleep(10)  # Initial wait for shutdown

        for attempt in range(1, max_retries):
            print(f"[?] Attempting to reconnect... (Try {attempt}/{max_retries})")
            time.sleep(10)
            self.handle=self._connect_()
            if self.handle:
                print("[+] Reconnected successfully.")
                return True

        print("[-] Failed to reconnect after reboot.")
        return False

    def copy_file_to_remote(self, local_file, remote_file):
        """Transfer file from local to remote server.
        Note: Suitable for small files only.
        """
        if not self.handle:
            raise ConnectionError("SSH not connected")

        try:
            with open(local_file, "r") as f:
                data = f.read()

            sftp = self.handle.open_sftp()
            with sftp.open(remote_file, 'w') as f:
                f.write(data)

            sftp.close()
            log.info("Copied file to remote: %s -> %s", local_file, remote_file)
            return True
        except Exception as e:
            log.error("Failed to copy file to remote: %s", e)
            raise

    def download_file(self, src_path, dst_path):
        if not self.handle:
            raise ConnectionError("SSH not connected")
        if src_path is None or dst_path is None:
            raise ValueError("src_path and dst_path are required")

        sftp = self.handle.open_sftp()
        try:
            try:
                sftp.stat(src_path)
            except IOError:
                raise FileNotFoundError(f"Remote file not found: {src_path}")

            local_dir = os.path.dirname(dst_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir)
                log.info("Created local directory: %s", local_dir)

            log.info("Downloading %s -> %s", src_path, dst_path)
            sftp.get(src_path, dst_path)
            log.info("Download completed")
            return True
        finally:
            sftp.close()
            
    def get_version(self):
        """Returns the IGEL OS version string."""
        release = self.exec("cat /etc/os-release")
        if not release:
            raise RuntimeError("Could not read /etc/os-release")
        result = dict(line.split("=", 1) for line in release.splitlines() if "=" in line)
        result = {k: v.strip('"') for k, v in result.items()}
        if 'VERSION' not in result:
            raise RuntimeError(f"VERSION not found in /etc/os-release: {result}")
        return result['VERSION']


#===================================================================================================
# LG ####
    def reconnect_with_retry(self, retries=6, delay=10, **kwargs):
        attempts = kwargs.get("attempts", retries)
        delay_sec = kwargs.get("delay_sec", delay)

        for attempt in range(1, attempts + 1):
            try:
                print(f"[?] Attempting to reconnect... (Try {attempt}/{attempts})")
                self.handle = self._connect_()
                if self.handle:
                    print("[+] Reconnected successfully.")
                    return True
            except Exception as e:
                print(f"[!] Connection failed: {e}")

            time.sleep(delay_sec)

        return False
    
    def wait_until_ready(self, timeout=180, interval=10):
        # Wait until SSH connection becomes available. Used after reboot.
        print("[+] Waiting for SSH to become ready...")
        start = time.time()

        while time.time() - start < timeout:
            if self.reconnect_with_retry(attempts=1, delay_sec=2):
                print("[+] SSH is ready.")
                return True
            print("[?] SSH not ready yet. Retrying...")
            time.sleep(interval)

            print("[-] SSH did not become ready in time.")
            return False

#LG#
    def launch_windows_app(self, app_name="mspaint"):
        if not self.handle:
            raise ConnectionError("SSH not connected")
        cmd = (
            "export DISPLAY=:0 && "
            f"xdotool key Super_L && "
            "sleep 2 && "
            f"xdotool type '{app_name}' && "
            "sleep 1 && "
            "xdotool key Return"
        )
        log.info("Launching Windows app: %s", app_name)
        result = self.exec(cmd)
        if result is not None:
            log.info("Application launch command sent")
            return True
        return False
