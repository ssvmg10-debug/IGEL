"""
This Python SSH code establishes a secure connection to a remote server to execute commands or transfer data.
It enables automation of remote system management tasks using authenticated SSH sessions.
"""

import paramiko
import time
import os
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
            print(f"Connecting to host: {self.host} ")

            if self.key_file:
                key = paramiko.RSAKey.from_private_key_file(self.key_file)
                handle.connect(hostname=self.host, port=self.port,
                                    username=self.user, pkey=key)
            else:
                handle.connect(hostname=self.host, port=self.port,
                                    username=self.user, password=self.pwd)

            print(f"[+] Connected to {self.host}")
            return handle
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return None
            #exit()

    def reconnect(self):
        print("[+] Attempting to reconnect...")
        try:
            self.handle = self._connect_()
            if self.handle:
                print("[+] Reconnected successfully.")
            else:
                print("[-] Failed to reconnect.")
                return None
        except Exception as e:
            print(f"[!] Exception during reconnection : {e}")
            return None

# New Change:
    def exec(self, command):
        if self.handle is None:
            self.handle = self.reconnect()
        handle=self.handle
        print(f"Executing command... {command}")
        if handle is None:
            print("[!] Server not connected.")
            return None

    # def exec(self, command):
    #     handle=self.handle
    #     print(f"Executing command... {command}")
    #     if handle is None:
    #         print("[!] Server not connected.")
    #         return None

        try:
            stdin, stdout, stderr = handle.exec_command(command, timeout = 30)
            output = stdout.read().decode()
            error = stderr.read().decode()

            print(f"Output = {output}")

            return output if output else error
        except Exception as e:
            print(f"[!] Failed to execute command: {e}")
            return None

    def getpid(self, process):
        try:
            pid=self.exec(f"pidof {process}")
            if pid is None:
                print(f"Error getting pid for {process}")
            return pid
        except Exception as e:
            print(f"Exception getting pid for {process}: {e}");
            return None

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
        """Transfer file from local to remote server
        Note: Suitable for small files only!!!
        """

        try:
            with open(local_file, "r") as f:
                data = f.read()

            sftp =self.handle.open_sftp()
            with sftp.open(remote_file, 'w') as f:
                f.write(data)

            sftp.close()
            print("[+] Copied file to remote.")
            return True
        except Exception as e:
            print(f"[!] Failed to copy file to remote: {e}")
            return False

    def download_file(self, src_path, dst_path):
        handle = self.handle

        try:
            sftp = handle.open_sftp()
            if src_path is None or dst_path is None:
                print(f"[!] Invalid source/destination file path provided!")
                return False

            # ---- Verify remote file ----
            try:
                sftp.stat(src_path)
            except IOError:
                print(f"[!] Remote file not found: {src_path}")
                return

            # ---- Verify local path ----
            local_dir = os.path.dirname(dst_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir)
                print(f"[+] Created local directory: {local_dir}")

            # ---- Download file ----
            print(f"Downloading {src_path} -> {dst_path}")
            sftp.get(src_path, dst_path)

            print("[+] Download completed")

            sftp.close()
            return True

        except Exception as e:
            print(f"[!] Download failed: {e}")
            return False
            
    def get_version(self):
        """
        This function returns the version of IGEL
        """
        try:

            release = self.exec("cat /etc/os-release")
            result = dict(line.split("=", 1) for line in release.splitlines() if line.strip())
            result = {k: v.strip('"') for k, v in result.items()}
            return result['VERSION']

        except Exception as e:
            print(f"[!] Failed to get version: {e}")
            return None


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

    def close(self):
        if self.handle:
            try:
                self.handle.close()
                print(f"[-] Disconnected from {self.host}")
            except Exception as e:
                print(f"Error closing connection {self.host}: {e}")
            finally:
                self.handle = None

#LG#
    def launch_windows_app(self, app_name="mspaint"):
        if not self.handle:
            print("SSH not connected")
            return False
        cmd = (
            "export DISPLAY=:0 && "
            f"xdotool key Super_L && "
            "sleep 2 && "
            f"xdotool type '{app_name}' && "
            "sleep 1 && "
            "xdotool key Return"
        )
        print(f"[+] Launching Windows app: {app_name}")
        exit_code, out, err = self.run_command(cmd, timeout=20)
        if exit_code == 0:
            print("[+] Application launch command sent")
            return True
        else:
            print(err)
            return False

# LG
