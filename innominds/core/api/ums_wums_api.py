# ###########################################################
# # Title        : UMS & WUMS Unified API Client
# # Description  : Reusable Python API layer that integrates
# #                UMS and WUMS endpoints to manage
# #                authentication, directories, devices,
# #                profiles, applications, versions, and
# #                device commands (scan, register, reboot,
# #                SSH/VNC enablement).
# #
# # Prerequisites:
# #   - Valid UMS credentials
# #   - Valid WUMS bearer token
# #
# # Author       : Sai Arokala
# # Email        : Sai.Arakala_ext@igel.com
# # Created On   : Dec-2025
# # Version      : 1.1
# ############################################################
#
#
# import base64
# import time
# from core.api.api_client import APIClient
# from core.utils.logger import get_logger
# from core.api.auth_token import initial_auth, refresh_ums_auth
#
# log = get_logger(__name__)
#
#
# class UMSWUMSApi:
#     """
#     Single reusable API layer for:
#     - UMS (device, directories, login)
#     - WUMS (apps, profiles, versions)
#     """
#
#     def __init__(self, base_url: str):
#         self.api = APIClient(base_url)
#         self.session_id: str | None = None
#         self.bearer: str | None = None
#
#     # ==========================================================
#     # AUTH
#     # ==========================================================
#     def login_ums_api(self, username: str, password: str) -> str:
#         log.info("[API] Logging into UMS API")
#
#         creds = base64.b64encode(
#             f"{username}:{password}".encode()
#         ).decode()
#
#         resp = self.api.post(
#             "/umsapi/v3/login",
#             headers={"Authorization": f"Basic {creds}"}
#         )
#
#         assert resp.status_code == 200, "UMS API login failed"
#         self.session_id = resp.cookies.get("JSESSIONID")
#
#         if not self.session_id:
#             log.warning("[API] No JSESSIONID received, assuming existing session")
#         else:
#             log.info("[API] JSESSIONID received")
#
#         log.info("[API] UMS API login successful")
#         return self.session_id
#
#     def set_bearer(self, bearer: str):
#         self.bearer = bearer
#         log.info("[API] Bearer token set")
#
#     # ==========================================================
#     # DIRECTORIES
#     # ==========================================================
#     def get_directory_id(self, directory_name: str) -> int:
#         log.info(f"[API] Resolving directory: {directory_name}")
#
#         resp = self.api.get(
#             "/umsapi/v3/directories/tcdirectories",
#             cookies={"JSESSIONID": self.session_id}
#         )
#
#         for d in resp.json():
#             if d["name"] == directory_name:
#                 log.info(f"[API] Directory resolved: {d['id']}")
#                 return d["id"]
#
#         raise AssertionError(f"Directory not found: {directory_name}")
#
#     # ==========================================================
#     # DEVICE
#     # ==========================================================
#     def scan_devices(self):
#         log.info("[API] Triggering device scan")
#
#         resp = self.api.post(
#             "/wums-app/device-command/scanfordevices",
#             headers={"Authorization": self.bearer},
#             json={"useTcpScan": False}
#         )
#
#         assert resp.status_code in (200, 202)
#         return resp.json()
#
#     def register_device(self, directory_id: int, mac: str, ip: str):
#         log.info(f"[API] Registering device MAC={mac}, IP={ip}")
#
#         resp = self.api.post(
#             "/wums-app/device-command/registerdevices",
#             headers={"Authorization": self.bearer},
#             json={
#                 "targetdir": directory_id,
#                 "devices": {mac: ip}
#             }
#         )
#
#         assert resp.status_code in (200, 202)
#
#     def get_device_id(self, device_name: str) -> int:
#         log.info(f"[API] Resolving device ID for {device_name}")
#
#         resp = self.api.get(
#             "/umsapi/v3/thinclients",
#             cookies={"JSESSIONID": self.session_id}
#         )
#
#         data = resp.json()
#
#         #  Normalize response
#         if isinstance(data, dict):
#             # Some UMS versions wrap devices
#             devices = data.get("items") or data.get("data") or []
#         elif isinstance(data, list):
#             devices = data
#         else:
#             raise RuntimeError(
#                 f"Unexpected thinclients response type: {type(data)}"
#             )
#
#         log.info(f"[API] {len(devices)} devices returned from UMS")
#
#         for d in devices:
#             if not isinstance(d, dict):
#                 continue
#
#             name = d.get("name")
#             did = d.get("id")
#
#             log.debug(f"[API] Found device name={name}, id={did}")
#
#             if name == device_name:
#                 log.info(f"[API] Device ID resolved: {did}")
#                 return did
#
#         raise RuntimeError(
#             f"Device '{device_name}' not found in UMS thinclients list"
#         )
#
#     def enable_ssh_vnc(self, device_id: int):
#         log.info("[API] Enabling SSH + VNC + Shadow")
#
#         payload = {
#             "id": {"id": device_id, "type": "DEVICE"},
#             "data": (
#                 "{\"network.ssh_server.enabled\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
#                 "\"network.ssh_server.permit_empty_passwords\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
#                 "\"network.ssh_server.permit_root_login\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
#                 "\"network.vncserver.enabled\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
#                 "\"network.vncserver.secure_mode\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
#                 "\"network.vncserver.promptuser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
#                 "\"network.vncserver.showdisconnectbtn\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
#                 "\"userinterface.vncserver.indicatorposition\":{\"uiType\":\"string\",\"value\":\"top-right\","
#                 "\"type\":2},"
#                 "\"update.auto_reboot_timeout\":{\"uiType\":\"integer\",\"value\":240,\"type\":2}}"
#             ),
#             "language": "en",
#             "sendSettingsNow": True
#         }
#
#         resp = self.api.post(
#             "/wums-app/device-detail/updateDeviceConfiguration",
#             headers={"Authorization": self.bearer},
#             json=payload
#         )
#
#         assert resp.status_code in (200, 202)
#
#     def reboot_device(self, device_id: int):
#         log.info("[API] Sending reboot command")
#
#         resp = self.api.post(
#             "/wums-app/device-command/execute",
#             headers={"Authorization": self.bearer},
#             json={
#                 "command": {"name": "REBOOT", "commandParams": {}},
#                 "deviceId": device_id
#             }
#         )
#
#         assert resp.status_code in (200, 202)
#
#     # ==========================================================
#     # PROFILE
#     # ==========================================================
#     def create_profile(self, name, description, directory_id, apps):
#         log.info(f"[API] Creating profile {name}")
#
#         resp = self.api.post(
#             "/wums-app/configuration/createConfiguration",
#             headers={"Authorization": self.bearer},
#             json={
#                 "name": name,
#                 "description": description,
#                 "directoryId": directory_id,
#                 "masterProfile": False,
#                 "appLineVersionList": apps
#             }
#         )
#
#         assert resp.status_code == 200, (
#             f"Profile creation failed: {resp.status_code} {resp.text}"
#         )
#
#         data = resp.json()
#
#         if isinstance(data, int):
#             return {"id": data}
#
#         if "id" in data:
#             return data
#
#         raise Exception(f"Unexpected create_profile response: {data}")
#
#     def assign_profile(self, device_id: int, profile_id: int):
#         log.info(f"[API] Assigning profile {profile_id}")
#
#         self.assign_object(device_id, profile_id, "PROFILE", False)
#
#     # ==========================================================
#     # VERSION MANAGEMENT
#     # ==========================================================
#     def set_template_version(
#             self,
#             app_id: int,
#             version_id: int,
#             profile_fixed_version_label: str,
#             name: str,
#             return_status: bool = False
#     ):
#         log.info(
#             f"[API] Setting template version "
#             f"{profile_fixed_version_label} for app {name}"
#         )
#
#         resp = self.api.patch(
#             f"/wums-app/installedapp/{app_id}/set-template-version",
#             headers={
#                 "Authorization": self.bearer,
#                 "Content-Type": "application/json"
#             },
#             json={
#                 "versionId": version_id,
#                 "updateTime": "NOW"
#             }
#         )
#
#         # --------------------------------------------------
#         # If caller wants raw status (Step 18 case)
#         # --------------------------------------------------
#         if return_status:
#             return resp.status_code, resp.text
#
#         # --------------------------------------------------
#         # Default behaviour (backward compatible)
#         # --------------------------------------------------
#         assert resp.status_code in (200, 204), (
#             f"Failed to set template version for {name}. "
#             f"Status: {resp.status_code}, Response: {resp.text}"
#         )
#
#     # ==========================================================
#     # INTERNAL
#     # ==========================================================
#     def assign_object(self, device_id, object_id, object_type, unassign):
#         payload = {
#             "assignOrUnassignObjects": [
#                 {
#                     "objectId": object_id,
#                     "objectType": object_type,
#                     "unassign": unassign
#                 }
#             ],
#             "deviceId": device_id,
#             "updateTime": "NOW"
#         }
#
#         resp = self.api.post(
#             "/wums-app/device-profile/assignOrUnassignObjectToDevice",
#             headers={"Authorization": self.bearer},
#             json=payload
#         )
#         if resp.status_code not in (200, 202):
#             log.error(f"[API] assign_object FAILED")
#             log.error(f"[API] Status: {resp.status_code}")
#             log.error(f"[API] Body: {resp.text}")
#             log.error(f"[API] Payload: {payload}")
#
#         assert resp.status_code in (200, 202), (
#             f"assign_object failed | status={resp.status_code} | body={resp.text}"
#         )
#         return resp
#
#     def assign_app(self, device_id: int, app_id: int):
#         log.info(f"[API] Assigning app {app_id}")
#
#         self.assign_object(device_id, app_id, "INSTALLED_APP", False)
#
#     def unassign_object(
#             self,
#             device_id,
#             object_id,
#             object_type,
#             unassign=True,
#             *,
#             return_status=False
#     ):
#         payload = {
#             "assignOrUnassignObjects": [
#                 {
#                     "objectId": object_id,
#                     "objectType": object_type,
#                     "unassign": unassign
#                 }
#             ],
#             "deviceId": device_id,
#             "updateTime": "NOW"
#         }
#
#         resp = self.api.post(
#             "/wums-app/device-profile/assignOrUnassignObjectToDevice",
#             headers={"Authorization": self.bearer},
#             json=payload
#         )
#
#         # -------------------------------
#         # SOFT MODE (Step 18 safe)
#         # -------------------------------
#         if return_status:
#             return resp.status_code, resp.text
#
#         # -------------------------------
#         # HARD MODE
#         # -------------------------------
#         assert resp.status_code in (200, 202), (
#             f"Unassign failed: {resp.status_code} {resp.text}"
#         )
#
#     # ==========================================================
#     # PROFILE DIRECTORY
#     # ==========================================================
#     def create_profile_directory(
#             self,
#             parent_directory_id: int,
#             directory_name: str
#     ) -> int:
#         """
#         Create a PROFILE directory under given parent directory.
#         Returns created directory ID.
#         """
#         log.info(
#             f"[API] Creating profile directory '{directory_name}' "
#             f"under parent {parent_directory_id}"
#         )
#
#         payload = {
#             "id": None,
#             "objectType": "DIRECTORY_REGULAR_PROFILE",
#             "parentId": {
#                 "type": "DIRECTORY_REGULAR_PROFILE",
#                 "id": parent_directory_id
#             },
#             "values": [
#                 {
#                     "valueClass": "STRING",
#                     "id": "NAME",
#                     "stringValue": directory_name
#                 }
#             ]
#         }
#
#         resp = self.api.post(
#             "/wums-app/configuration/createOrRenameDirectory",
#             headers={"Authorization": self.bearer},
#             json=payload
#         )
#
#         assert resp.status_code == 200, (
#             f"Directory creation failed: {resp.status_code} {resp.text}"
#         )
#
#         directory_id = resp.json()["id"]["id"]
#         log.info(f"[API] Profile directory created with ID {directory_id}")
#
#         return directory_id
#
#     # ==========================================================
#     # PROFILE DIRECTORY TREE
#     # ==========================================================
#     def get_profile_directory_tree(self):
#         """
#         Get full PROFILE directory tree.
#         """
#         log.info("[API] Fetching profile directory tree")
#
#         resp = self.api.get(
#             "/wums-app/configuration/rootDirectoryTree/DIRECTORY_REGULAR_PROFILE",
#             headers={"Authorization": self.bearer}
#         )
#
#         assert resp.status_code == 200, (
#             f"Failed to get directory tree: {resp.status_code} {resp.text}"
#         )
#
#         return resp.json()
#
#     # TO Check assigned profiles for perticular device.
#     def get_direct_assigned_objects(self, device_id):
#         resp = self.api.get(
#             f"/wums-app/device-profile/directAssignedObjectsByDeviceId/{device_id}",
#             headers={"Authorization": self.bearer}
#         )
#
#         assert resp.status_code == 200, (
#             f"Failed to fetch assigned objects for device {device_id}: "
#             f"{resp.status_code} {resp.text}"
#         )
#
#         return resp.json()
#
#     # TO reset the device form UMS:
#
#     def reset_device_to_factory(self, device_id: int):
#         """
#         Executes RESET_TO_FACTORY_DEFAULTS on the given device.
#         This will wipe the device and unregister it from UMS.
#         """
#
#         payload = {
#             "command": {
#                 "commandParams": {},
#                 "name": "RESET_TO_FACTORY_DEFAULTS",
#                 "genericCommandId": None
#             },
#             "deviceId": device_id
#         }
#
#         resp = self.api.post(
#             "/wums-app/device-command/execute",
#             headers={"Authorization": self.bearer},
#             json=payload
#         )
#
#         assert resp.status_code in (200, 202), (
#             f"Factory reset failed: {resp.status_code} {resp.text}"
#         )
#
#     # ==========================================================
#     # DEVICE CHECK HELPER (Reusable)
#     # ==========================================================
#     def cleanup_device_if_exists(
#             self,
#             device_name,
#             page=None,
#             ums_cfg=None,
#             CFG=None
#     ):
#         """
#         Checks whether the device already exists in UMS.
#         If yes → performs factory reset and waits until it is removed.
#
#         Parameters:
#             device_name (str) : Device name to check
#             page              : Playwright page (optional, for auth refresh)
#             ums_cfg           : UMS config (optional)
#             CFG               : Full config (optional)
#         """
#
#         log.info("[DEVICE CHECK] Looking for existing device in UMS")
#
#         try:
#             device_id = self.get_device_id(device_name)
#             log.warning(
#                 f"[DEVICE CHECK] Device '{device_name}' exists (ID: {device_id})"
#             )
#         except Exception:
#             log.info("[DEVICE CHECK] Device not found. Proceeding normally.")
#             return  # Device not present → nothing to do
#
#         # --------------------------------------------------
#         # Device exists → Reset to factory defaults
#         # --------------------------------------------------
#         try:
#             log.info("[DEVICE CHECK] Sending RESET_TO_FACTORY_DEFAULTS command")
#             self.reset_device_to_factory(device_id)
#
#         except Exception as e:
#             if "403" in str(e) and page and ums_cfg and CFG:
#                 log.warning("[DEVICE CHECK] 403 detected, refreshing auth")
#                 refresh_ums_auth(self, page, ums_cfg, CFG)
#                 self.reset_device_to_factory(device_id)
#             else:
#                 raise
#
#         # --------------------------------------------------
#         # Wait for reset to complete
#         # --------------------------------------------------
#         RESET_WAIT = 120
#         log.info(f"[DEVICE CHECK] Waiting {RESET_WAIT}s for device reset")
#         time.sleep(RESET_WAIT)
#
#         # --------------------------------------------------
#         # Confirm device removed from UMS
#         # --------------------------------------------------
#         log.info("[DEVICE CHECK] Verifying device removal from UMS")
#
#         for attempt in range(1, 7):
#             try:
#                 self.get_device_id(device_name)
#                 log.warning(
#                     f"[DEVICE CHECK] Device still present (attempt {attempt}/6). Waiting..."
#                 )
#                 time.sleep(20)
#             except Exception:
#                 log.info("[DEVICE CHECK] Device successfully cleaned.")
#                 return
#
#         raise AssertionError(
#             "[DEVICE CHECK] Device still exists after factory reset timeout"
#         )


