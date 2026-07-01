import yaml
import os
import re
import sys
from pathlib import Path

root_path = Path(__file__).resolve().parents[1]
print(root_path)


sys.path.append(root_path)


def _resolve_env_vars(obj):
    """Recursively replace '${VAR}' placeholders with os.environ values."""
    if isinstance(obj, str):
        def _replace(match):
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                print(f"WARNING: environment variable {var_name} is not set")
                return match.group(0)
            return value
        return re.sub(r"\$\{(\w+)\}", _replace, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


try:

    file_path = os.path.join(root_path, "config", 'all_conf.yaml')

    with open(file_path, 'r') as file:
        config_data = yaml.safe_load(file)

    config_data = _resolve_env_vars(config_data)

    device_cred = config_data['device']
    ums_cred = config_data['UMS']
    logging_level = config_data['logger']
    otp_secrets_cred = config_data['otp_secret_cred']

except Exception as e:
    print(f"Exception occurred reading config file {e}")
    exit(1)