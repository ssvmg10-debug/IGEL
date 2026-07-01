"""
Shared device configuration payloads for the WUMS API.

Centralizes duplicated JSON payloads that were copy-pasted across
wums_api.py and ums_wums_api.py.
"""

import json

SSH_VNC_SETTINGS = json.dumps({
    "network.ssh_server.enabled": {"uiType": "bool", "value": True, "type": 2},
    "network.ssh_server.permit_empty_passwords": {"uiType": "bool", "value": True, "type": 2},
    "network.ssh_server.permit_root_login": {"uiType": "bool", "value": True, "type": 2},
    "network.vncserver.enabled": {"uiType": "bool", "value": True, "type": 2},
    "network.vncserver.secure_mode": {"uiType": "bool", "value": False, "type": 2},
    "network.vncserver.promptuser": {"uiType": "bool", "value": False, "type": 2},
    "network.vncserver.showdisconnectbtn": {"uiType": "bool", "value": False, "type": 2},
    "userinterface.vncserver.indicatorposition": {"uiType": "string", "value": "top-right", "type": 2},
    "update.auto_reboot_timeout": {"uiType": "integer", "value": 240, "type": 2},
})


def make_device_config_payload(device_id, data_payload, send_now=True):
    """
    Build the standard device configuration update payload.

    Used by enable_ssh_vnc, update_device_configuration, and similar methods
    across wums_api.py and ums_wums_api.py.
    """
    return {
        "id": {"id": device_id, "type": "DEVICE"},
        "data": data_payload,
        "language": "en",
        "sendSettingsNow": send_now,
    }