###########################################################
# Title        : UMS & WUMS Unified API Client
# Description  : Reusable Python API layer that integrates
#                UMS and WUMS endpoints to manage
#                authentication, directories, devices,
#                profiles, applications, versions, and
#                device commands (scan, register, reboot,
#                SSH/VNC enablement).
#
# Prerequisites:
#   - Valid UMS credentials
#   - Valid WUMS bearer token
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Dec-2025
# Version      : 1.1
############################################################


import base64
import json
import time
from core.api.api_client import APIClient
from core.utils.logger import get_logger
from core.api.auth_token import initial_auth, refresh_ums_auth
from core.ssh.my_logger import logger
import requests

log = get_logger(__name__)


class UMSWUMSApi:
    """
    Single reusable API layer for:
    - UMS (device, directories, login)
    - WUMS (apps, profiles, versions)
    """

    def __init__(self, base_url: str):
        self.api = APIClient(base_url)
        self.session_id: str | None = None
        self.bearer: str | None = None

    # ==========================================================
    # AUTH
    # ==========================================================
    def login_ums_api(self, username: str, password: str) -> str:
        log.info("[API] Logging into UMS API")

        creds = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()

        resp = self.api.post(
            "/umsapi/v3/login",
            headers={"Authorization": f"Basic {creds}"}
        )

        assert resp.status_code == 200, "UMS API login failed"
        self.session_id = resp.cookies.get("JSESSIONID")

        if not self.session_id:
            log.warning("[API] No JSESSIONID received, assuming existing session")
        else:
            log.info("[API] JSESSIONID received")

        log.info("[API] UMS API login successful")
        return self.session_id

    def set_bearer(self, bearer: str):
        self.bearer = bearer
        log.info("[API] Bearer token set")

    # ==========================================================
    # DIRECTORIES
    # ==========================================================
    def get_directory_id(self, directory_name: str) -> int:
        log.info(f"[API] Resolving directory: {directory_name}")

        resp = self.api.get(
            "/umsapi/v3/directories/tcdirectories",
            cookies={"JSESSIONID": self.session_id}
        )

        for d in resp.json():
            if d["name"] == directory_name:
                log.info(f"[API] Directory resolved: {d['id']}")
                return d["id"]

        raise AssertionError(f"Directory not found: {directory_name}")

    # ==========================================================
    # DEVICE
    # ==========================================================
    def scan_devices(self):
        log.info("[API] Triggering device scan")

        resp = self.api.post(
            "/wums-app/device-command/scanfordevices",
            headers={"Authorization": self.bearer},
            json={"useTcpScan": False}
        )
        assert resp.status_code in (200, 202)
        return resp.json()

    def register_device(self, directory_id: int, mac: str, ip: str):
        log.info(f"[API] Registering device MAC={mac}, IP={ip}")

        resp = self.api.post(
            "/wums-app/device-command/registerdevices",
            headers={"Authorization": self.bearer},
            json={
                "targetdir": directory_id,
                "devices": {mac: ip}
            }
        )
        assert resp.status_code in (200, 202)

    def get_device_id(self, device_name: str) -> int:
        log.info(f"[API] Resolving device ID for {device_name}")

        resp = self.api.get(
            "/umsapi/v3/thinclients",
            cookies={"JSESSIONID": self.session_id}
        )

        data = resp.json()

        #  Normalize response
        if isinstance(data, dict):
            # Some UMS versions wrap devices
            devices = data.get("items") or data.get("data") or []
        elif isinstance(data, list):
            devices = data
        else:
            raise RuntimeError(
                f"Unexpected thinclients response type: {type(data)}"
            )

        log.info(f"[API] {len(devices)} devices returned from UMS")

        for d in devices:
            if not isinstance(d, dict):
                continue

            name = d.get("name")
            did = d.get("id")

            log.debug(f"[API] Found device name={name}, id={did}")

            if name == device_name:
                log.info(f"[API] Device ID resolved: {did}")
                return did

        raise RuntimeError(
            f"Device '{device_name}' not found in UMS thinclients list"
        )

    def enable_ssh_vnc(self, device_id: int):
        log.info("[API] Enabling SSH + VNC + Shadow")

        payload = {
            "id": {"id": device_id, "type": "DEVICE"},
            "data": (
                "{\"network.ssh_server.enabled\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
                "\"network.ssh_server.permit_empty_passwords\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
                "\"network.ssh_server.permit_root_login\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
                "\"network.vncserver.enabled\":{\"uiType\":\"bool\",\"value\":true,\"type\":2},"
                "\"network.vncserver.secure_mode\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
                "\"network.vncserver.promptuser\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
                "\"network.vncserver.showdisconnectbtn\":{\"uiType\":\"bool\",\"value\":false,\"type\":2},"
                "\"userinterface.vncserver.indicatorposition\":{\"uiType\":\"string\",\"value\":\"top-right\","
                "\"type\":2},"
                "\"update.auto_reboot_timeout\":{\"uiType\":\"integer\",\"value\":240,\"type\":2}}"
            ),
            "language": "en",
            "sendSettingsNow": True
        }

        resp = self.api.post(
            "/wums-app/device-detail/updateDeviceConfiguration",
            headers={"Authorization": self.bearer},
            json=payload
        )

        assert resp.status_code in (200, 202)

    def reboot_device(self, device_id: int):
        log.info("[API] Sending reboot command")

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer},
            json={
                "command": {"name": "REBOOT", "commandParams": {}},
                "deviceId": device_id
            }
        )

        assert resp.status_code in (200, 202)

    def shutdown_device(self, device_id: int):
        log.info("[API] Sending shutdown command")

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer},
            json={
                "command": {"name": "SHUTDOWN", "commandParams": {}},
                "deviceId": device_id
            }
        )

        assert resp.status_code in (200, 202)

    def wake_up_device(self, device_id: int):
        log.info("[API] Sending wake-up command")

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer},
            json={
                "command": {"name": "WAKEUP", "commandParams": {}},
                "deviceId": device_id
            }
        )

        assert resp.status_code in (200, 202)

    # ==========================================================
    # PROFILE
    # ==========================================================
    def create_profile(self, name, description, directory_id, apps):
        log.info(f"[API] Creating profile {name}")

        resp = self.api.post(
            "/wums-app/configuration/createConfiguration",
            headers={"Authorization": self.bearer},
            json={
                "name": name,
                "description": description,
                "directoryId": directory_id,
                "masterProfile": False,
                "appLineVersionList": apps
            }
        )

        assert resp.status_code == 200, (
            f"Profile creation failed: {resp.status_code} {resp.text}"
        )

        data = resp.json()

        if isinstance(data, int):
            return {"id": data}

        if "id" in data:
            return data

        raise Exception(f"Unexpected create_profile response: {data}")

    def assign_profile(self, device_id: int, profile_id: int):
        log.info(f"[API] Assigning profile {profile_id}")

        self.assign_object(device_id, profile_id, "PROFILE", False)

    def detach_profile(self, device_id: int, profile_id: int):
        log.info(f"[API] Detaching profile {profile_id}")

        self.assign_object(device_id, profile_id, "PROFILE", True)

    # ==========================================================
    # VERSION MANAGEMENT
    # ==========================================================
    def set_template_version(
            self,
            app_id: int,
            version_id: int,
            profile_fixed_version_label: str,
            name: str,
            return_status: bool = False
    ):
        log.info(
            f"[API] Setting template version "
            f"{profile_fixed_version_label} for app {name}"
        )

        resp = self.api.patch(
            f"/wums-app/installedapp/{app_id}/set-template-version",
            headers={
                "Authorization": self.bearer,
                "Content-Type": "application/json"
            },
            json={
                "versionId": version_id,
                "updateTime": "NOW"
            }
        )

        # --------------------------------------------------
        # If caller wants raw status (Step 18 case)
        # --------------------------------------------------
        if return_status:
            return resp.status_code, resp.text

        # --------------------------------------------------
        # Default behaviour (backward compatible)
        # --------------------------------------------------
        assert resp.status_code in (200, 204), (
            f"Failed to set template version for {name}. "
            f"Status: {resp.status_code}, Response: {resp.text}"
        )

    # ==========================================================
    # INTERNAL
    # ==========================================================
    def assign_object(self, device_id, object_id, object_type, unassign):
        payload = {
            "assignOrUnassignObjects": [
                {
                    "objectId": (object_id),
                    "objectType": object_type,
                    "unassign": unassign
                }
            ],
            "deviceId": device_id,
            "updateTime": "NOW"
        }

        resp = self.api.post(
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            headers={"Authorization": self.bearer},
            json=payload
        )
        if resp.status_code not in (200, 202):
            log.error(f"[API] assign_object FAILED")
            log.error(f"[API] Status: {resp.status_code}")
            log.error(f"[API] Body: {resp.text}")
            log.error(f"[API] Payload: {payload}")

        assert resp.status_code in (200, 202), (
            f"assign_object failed | status={resp.status_code} | body={resp.text}"
        )
        return resp

    def assign_app(self, device_id: int, app_id: int):
        log.info(f"[API] Assigning app {app_id}")

        self.assign_object(device_id, app_id, "INSTALLED_APP", False)

    def remove_app(self, device_id: int, app_id: int):
        log.info(f"[API] Removing app {app_id}")

        self.assign_object(device_id, app_id, "INSTALLED_APP", True)

    def unassign_object(
            self,
            device_id,
            object_id,
            object_type,
            unassign=True,
            *,
            return_status=False
    ):
        payload = {
            "assignOrUnassignObjects": [
                {
                    "objectId": object_id,
                    "objectType": object_type,
                    "unassign": unassign
                }
            ],
            "deviceId": device_id,
            "updateTime": "NOW"
        }

        resp = self.api.post(
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            headers={"Authorization": self.bearer},
            json=payload
        )

        # -------------------------------
        # SOFT MODE (Step 18 safe)
        # -------------------------------
        if return_status:
            return resp.status_code, resp.text

        # -------------------------------
        # HARD MODE
        # -------------------------------
        assert resp.status_code in (200, 202), (
            f"Unassign failed: {resp.status_code} {resp.text}"
        )

    # ==========================================================
    # PROFILE DIRECTORY
    # ==========================================================
    def create_profile_directory(
            self,
            parent_directory_id: int,
            directory_name: str
    ) -> int:
        """
        Create a PROFILE directory under given parent directory.
        Returns created directory ID.
        """
        log.info(
            f"[API] Creating profile directory '{directory_name}' "
            f"under parent {parent_directory_id}"
        )

        payload = {
            "id": None,
            "objectType": "DIRECTORY_REGULAR_PROFILE",
            "parentId": {
                "type": "DIRECTORY_REGULAR_PROFILE",
                "id": parent_directory_id
            },
            "values": [
                {
                    "valueClass": "STRING",
                    "id": "NAME",
                    "stringValue": directory_name
                }
            ]
        }

        resp = self.api.post(
            "/wums-app/configuration/createOrRenameDirectory",
            headers={"Authorization": self.bearer},
            json=payload
        )

        assert resp.status_code == 200, (
            f"Directory creation failed: {resp.status_code} {resp.text}"
        )

        directory_id = resp.json()["id"]["id"]
        log.info(f"[API] Profile directory created with ID {directory_id}")

        return directory_id

    # ==========================================================
    # PROFILE DIRECTORY TREE
    # ==========================================================
    def get_profile_directory_tree(self):
        """
        Get full PROFILE directory tree.
        """
        log.info("[API] Fetching profile directory tree")

        resp = self.api.get(
            "/wums-app/configuration/rootDirectoryTree/DIRECTORY_REGULAR_PROFILE",
            headers={"Authorization": self.bearer}
        )

        assert resp.status_code == 200, (
            f"Failed to get directory tree: {resp.status_code} {resp.text}"
        )

        return resp.json()

    # TO Check assigned profiles for perticular device.
    def get_direct_assigned_objects(self, device_id):
        resp = self.api.get(
            f"/wums-app/device-profile/directAssignedObjectsByDeviceId/{device_id}",
            headers={"Authorization": self.bearer}
        )

        assert resp.status_code == 200, (
            f"Failed to fetch assigned objects for device {device_id}: "
            f"{resp.status_code} {resp.text}"
        )

        return resp.json()

    # TO reset the device form UMS:

    def reset_device_to_factory(self, device_id: int):
        """
        Executes RESET_TO_FACTORY_DEFAULTS on the given device.
        This will wipe the device and unregister it from UMS.
        """

        payload = {
            "command": {
                "commandParams": {},
                "name": "RESET_TO_FACTORY_DEFAULTS",
                "genericCommandId": None
            },
            "deviceId": device_id
        }

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer},
            json=payload
        )

        assert resp.status_code in (200, 202), (
            f"Factory reset failed: {resp.status_code} {resp.text}"
        )
