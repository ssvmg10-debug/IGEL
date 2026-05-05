###########################################################
# Title        : IGEL setup.ini Configuration Utilities
# Description  : Helper functions to read, back up, and
#                modify the IGEL /wfs/setup.ini file via
#                SSH, including adding update repositories
#                and browser session definitions used in
#                automated device provisioning workflows.
#
# Prerequisites:
#   - Python 3.10+
#   - SSH client with remote command execution capability
#   - Access to IGEL /wfs filesystem
#   - Sufficient permissions to modify setup.ini
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.1
############################################################


SETUP_INI = "/wfs/setup.ini"
SETUP_BAK = "/wfs/setup.ini.bak"


def read_setup(ssh):
    _, out, _ = ssh.run_command(f"cat {SETUP_INI}")
    return out


def write_setup(ssh, content: str):
    ssh.run_command(f"cp {SETUP_INI} {SETUP_BAK}")
    ssh.run_command(f"printf '%s' '{content}' > {SETUP_INI}")


def add_qa_repo(content: str, uuid: str, url: str) -> str:
    if url in content:
        return content

    return content + f"""
<update>
 <repository%></repository%>
 <repository${uuid}>
  uuid=<{uuid}>
  url=<{url}>
 </repository${uuid}>
</update>"""


def add_browser_session(content: str, name: str, uuid: str) -> str:
    if f"<{name}${uuid}>" in content:
        return content

    return content + f"""
<app>
 <{name}>
  <sessions>
   <{name}%></{name}%>
   <{name}${uuid}>
    uuid=<{uuid}>
    name=<{name}>
   </{name}${uuid}>
  </sessions>
 </{name}>
</app>"""




import yaml
from pathlib import Path


class OBSSetupManager:
    """
    Full IGEL setup.ini automation workflow
    Handles:
    - terminal open
    - root login
    - setup.ini modification
    - reboot
    """

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, page):
        self.page = page
        self.config = self._load_config()

    # ==========================================================
    # CONFIG
    # ==========================================================

    def _load_config(self):
        config_path = Path(__file__).resolve().parents[2] / "config" / "tc_qcl_data.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    def get_vmware_config(self):
        return self.config["vmware"]

    def get_setup_ini_path(self):
        return self.config["paths"]["setup_ini"]

    # ==========================================================
    # VM CONSOLE
    # ==========================================================

    def focus_console(self):
        self.page.bring_to_front()
        vp = self.page.viewport_size
        if vp:
            self.page.mouse.click(vp["width"] // 2, vp["height"] // 2)
        else:
            self.page.mouse.click(960, 540)
        self.page.wait_for_timeout(500)

    def open_terminal(self):
        for _ in range(3):
            self.page.keyboard.press("Control+Alt+F12")
            self.page.wait_for_timeout(500)

    # ==========================================================
    # GERMAN KEYBOARD TYPING
    # ==========================================================

    def _type_german(self, text):
        for char in text:
            if char == "<":
                self.page.keyboard.press("Shift+Comma")
            elif char == ">":
                self.page.keyboard.press("Shift+Period")
            elif char == ":":
                self.page.keyboard.press("Shift+Semicolon")
            elif char == "_":
                self.page.keyboard.press("Shift+Minus")
            elif char == "\n":
                self.page.keyboard.press("Enter")
            else:
                self.page.keyboard.press(char)

            self.page.wait_for_timeout(50)

    # ==========================================================
    # TERMINAL COMMAND
    # ==========================================================

    def run(self, command, wait=2000):
        self.page.keyboard.press("Control+u")
        self._type_german(command)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(wait)

    # ==========================================================
    # ROOT LOGIN
    # ==========================================================

    def login_root(self):
        self.focus_console()
        self.page.keyboard.type("root")
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(1000)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(1000)

    # ==========================================================
    # SETUP.INI UPDATE
    # ==========================================================

    def update_setup_ini(self):
        setup_path = self.get_setup_ini_path()

        print("Backing up setup.ini...")
        self.run(f"cp {setup_path} {setup_path}.bkp")

        print("Appending XML...")

        xml_lines = [
            "<setup-assistant>\n"
            "obs_endpoint=<https://obs-qas-stable.services.igel.com>\n"
            "</setup-assistant>\n"
        ]

        for line in xml_lines:
            self.page.keyboard.press("Control+u")
            self.page.keyboard.type("printf '")
            self._type_german(line)
            self.page.keyboard.type("' ")

            # >>
            self.page.keyboard.press("Shift+Period")
            self.page.keyboard.press("Shift+Period")

            self.page.keyboard.type(f"{setup_path}.bkp")
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(1000)

        print("Restoring modified file...")
        self.run(f"cp {setup_path}.bkp {setup_path}")

        print("Verifying...")
        self.run(f"cat {setup_path}", wait=2000)

        print("Rebooting...")
        self.run("reboot")

    # ==========================================================
    # FULL WORKFLOW
    # ==========================================================

    def apply_obs_configuration(self):
        """
        One-call full execution
        """
        self.focus_console()
        self.open_terminal()
        self.login_root()
        self.update_setup_ini()