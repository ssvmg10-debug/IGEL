import logging
import yaml
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

root_path = Path(__file__).resolve().parents[1]

sys.path.append(root_path)


file_path = os.path.join(root_path, "config", 'all_conf.yaml')

try:
    with open(file_path, 'r') as file:
        config_data = yaml.safe_load(file)
except FileNotFoundError:
    log.error("Config file not found: %s", file_path)
    raise
except yaml.YAMLError as e:
    log.error("Invalid YAML in config file %s: %s", file_path, e)
    raise

_required_keys = ['device', 'UMS', 'logger', 'otp_secret_cred']
_missing = [k for k in _required_keys if k not in config_data]
if _missing:
    raise KeyError(f"Missing required config keys: {_missing}")

device_cred = config_data['device']
ums_cred = config_data['UMS']
logging_level = config_data['logger']
otp_secrets_cred = config_data['otp_secret_cred']