# POOJA
#=======================================================================
    # ==========================================================
    # CERTIFICATE / FILE
    # ==========================================================

    def get_file_details(self, file_name):
        log.info(f"[API] Fetching file ID for: {file_name}")

        request_body = {
            "filterTerm": "",
            "pageInfo": {
                "pageNumber": 1,
                "pageSize": 100,
                "totalPages": 1,
                "totalRecords": 0,
                "pageFirstRecordNumber": 1,
                "pageRecords": 0
            },
            "sortInfo": {
                "sortProperties": [
                    {
                        "name": "name",
                        "order": "ASCENDING"
                    }
                ]
            },
            "id": -7
        }

        resp = self.api.post(
            "/wums-app/files/list",
            headers={
                "Authorization": self.bearer,
                "Content-Type": "application/json"
            },
            json=request_body
        )

        assert resp.status_code == 200, \
            f"Failed to get file list. Status: {resp.status_code}, Response: {resp.text}"

        data = resp.json()

        # Find file ID
        for record in data.get("records", []):
            ums_obj = record.get("umsObject", {})
            name = ums_obj.get("fileName")

            if name and name.lower() == file_name.lower():
                return ums_obj.get("typedId", {}).get("id")

        # If not found
        raise Exception(f"File '{file_name}' not found in WUMS")

    def assign_files(self, device_id: int, file_id: int):
        log.info(f"[API] Assigning file {file_id}")

        self.assign_object(device_id, file_id, "URL_FILE", False)

    def remove_files(self, device_id: int, file_id: int):
        log.info(f"[API] Removing file {file_id}")

        self.assign_object(device_id, file_id, "URL_FILE", True)

    # ==========================================================
    # Applicatinon details
    # ==========================================================

    def get_installed_app_id(self, app_name):
        log.info(f"[API] Fetching Installed App ID for: {app_name}")

        payload = {
            "categoryId": -101,
            "pageInfo": {"pageNumber": 1, "pageSize": 100, "totalPages": 1, "totalRecords": 0,
                         "pageFirstRecordNumber": 1, "pageRecords": 100},
            "sortInfo": {"sortProperties": []},
            "filterTerm": ""
        }

        resp = self.api.post(
            "/wums-app/installedapp/filter-in-directory",
            headers={"Authorization": self.bearer, "Content-Type": "application/json"},
            json=payload
        )

        assert resp.status_code == 200, \
            f"Failed to get installed app list. Status: {resp.status_code}, Response: {resp.text}"

        data = resp.json()

        for record in data.get("pageResponse", {}).get("records", []):
            ums_obj = record.get("umsObject", {})
            name = ums_obj.get("name", {}).get("value")
            # print("DEBUG NAME:", name)

            if name and name.lower() == app_name.lower():
                return ums_obj.get("typedId", {}).get("id")

        raise Exception(f"Installed App '{app_name}' not found in directory")

    def create_citrix_session(self, device_id, username, password, store_url="https://qa-2203.qa.test", send_now=True):
        """
        Update the device configuration in WUMS for Citrix/CWA sessions.

        Args:
            device_id (int): WUMS device ID
            username (str): Citrix/Storefront username
            password (str): Citrix/Storefront password
            store_url (str): Storefront URL
            send_now (bool): Whether to send settings immediately
        """
        log.info(f"[API] Updating device configuration for device_id={device_id}")

        payload = {
            "id": {"id": device_id, "type": "DEVICE"},
            "data": (
                "{"
                "\"app.cwa.sessions.cwa\": {"
                "\"instancesToAdd\": {"
                "\"1771490209065a2effa06-7d1b-40fd-8837-89d2bba67c27\": {"
                f"\"name\": {{\"uiType\":\"string\",\"value\":\"Citrix storefront\",\"type\":2}},"
                f"\"options.type\": {{\"uiType\":\"string\",\"value\":\"storebrowse\",\"type\":2}},"
                f"\"options.stores.url1\": {{\"uiType\":\"string\",\"value\":\"{store_url}\",\"type\":2}},"
                f"\"options.authentication.method\": {{\"uiType\":\"string\",\"value\":\"credentials\",\"type\":2}},"
                f"\"options.authentication.username\": {{\"uiType\":\"string\",\"value\":\"{username}\",\"type\":2}},"
                f"\"options.authentication.domain\": {{\"uiType\":\"string\",\"value\":\"{username.split('@')[-1]}\",\"type\":2}},"
                f"\"options.authentication.password\": {{\"uiType\":\"string\",\"value\":\"{password}\",\"type\":2}}"
                "},"
                "\"1771490319949db222680-4f91-4e2e-b8b1-6e599fcabda0\": {"
                f"\"name\": {{\"uiType\":\"string\",\"value\":\"Citrix SelfService\",\"type\":2}},"
                f"\"options.stores.url1\": {{\"uiType\":\"string\",\"value\":\"{store_url}\",\"type\":2}}"
                "}"
                "},"
                "\"instancesToRemove\": [],"
                "\"instances\": {},"
                "\"type\":1"
                "}"
                "}"
            ),
            "language": "en",
            "sendSettingsNow": send_now
        }

        resp = self.api.post(
            "/wums-app/device-detail/updateDeviceConfiguration",
            headers={"Authorization": self.bearer, "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )

        if resp.status_code != 200:
            raise Exception(f"Failed to update device configuration. Status: {resp.status_code}, Response: {resp.text}")

        log.info("[API] Device configuration updated successfully")
        return resp.json()

    def remove_citrix_session(self, device_id: int, send_now=True):
        log.info(f"[API] Removing Citrix session configuration for device_id={device_id}")

        payload = {
            "id": {"id": device_id, "type": "DEVICE"},
            "data": (
                "{"
                "\"app.cwa.sessions.cwa\": {"
                "\"instancesToAdd\": {},"
                "\"instancesToRemove\": [\"d4e7ba92-1843-4578-a9c9-d4a032266a24\",\"b6c123ad-46d9-49c8-b8b5-e24d37564a33\"],"
                "\"instances\": {},"
                "\"type\":1"
                "}"
                "}"
            ),
            "language": "en",
            "sendSettingsNow": send_now
        }

        resp = self.api.post(
            "/wums-app/device-detail/updateDeviceConfiguration",
            headers={"Authorization": self.bearer, "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )

        if resp.status_code != 200:
            raise Exception(
                f"Failed to remove Citrix session configuration. Status: {resp.status_code}, Response: {resp.text}")

        log.info("[API] Citrix session configuration removed successfully")
        return resp.json()

    def get_vm_sys_licence_info(self, device_id):

        resp = self.api.get(
            f"/wums-app/device-detail/device/{device_id}",
            headers={"Authorization": self.bearer}
        )

        assert resp.status_code == 200, (
            f"Failed to fetch assigned objects for device {device_id}: "
            f"{resp.status_code} {resp.text}"
        )

        return resp.json()

    def send_message_to_device(self, device_id, message):
        """
        Send a message to a WUMS device.

        Args:
            device_id (int): Target device ID
            message (str): Message body to send
        """
        log.info(f"[API] Sending message to device_id={device_id}")

        payload = {
            "command": {
                "name": "SEND_MESSAGE",
                "commandParams": {
                    "MESSAGE": message
                },
                "genericCommandId": None
            },
            "deviceId": device_id
        }

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer, "Content-Type": "application/json"},
            json=payload
        )

        if resp.status_code not in (200, 202):
            raise Exception(f"Failed to send message to device. Status: {resp.status_code}, Response: {resp.text}")

        log.info("[API] Message sent to device successfully")
        return resp.json()

    def reset_device_to_factory(self, device_id: int):
        """
        Executes RESET_TO_FACTORY_DEFAULTS on the given device.
        This will wipe the device and unregister it from UMS.
        """

        payload = {
            "command": {
                "commandParams": {},
                "name": "RESET_TO_FACTORY_DEFAULTS",
                "genericCommandId": None
            },
            "deviceId": device_id
        }

        resp = self.api.post(
            "/wums-app/device-command/execute",
            headers={"Authorization": self.bearer},
            json=payload
        )

        assert resp.status_code in (200, 202), (
            f"Factory reset failed: {resp.status_code} {resp.text}"
        )

    # ==========================================================
    # DEVICE CHECK HELPER (Reusable)
    # ==========================================================
    def cleanup_device_if_exists(
            self,
            device_name,
            page=None,
            ums_cfg=None,
            CFG=None
    ):
        """
        Checks whether the device already exists in UMS.
        If yes → performs factory reset and waits until it is removed.

        Parameters:
            device_name (str) : Device name to check
            page              : Playwright page (optional, for auth refresh)
            ums_cfg           : UMS config (optional)
            CFG               : Full config (optional)
        """

        log.info("[DEVICE CHECK] Looking for existing device in UMS")

        try:
            device_id = self.get_device_id(device_name)
            log.warning(
                f"[DEVICE CHECK] Device '{device_name}' exists (ID: {device_id})"
            )
        except Exception:
            log.info("[DEVICE CHECK] Device not found. Proceeding normally.")
            return  # Device not present → nothing to do

        # --------------------------------------------------
        # Device exists → Reset to factory defaults
        # --------------------------------------------------
        try:
            log.info("[DEVICE CHECK] Sending RESET_TO_FACTORY_DEFAULTS command")
            self.reset_device_to_factory(device_id)

        except Exception as e:
            if "403" in str(e) and page and ums_cfg and CFG:
                log.warning("[DEVICE CHECK] 403 detected, refreshing auth")
                refresh_ums_auth(self, page, ums_cfg, CFG)
                self.reset_device_to_factory(device_id)
            else:
                raise

        # --------------------------------------------------
        # Wait for reset to complete
        # --------------------------------------------------
        RESET_WAIT = 120
        log.info(f"[DEVICE CHECK] Waiting {RESET_WAIT}s for device reset")
        time.sleep(RESET_WAIT)

        # --------------------------------------------------
        # Confirm device removed from UMS
        # --------------------------------------------------
        log.info("[DEVICE CHECK] Verifying device removal from UMS")

        for attempt in range(1, 7):
            try:
                self.get_device_id(device_name)
                log.warning(
                    f"[DEVICE CHECK] Device still present (attempt {attempt}/6). Waiting..."
                )
                time.sleep(20)
            except Exception:
                log.info("[DEVICE CHECK] Device successfully cleaned.")
                return

        raise AssertionError(
            "[DEVICE CHECK] Device still exists after factory reset timeout"
        )
		
# """"#=======================================================================
# # POOJA
#
#
# # LG
# # ==========================================================
# # CIC FETCH (Firmware Customization)
# # ==========================================================
# """
    def get_cic_profile_details(self, cic_name: str, parent_id: int = 2153):

        """"# need to read 'parent_id' from get api or read it from yaml file
        Fetch a specific CIC (Firmware Customization) profile from WUMS using fwc/{parent_id}/select endpoint.
    """

        if not self.bearer:
            raise ValueError("Bearer token not set. Call set_bearer() first.")
        payload = {
            "filterTerm": "",
            "pageInfo": {
                "pageNumber": 1,
                "pageSize": 100
            },
            "sortInfo": {
                "sortProperties": [
                    {
                        "name": "name",
                        "order": "ASCENDING"
                    }
                ]
            },
            "id": parent_id
        }

        endpoint = f"/wums-app/fwc-resource/fwc/{parent_id}/select"
        resp = self.api.post(
            endpoint,
            headers={
                "Authorization": self.bearer,
                "Content-Type": "application/json"
            },
            json=payload
        )
        log.info(f"[API] CIC fetch status: {resp.status_code}")

        if resp.status_code != 200:
            raise RuntimeError(
                f"CIC fetch failed | status={resp.status_code} | body={resp.text}"
            )

        data = resp.json()

        records = data.get("records", [])
        if not isinstance(records, list):
            raise ValueError(
                f"Unexpected CIC response structure. Keys: {list(data.keys())}"
            )
        target = cic_name.strip().lower()
        for record in records:
            ums_obj = record.get("umsObject", {})
            name_value = (
                ums_obj.get("name", {})
                .get("value", "")
                .strip()
                .lower()
            )
            if name_value == target:
                profile_id = ums_obj.get("typedId", {}).get("id")
                object_type = ums_obj.get("typedId", {}).get("type")
                log.info(
                    f"[API] CIC found: {name_value} "
                    f"(ID={profile_id}, TYPE={object_type})"
                )
                return {
                    "id": profile_id,
                    "name": name_value,
                    "type": object_type
                }
        available = [
            r.get("umsObject", {}).get("name", {}).get("value")
            for r in records
        ]
        raise ValueError(
            f"CIC profile '{cic_name}' not found. "
            f"Available CICs: {available}"
        )
# LG Below -5020
def unassign_profile(self, device_id, profile_id):

    url = f"{self.base_url}/umsapi/v3/thinclients/{device_id}/assignments/profiles/{profile_id}"

    logger.info(f"[API] Unassign profile from device {device_id} -> profile {profile_id}")

    response = requests.delete(
        url,
        headers=self.headers,
        verify=False
    )

    logger.info(f"[API] Unassign response: {response.status_code}")

    if response.status_code not in [200, 204]:
        logger.error(f"[API] Unassign failed: {response.text}")

    return response
#LG
