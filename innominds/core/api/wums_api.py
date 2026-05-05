###########################################################
# Title        : UMS & WUMS Unified API Client
# Description  : Single reusable API client handling
#                authentication, browser lifecycle,
#                bearer reuse, session reuse and retry.
#
# Features
# --------
# - Single Playwright browser instance
# - Single Bearer token reused
# - Automatic refresh on 401/403
# - Automatic retry
# - Payload override support
#
# Author       : Sai Arokala
# Version      : 2.0
###########################################################


import base64
import time
import requests
import secrets
import hashlib

from urllib.parse import urlparse, parse_qs
from core.utils.logger import get_logger

log = get_logger(__name__)


class UMSWUMSApi:

    # --------------------------------------------
    # SHARED TOKEN CACHE
    # --------------------------------------------
    _bearer = None
    _token_expiry = 0

    # --------------------------------------------
    # INIT
    # --------------------------------------------
    def __init__(self, base_url, username, password):

        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

        # single session for all API calls
        self.api = requests.Session()
        self.api.verify = False
        self.api.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        if not UMSWUMSApi._bearer:
            self._authenticate()

    # --------------------------------------------
    # PKCE HELPERS
    # --------------------------------------------
    def _generate_code_verifier(self):
        return base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).rstrip(b'=').decode()

    def _generate_code_challenge(self, verifier):
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    # --------------------------------------------
    # AUTHENTICATION (PKCE → LBearer)
    # --------------------------------------------
    def _authenticate(self):

        log.info("[AUTH] Starting PKCE authentication")

        # use SAME session everywhere
        self.api = requests.Session()
        self.api.verify = False

        bearer, expires_in = self._get_bearer_token(session=self.api)

        UMSWUMSApi._bearer = bearer
        UMSWUMSApi._token_expiry = time.time() + expires_in - 30

        self.api.headers.update({
            "Authorization": bearer
        })

        log.info("[AUTH] LBearer token ready")

    # --------------------------------------------
    # PKCE FLOW
    # --------------------------------------------
    def _get_bearer_token(self, session):

        verifier = self._generate_code_verifier()
        challenge = self._generate_code_challenge(verifier)

        redirect_uri = f"{self.base_url}/webapp/authorize"
        authorize_url = f"{self.base_url}/auth-service/oauth2/authorize"

        auth_params = {
            "response_type": "code",
            "client_id": "webums",
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }

        # Step 1
        session.get(authorize_url, params=auth_params, verify=False, timeout=15)

        # Step 2
        login_url = f"{self.base_url}/auth-service/login"

        session.post(
            login_url,
            data={
                "username": self.username,
                "password": self.password,
                "rememberMe": "false",
                "dropdownLanguage": "en"
            },
            verify=False,
            timeout=15
        )

        # Step 3
        final = session.get(
            authorize_url,
            params=auth_params,
            allow_redirects=True,
            verify=False,
            timeout=15
        )

        redirect_url = final.url

        if "code=" not in redirect_url:
            raise RuntimeError(f"Authorization failed: {redirect_url}")

        auth_code = parse_qs(urlparse(redirect_url).query)["code"][0]

        # Step 4
        token_url = f"{self.base_url}/auth-service/oauth2/token"

        resp = session.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "code_verifier": verifier,
                "client_id": "webums",
                "redirect_uri": redirect_uri
            },
            verify=False,
            timeout=15
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Token failed: {resp.text}")

        data = resp.json()

        access_token = data.get("access_token")

        if not access_token:
            raise RuntimeError("No access token received")

        log.info("[AUTH] Bearer token generated")

        return f"LBearer {access_token}", data.get("expires_in", 300)

    # --------------------------------------------
    # TOKEN CHECK
    # --------------------------------------------
    def _ensure_token_valid(self):

        if time.time() >= UMSWUMSApi._token_expiry:
            log.info("[AUTH] Token expired → refreshing")
            self._authenticate()

    def _login_ums_session(self):

        log.info("[AUTH] Logging into UMS (JSESSIONID)")

        session = requests.Session()
        session.verify = False

        creds = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()

        resp = session.post(
            f"{self.base_url}/umsapi/v3/login",
            headers={"Authorization": f"Basic {creds}"}
        )

        if resp.status_code != 200:
            raise RuntimeError("UMS login failed")

        jsession = session.cookies.get("JSESSIONID")

        if not jsession:
            raise RuntimeError("JSESSIONID missing")

        log.info("[AUTH] JSESSIONID acquired")

        return session

    # --------------------------------------------
    # REQUEST WRAPPER
    # --------------------------------------------
    def _request(self, method, url, **kwargs):

        is_wums = url.startswith("/wums-app")

        for _ in range(2):

            if is_wums:
                self._ensure_token_valid()
                headers = kwargs.pop("headers", {})
                headers["Authorization"] = UMSWUMSApi._bearer
                kwargs["headers"] = headers
                session = self.api

            else:
                # use JSESSION session
                if not hasattr(self, "_ums_session"):
                    self._ums_session = self._login_ums_session()

                session = self._ums_session

            resp = getattr(session, method)(
                f"{self.base_url}{url}",
                **kwargs
            )

            if resp.status_code in (401, 403):

                log.warning("[AUTH] Re-authenticating...")

                if is_wums:
                    self._authenticate()
                else:
                    self._ums_session = self._login_ums_session()

                continue

            return resp

        raise RuntimeError("Request failed after retry")

    # --------------------------------------------------
    # DIRECTORIES
    # --------------------------------------------------
    def get_directory_id(self, directory_name):

        resp = self._request(
            "get",
            "/umsapi/v3/directories/tcdirectories"
        )

        for d in resp.json():

            if d["name"] == directory_name:
                return d["id"]

        raise RuntimeError(f"Directory not found: {directory_name}")

    # --------------------------------------------------
    # DEVICE
    # --------------------------------------------------
    def scan_devices(self, payload=None):

        if payload is None:
            payload = {"useTcpScan": False}

        resp = self._request(
            "post",
            "/wums-app/device-command/scanfordevices",
            json=payload
        )

        return resp.json()

    def register_device(self, directory_id, mac, ip, payload=None):

        if payload is None:
            payload = {
                "targetdir": directory_id,
                "devices": {mac: ip}
            }

        resp = self._request(
            "post",
            "/wums-app/device-command/registerdevices",
            json=payload
        )

        return resp

    def get_device_id(self, device_name):

        resp = self._request(
            "get",
            "/umsapi/v3/thinclients"
        )

        data = resp.json()

        if isinstance(data, dict):
            devices = data.get("items") or data.get("data") or []
        else:
            devices = data

        for d in devices:

            if d.get("name") == device_name:
                return d.get("id")

        raise RuntimeError(f"Device not found: {device_name}")

    def reboot_device(self, device_id, payload=None):

        if payload is None:
            payload = {
                "command": {"name": "REBOOT", "commandParams": {}},
                "deviceId": device_id
            }

        return self._request(
            "post",
            "/wums-app/device-command/execute",
            json=payload
        )

    def reset_device_to_factory(self, device_id):

        payload = {
            "command": {
                "name": "RESET_TO_FACTORY_DEFAULTS",
                "commandParams": {}
            },
            "deviceId": device_id
        }

        return self._request(
            "post",
            "/wums-app/device-command/execute",
            json=payload
        )

    # --------------------------------------------------
    # PROFILE
    # --------------------------------------------------
    def create_profile(self, name, description, directory_id, apps):

        payload = {
            "name": name,
            "description": description,
            "directoryId": directory_id,
            "masterProfile": False,
            "appLineVersionList": apps
        }

        resp = self._request(
            "post",
            "/wums-app/configuration/createConfiguration",
            json=payload
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

    def assign_profile(self, device_id, profile_id):

        payload = {
            "assignOrUnassignObjects": [
                {
                    "objectId": profile_id,
                    "objectType": "PROFILE",
                    "unassign": False
                }
            ],
            "deviceId": device_id,
            "updateTime": "NOW"
        }

        return self._request(
            "post",
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            json=payload
        )

    # --------------------------------------------------
    # APPLICATION
    # --------------------------------------------------
    def assign_app(self, device_id, app_id):

        payload = {
            "assignOrUnassignObjects": [
                {
                    "objectId": app_id,
                    "objectType": "INSTALLED_APP",
                    "unassign": False
                }
            ],
            "deviceId": device_id,
            "updateTime": "NOW"
        }

        return self._request(
            "post",
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            json=payload
        )

    # --------------------------------------------------
    # PROFILE DIRECTORY
    # --------------------------------------------------
    def create_profile_directory(self, parent_directory_id, directory_name):

        log.info(f"[API] Creating profile directory '{directory_name}' under parent {parent_directory_id}")

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

        resp = self._request(
            "post",
            "/wums-app/configuration/createOrRenameDirectory",
            json=payload
        )

        assert resp.status_code == 200, (
            f"Directory creation failed: {resp.status_code} {resp.text}"
        )

        data = resp.json()

        if "id" not in data:
            raise Exception(f"Unexpected response: {data}")

        directory_id = data["id"]["id"]

        log.info(f"[API] Profile directory created with ID {directory_id}")

        return directory_id

    # --------------------------------------------------
    # GET OR CREATE PROFILE DIRECTORY
    # --------------------------------------------------
    def get_or_create_profile_directory(
            self,
            directory_name,
            parent_directory_id
    ):
        """
        Finds profile directory by name.
        If not found, creates it under given parent.
        """

        log.info(f"[PROFILE DIR] Resolving directory: {directory_name}")

        tree = self.get_profile_directory_tree()

        def find_dir(node):

            # ✅ FIXED FIELD ACCESS
            name = node.get("directoryName", {}).get("value")

            if name == directory_name:
                return node.get("typedId", {}).get("id")

            for child in node.get("children", []):
                res = find_dir(child)
                if res:
                    return res

            return None

        # ------------------------------------------
        # SEARCH EXISTING
        # ------------------------------------------
        existing_id = find_dir(tree)

        if existing_id:
            log.info(f"[PROFILE DIR] Found existing: {existing_id}")
            return existing_id

        # ------------------------------------------
        # CREATE NEW
        # ------------------------------------------
        log.info(f"[PROFILE DIR] Creating new directory: {directory_name}")

        new_id = self.create_profile_directory(
            parent_directory_id=parent_directory_id,
            directory_name=directory_name
        )

        log.info(f"[PROFILE DIR] Created: {new_id}")

        return new_id

    # --------------------------------------------------
    # DEVICE CLEANUP
    # --------------------------------------------------
    def cleanup_device_if_exists(self, device_name):

        try:
            device_id = self.get_device_id(device_name)

            log.warning(f"[DEVICE] Device exists: {device_name}")

        except Exception:
            log.info("[DEVICE] Device not present")
            return

        self.reset_device_to_factory(device_id)

        log.info("[DEVICE] Waiting for device reset")

        time.sleep(120)

        for _ in range(6):

            try:
                self.get_device_id(device_name)

                log.warning("[DEVICE] Still present")

                time.sleep(20)

            except Exception:

                log.info("[DEVICE] Device cleaned")

                return

        raise RuntimeError("Device cleanup failed")

    def enable_ssh_vnc(self, device_id):

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
                "\"userinterface.vncserver.indicatorposition\":{\"uiType\":\"string\",\"value\":\"top-right\",\"type\":2},"
                "\"update.auto_reboot_timeout\":{\"uiType\":\"integer\",\"value\":240,\"type\":2}}"
            ),
            "language": "en",
            "sendSettingsNow": True
        }

        return self._request(
            "post",
            "/wums-app/device-detail/updateDeviceConfiguration",
            json=payload
        )

    def set_template_version(
            self,
            app_id,
            version_id,
            profile_fixed_version_label,
            name,
            return_status=False
    ):

        resp = self._request(
            "patch",
            f"/wums-app/installedapp/{app_id}/set-template-version",
            json={
                "versionId": version_id,
                "updateTime": "NOW"
            }
        )

        if return_status:
            return resp.status_code, resp.text

        assert resp.status_code in (200, 204), (
            f"Failed to set template version for {name}: "
            f"{resp.status_code} {resp.text}"
        )

    def assign_object(self, device_id, object_id, object_type, unassign):

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

        return self._request(
            "post",
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            json=payload
        )

    def unassign_object(
            self,
            device_id,
            object_id,
            object_type,
            unassign=True
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

        resp = self._request(
            "post",
            "/wums-app/device-profile/assignOrUnassignObjectToDevice",
            json=payload
        )
        return resp.status_code, resp.text


    def get_profile_directory_tree(self):

        resp = self._request(
            "get",
            "/wums-app/configuration/rootDirectoryTree/DIRECTORY_REGULAR_PROFILE"
        )

        return resp.json()

    def get_direct_assigned_objects(self, device_id):

        resp = self._request(
            "get",
            f"/wums-app/device-profile/directAssignedObjectsByDeviceId/{device_id}"
        )

        return resp.json()

    # --------------------------------------------------
    # EDIT PROFILE CONFIGURATION
    # --------------------------------------------------
    def update_profile_configuration(self, profile_id, data_payload, send_now=False):

        payload = {
            "id": {
                "id": profile_id,
                "type": "REGULAR_PROFILE"
            },
            "data": data_payload,  # IMPORTANT: string JSON
            "language": "en",
            "sendSettingsNow": send_now
        }

        resp = self._request(
            "post",
            "/wums-app/configuration/config",
            json=payload
        )

        assert resp.status_code in (200, 202), (
            f"Profile update failed: {resp.status_code} {resp.text}"
        )

        return resp

    def update_device_configuration(self, device_id, data_payload, send_now=True):
        """
        Update device configuration (used for default browser, SSH, etc.)
        """

        payload = {
            "id": {
                "id": device_id,
                "type": "DEVICE"
            },
            "data": data_payload,  # IMPORTANT: string JSON
            "language": "en",
            "sendSettingsNow": send_now
        }

        resp = self._request(
            "post",
            "/wums-app/device-detail/updateDeviceConfiguration",
            json=payload
        )

        assert resp.status_code in (200, 202), (
            f"Device config update failed: {resp.status_code} {resp.text}"
        )

        return resp


