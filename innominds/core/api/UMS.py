import json
import logging
import requests

log = logging.getLogger(__name__)


def get_ums_creds(file_name):
	try:
		with open(file_name) as f:
			ums = json.load(f)
		return ums
	except FileNotFoundError:
		log.error("Credentials file not found: %s", file_name)
		raise
	except json.JSONDecodeError as e:
		log.error("Invalid JSON in credentials file %s: %s", file_name, e)
		raise


class UMS:
	def __init__(self, base_url, user, pwd):
		self.base_url=base_url
		self.user=user
		self.pwd=pwd
		self.session=self.__connect__()


	def __connect__(self):
		try:
			requests.packages.urllib3.disable_warnings()
			session = requests.Session()
			session.auth = (self.user,self.pwd)
			session.verify = False
			login_url = f"{self.base_url}/login"
			response = session.post(login_url)
			if response.ok:
				return session
			else:
				log.error("UMS login failed with status %s: %s", response.status_code, response.text)
				raise ConnectionError(
					f"UMS login failed (HTTP {response.status_code}): {response.text}"
				)
		except requests.RequestException as e:
			log.error("UMS connection failed: %s", e)
			raise ConnectionError(f"UMS connection failed: {e}") from e

	def get_all_tc_directories(self):
		url=f"{self.base_url}/directories/tcdirectories"
		tc_dirs=self.session.get(url)
		if tc_dirs.ok:
			return tc_dirs.json()
		log.error("Failed to get TC directories (HTTP %s): %s", tc_dirs.status_code, tc_dirs.text)
		raise RuntimeError(
			f"Failed to get TC directories (HTTP {tc_dirs.status_code})"
		)


	def get_tc_directory_details(self, dir_name=None):
		if dir_name is None:
			raise ValueError("dir_name is required")

		log.info("Looking up TC directory: %s", dir_name)
		url=f"{self.base_url}/directories/tcdirectories"
		tc_dir_list=self.session.get(url)

		if tc_dir_list.status_code in (401, 402):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			tc_dir_list=self.session.get(url)

		if not tc_dir_list.ok:
			raise RuntimeError(
				f"Failed to list TC directories (HTTP {tc_dir_list.status_code})"
			)

		for tc_dir in tc_dir_list.json():
			if tc_dir['name'] == dir_name:
				log.info("TC Directory found: %s", dir_name)
				return tc_dir

		return None



	def get_vm_details(self, vm_name):
		url = f"{self.base_url}/thinclients"
		resp=self.session.get(url)
		if not resp.ok:
			raise RuntimeError(
				f"Failed to list VMs (HTTP {resp.status_code}): {resp.text}"
			)
		for vm in resp.json():
			if vm_name == vm["name"]:
				return vm
		return None

	def get_profile_details(self, prof_name):
		url=f"{self.base_url}/profiles"
		resp=self.session.get(url)
		if not resp.ok:
			raise RuntimeError(
				f"Failed to list profiles (HTTP {resp.status_code}): {resp.text}"
			)
		for profile in resp.json():
			if prof_name==profile["name"]:
				return profile
		return None
	
	def assign_profile_to_device (self, profile, device):
		if not profile.get("id") or not device.get("id"):
			raise ValueError("Both profile and device must have an 'id'")

		log.info("Assigning profile %s to %s", profile['name'], device['name'])
		url=f"{self.base_url}/profiles/{profile['id']}/assignments/thinclients"
		data=[{"assignee": {"id": profile["id"], "type": "profile"}, "receiver": {"id": device["id"], "type": "tc"}}]
		assignment=self.session.put(url, json=data, verify=False)
		if assignment.ok:
			log.info("Assigned profile %s successfully to device %s", profile['name'], device['name'])
		else:
			log.error("Error assigning profile: %s", assignment.text)
		return assignment
		
	
	def delete_profile_from_device(self, profile, device):
		if not profile.get("id") or not device.get("id"):
			raise ValueError("Both profile and device must have an 'id'")

		log.info("Deleting profile %s from %s", profile['name'], device['name'])
		url=f"{self.base_url}/profiles/{profile['id']}/assignments/thinclients/{device['id']}"
		resp=self.session.delete(url)
		if resp.ok:
			log.info("Deleted profile %s from %s successfully", profile['name'], device['name'])
		else:
			log.error("Error deleting profile: %s", resp.text)
		return resp

	def get_all_profile_directories(self):
		url=f"{self.base_url}/directories/profiledirectories"
		resp=self.session.get(url)
		if resp.ok:
			return resp.json()
		log.error("Failed to read profile directories (HTTP %s): %s", resp.status_code, resp.text)
		raise RuntimeError(
			f"Failed to read profile directories (HTTP {resp.status_code})"
		)

	def get_all_priority_profiles(self):
		url=f"{self.base_url}/masterprofiles"
		resp=self.session.get(url)
		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.get(url)
		if resp.ok:
			return resp.json()
		log.error("Failed to read priority profiles (HTTP %s): %s", resp.status_code, resp.text)
		raise RuntimeError(
			f"Failed to read priority profiles (HTTP {resp.status_code})"
		)

	def create_profile_directory(self, name):
		if not name:
			raise ValueError("Directory name is required")

		url=(f"{self.base_url}/directories/profiledirectories")
		data={"name":name}
		resp=self.session.put(url, data=data)
		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.put(url, data=data)
		if resp.ok:
			log.info("Created profile directory: %s", name)
			return resp.json()
		log.error("Failed to create profile directory (HTTP %s): %s", resp.status_code, resp.text)
		raise RuntimeError(
			f"Failed to create profile directory (HTTP {resp.status_code})"
		)

	def get_profile_assigned_device(self, device):
		device_id=device["id"]
		url=(f"{self.base_url}/thinclients/{device_id}/assignments/profiles")
		resp=self.session.get(url)
		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.get(url)
		if resp.ok:
			return resp.json()
		log.error("Failed to get assigned profiles (HTTP %s): %s", resp.status_code, resp.text)
		raise RuntimeError(
			f"Failed to get assigned profiles (HTTP {resp.status_code})"
		)

	def get_device_online_status(self, device):
		device_id=device["id"]
		url=(f"{self.base_url}/thinclients/{device_id}?facets=online")
		resp=self.session.get(url)
		if not resp.ok:
			raise RuntimeError(
				f"Failed to get device online status (HTTP {resp.status_code})"
			)
		data = resp.json()
		if 'online' not in data:
			raise RuntimeError(f"'online' field missing from response: {data}")
		return data['online']

	def move_device_to_directory(self, device, dir_name):
		if device is None or dir_name is None:
			raise ValueError(
				f"Both device and dir_name are required (device={device}, dir_name={dir_name})"
			)

		device_id=device["id"]
		data=[{"id":device_id, "type":"tc"}]
		dirs = self.get_all_tc_directories()
		tgt_dir = None
		for d in dirs:
			if d["name"] == dir_name:
				tgt_dir = d

		if tgt_dir is None:
			raise RuntimeError(f"Target directory not found: {dir_name}")

		url = f"{self.base_url}/directories/tcdirectories/{tgt_dir['id']}?operation=move"
		resp = self.session.put(url, json=data, verify=False)
		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.put(url, json=data, verify=False)

		if resp.ok:
			log.info("Moved device to directory: %s", dir_name)
			return True
		log.error("Error moving device to directory %s (HTTP %s): %s", dir_name, resp.status_code, resp.text)
		return False

	def enable_ssh(self,device):
		raise NotImplementedError("enable_ssh is not yet implemented")

	def reset_to_defaults(self, device=None):
		if device is None:
			raise ValueError("Device details are required")

		url=f"{self.base_url}/thinclients"
		params={'command':'tcreset2facdefs'}
		device_id = f"{device['id']}"
		data=[{'id':device_id, 'type':'tc'}]
		log.info("Sending factory reset for device %s", device_id)
		resp=self.session.post(url, params=params, json=data, verify=False)

		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.post(url, params=params, json=data, verify=False)

		if not resp.ok:
			log.error("Factory reset failed (HTTP %s): %s", resp.status_code, resp.text)
			return False, resp.json()

		result = resp.json()
		state = result.get("CommandExecList", [{}])[0].get("state", "unknown")
		log.info("Factory reset sent for %s, state=%s", device_id, state)
		return True, result

	def device_reboot(self, device=None):
		if device is None:
			raise ValueError("Device details are required")

		url=f"{self.base_url}/thinclients"
		params={'command':'reboot'}
		device_id = f"{device['id']}"
		data=[{'id':device_id, 'type':'tc'}]
		log.info("Sending reboot for device %s", device_id)
		resp=self.session.post(url, params=params, json=data, verify=False)

		if resp.status_code in (401, 403):
			log.warning("Session expired, reconnecting...")
			self.session = self.__connect__()
			resp=self.session.post(url, params=params, json=data, verify=False)

		if not resp.ok:
			log.error("Device reboot failed (HTTP %s): %s", resp.status_code, resp.text)
			return False, resp.json()

		result = resp.json()
		state = result.get("CommandExecList", [{}])[0].get("state", "unknown")
		log.info("Reboot sent for %s, state=%s", device_id, state)
		return True, result

	def cleanup(self):
		try:
			self.session.close()
			log.info("UMS session closed")
		except Exception as e:
			log.warning("Error closing UMS session: %s", e)