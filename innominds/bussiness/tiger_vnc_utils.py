import logging
import time
import subprocess
from typing import Optional
import socket

log = logging.getLogger(__name__)

TIGERVNC_PATH = r"\\bin\\vncviewer.exe"
PROCESS_NAME = "tvncviewer.exe"

class Vnc_utils:
    # ----------------------------------------------
    # OPEN TIGERVNC IN FULL SCREEN
    # ----------------------------------------------


    def __init__(self, tigervnc_path: str = TIGERVNC_PATH):
        self.tigervnc_path = tigervnc_path

    # ----------------------------------------------
    # CHECK IF VNC PORT IS OPEN
    # ----------------------------------------------
    def is_vnc_port_open(self, ip: str, port: int = 5900, timeout: int = 2) -> bool:
        """Check if VNC server port is reachable."""
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (OSError, socket.timeout) as e:
            log.debug("VNC port %d on %s not reachable: %s", port, ip, e)
            return False

    # ----------------------------------------------
    # OPEN TIGERVNC IN FULL SCREEN
    # ----------------------------------------------
    def open_tigervnc_fullscreen(self, vm_ip: str) -> Optional[subprocess.Popen]:
        """
        Opens TigerVNC viewer in fullscreen mode without PyAutoGUI.
        Retries 3 times if connection fails.
        Returns Popen process if successful, else None.
        """

        retries = 3
        delay = 5  # seconds

        # If port is standard 5900 for :0, adjust if needed
        vnc_port = 5900  # default port, can modify to 5901, 5902 etc.
        display_ip = vm_ip

        for attempt in range(1, retries + 1):
            print(f"Attempt {attempt}/{retries}: Checking VNC port {vnc_port} for {vm_ip}")

            if not self.is_vnc_port_open(vm_ip, vnc_port):
                print(f"VNC port {vnc_port} not open. Retrying in {delay}s...")
                time.sleep(delay)
                continue

            print(f"VNC port {vnc_port} is open. Launching TigerVNC...")

            # Launch TigerVNC with safe flags
            process = subprocess.Popen(
                [
                    TIGERVNC_PATH,
                    "-Shared",          # allows multiple sessions
                    "-FullScreen",      # fullscreen
                    display_ip
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait a bit to see if process stays alive
            time.sleep(5)

            if process.poll() is None:
                print("TigerVNC opened successfully in fullscreen")
                return process

            print(f"Failed to open TigerVNC. Retrying in {delay}s...")
            time.sleep(delay)

        log.error("Failed to open TigerVNC after %d retries for %s", retries, vm_ip)
        return None

    



    # ----------------------------------------------
    # CLOSE TIGERVNC
    # ----------------------------------------------
    def close_tigervnc(self,process: subprocess.Popen | None = None):
        """
        Closes TigerVNC viewer.
        Uses process handle if provided, otherwise kills by process name.
        """
        if process and process.poll() is None:
            process.terminate()
            print("TigerVNC closed using process handle")
        else:
            # Fallback: kill by name
            subprocess.run(
                ["taskkill", "/F", "/IM", PROCESS_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("TigerVNC closed using taskkill")