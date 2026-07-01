import json
import requests


def get_ums_creds(file_name):
	ums=None
	try:
		with open(file_name) as f:
			ums = json.loads(f)
		return ums

	except Exception as e:
		print(f"Exception: {e}")


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
			if (response.ok):
				return session
			else:
				return None
		except Exception as e:
			print(f"Exception occured: {e}")
			return None

	def get_all_tc_directories(self):
		try:
			url=f"{self.base_url}/directories/tcdirectories"
			tc_dirs=self.session.get(url)
			if (tc_dirs):
				return tc_dirs.json()
			else:
				return None
		except Exception as e:
			print(F"Exception getting all dirs: {e}")


	def get_tc_directory_details(self, dir_name=None):
		try:
			print(f"dir name = {dir_name}")
			if dir_name is None:
				print(f"dir_name is missing/not valid")
				return None
			url=f"{self.base_url}/directories/tcdirectories"
			tc_dir_list=self.session.get(url)
			if tc_dir_list.status_code in (401, 402):
				print("Session disconnected, reconnecting...")
				self.__connect__()
				tc_dir_list=self.session.get(url)
				if tc_dir_list.ok:
					for tc_dir in tc_dir_list.json():
						if tc_dir['name'] == dir_name:
							return tc_dir

			elif (tc_dir_list.ok):

				for tc_dir in tc_dir_list.json():
					if tc_dir['name'] == dir_name:
						print(f"TC Directory found: {dir_name}")
						return tc_dir
				print(f"No matching directory found:{dir_name}")
				return None
			else:
				print(f"No matching directory found:{dir_name}")
				return None

		except Exception as e:
			print(f"Exception occurred: {e}")
			return None



	def get_vm_details(self, vm_name):
		try:
			url = f"{self.base_url}/thinclients"
			vm_List=self.session.get(url)
			for vm in vm_List.json():
				if vm_name == vm["name"]:
					return vm

			return None
		except Exception as e:
			print(f"Exception occurred in get vms: {e}")
			return None

	def get_profile_details(self, prof_name):
		try:
			url=f"{self.base_url}/profiles"
			pr_list=self.session.get(url)
			for profile in pr_list.json():
				if prof_name==profile["name"]:
					return profile

			return None

		except Exception as e:
			print(f"Error while reading profiles: {e}")
			return None
	
	def assign_profile_to_device (self, profile, device):
		try:
			print(f"Assigning profile {profile['name']} to {device['name']}")
			if profile["id"] and device["id"]:
				url=f"{self.base_url}/profiles/{profile['id']}/assignments/thinclients"
				#data=f"('[{"assignee": {"id": profile["id"], "type": "profile"}, "receiver": {"id": device["id"], "type": "tc"}}]')
				data=[{"assignee": {"id": profile["id"], "type": "profile"}, "receiver": {"id": device["id"], "type": "tc"}}]
				print(f"data = {data}, url={url}")
				assignment=self.session.put(url, json=data, verify=False)
				if (assignment.ok):
					print(f"Assigned profile {profile['name']} successfully to device {device['name']}")
					return assignment
				else:
					print(f"Error assigning the policy: {assignment.json()}")
					return assignment

		except Exception as e:
			print(f"Exception assigning profile to device: {e}")
			return None
		
	
	def delete_profile_from_device(self, profile, device):
		try:
			print(f"Deleting profile {profile['name']} from {device['name']}")
			if profile["id"] and device["id"]:
				url=f"{self.base_url}/profiles/{profile['id']}/assignments/thinclients/{device['id']}"
				print(f"URL is {url}")
				delete=self.session.delete(url)
				if (delete.ok):
					print(f"Deleted profile {profile['name']} from {device['name']} successfully")
					return delete

				else:
					print(f"Error deleting the profile: {delete.json()}")
					return delete

		except Exception as e:
			print(f"Exception deleting profile: {e}")
			return None

	def get_all_profile_directories(self):
		try:
			url=f"{self.base_url}/directories/profiledirectories"
			print(f"url is {url}")
			prof_dirs=self.session.get(url)
			if prof_dirs.ok:
				print("Rxd profiles")
				return prof_dirs.json()
			else:
				print(f"Error reading all profiles: {prof_dirs.json()}")
				return None
		except Exception as e:
			print(f"Exception during read all profiles: {e}")
			return None

	def get_all_priority_profiles(self):
		try:
			url=f"{self.base_url}/masterprofiles"
			prt_prof_dirs=self.session.get(url)
			if prt_prof_dirs.ok:
				print("Rxd priority profiles:")
				return prt_prof_dirs.json()
			elif prt_prof_dirs.status_code in (401, 403):
				print("Connection lost, reconnecting..");
				self.__connect__()
				prt_prof_dirs=self.session.get(url)
				if prt_prof_dirs.ok:
					print("Rxd priority profiles:")
					return prt_prof_dirs.json()
			else:
				print(f"Error reading prt profiles: {prt_prof_dirs.json()}")
				return None

		except Exception as e:
			print(f"Exception reading prt profiles: {e}")
			return None

	def create_profile_directory(self, name):
		try:
			url=(f"{self.base_url}/directories/profiledirectories")
			if name:
				data={"name":name}
			else:
				print("Dir name not valid")
				return None
			crt_prf_dir=self.session.put(url, data=data)
			if crt_prf_dir.status_code in (401, 403):
				self.__connect__()
				crt_prf_dir=self.session.put(url, data=data)
				if crt_prf_dir.ok:
					print ("Created profile directory successfully")
					return crt_prf_dir.json()
				else:
					print(f"Error creating profile dir: {crt_prf_dir.json()}")
		
		except Exception as e:
			print(f"Exception creating profile directory: {e}")
			return None

	def get_profile_assigned_device(self, device):
		try:
			device_id=device["id"]
			url=(f"{self.base_url}/thinclients/{device_id}/assignments/profiles")
			print(f"url is {url}")
			profile_assigned=self.session.get(url)
			if profile_assigned.status_code in (401, 403):
				self.__connect__()
				profile_assigned=self.session.get(url)
			if profile_assigned.ok:
				print("Rxd profiles")
				return profile_assigned.json()

			else:
				print(f"Error getting profile assigned: {profile_assigned.json()}")
				return None
		except Exception as e:
			print(f"Exception getting profile assigned: {e}")

	def get_device_online_status(self, device):
		try:
			device_id=device["id"]
			url=(f"{self.base_url}/thinclients/{device_id}?facets=online")
			print(f"url is {url}")
			online_status=self.session.get(url)
			return json.loads(online_status.content)['online']


		except Exception as e:
			print(f"Exception getting online status: {e}")
			return None


	def move_device_to_directory(self, device, dir_name):
		if device is None or dir_name is None:
			print(f"Device Directory ({dir_name})or device:{device} details not found!")
		try:
			device_id=device["id"]
			data=[{f"id":device_id, "type":"tc"}]
			print(f"data is {data}")
			dirs = self.get_all_tc_directories()
			tgt_dir = None
			for dir in dirs:
				if dir["name"] == dir_name:
					tgt_dir = dir

			if tgt_dir is None:
				print(f"Device Directory not found: {dir_name}")
				return None

			url = f"{self.base_url}/directories/tcdirectories/{tgt_dir['id']}?operation=move"
			print(f"url is {url}")
			print(f"data = {data}")
			resp = self.session.put(url, json=data, verify=False)
			if resp.status_code in (401, 403):
				self.__connect__()
				resp=self.session.put(url, json=data, verify=False)
				if resp.ok:
					print(f"Moved device to directory: {dir_name}")
					return True
				else:
					print(f"Error moving device to directory: {dir_name}")
					print(resp.json())
					return False
			else:
				#resp = self.session.put(url, json=data, verify=False)
				if resp.ok:
					print(f"Moved device to directory: {dir_name}")
					print(resp.json())
					return True
				else:
					print(f"Error moving device to directory: {dir_name}")
					print(resp.json())
					return False
# LG 3 line
		except Exception as e:
			print(f"Exception moving device to directory {e}")
			return None
# LG 3 line


	def enable_ssh(self,device):
		try:
			payload={  "sshEnabled": True }
			id=device["id"]
			url = (f"{self.base_url}/clients/{id}/apply")
			###Incomplete

		except Exception as e:
			print(f"Exception enabling ssh: {e}")
			return None


	def reset_to_defaults(self, device=None):
		if device is None:
			print("Device details not found!")
			return False, "Device details not found!"
		try:
			url=f"{self.base_url}/thinclients"
			params={'command':'tcreset2facdefs'}
			device_id = f"{device['id']}"
			data=[{'id':device_id, 'type':'tc'}]
			print("Sending factory reset api request...")
			resp=self.session.post(url, params=params, json=data, verify=False)
			print(resp.text)
			if resp.status_code in (401, 403):
				print("Session disconnected, trying to reconnect...")
				self.__connect__()
				if self.session:
					print("Reconnection successful")
				else:
					print("Connection failed")
					return False, resp.json()
				resp=self.session.put(url, params=params, json=data, verify=False)
				if resp.ok:
					print(f"Reset device to defaults: {device_id}")
					print(resp.text)
					print("Status here is:")
					x=resp.json()
					print(x["CommandExecList"][0]["state"])
					return True
				else:
					print(f"Error resetting device to defaults: {device_id}")
					print(resp.json())
					print(resp.text)
					return False, resp.json()

			elif resp.ok:
				print(f"Reset device to defaults: {device_id}")
				print(resp.text)
				print("Status here is:")
				x = resp.json()
				print(x["CommandExecList"][0]["state"])
				return True, resp.json()


		except Exception as e:
			print(f"Exception resetting to defaults: {e}")
			return False, {e}

	def device_reboot(self, device=None):
		if device is None:
			print("Device details not found!")
			return False, "Device details not found!"
		try:
			url=f"{self.base_url}/thinclients"
			params={'command':'reboot'}
			device_id = f"{device['id']}"
			data=[{'id':device_id, 'type':'tc'}]
			print("Sending device reboot api request...")
			resp=self.session.post(url, params=params, json=data, verify=False)
			print(resp.text)
			if resp.status_code in (401, 403):
				print("Session disconnected, trying to reconnect...")
				self.__connect__()
				if self.session:
					print("Reconnection successful")
				else:
					print("Connection failed")
					return False, resp.json()
				resp=self.session.put(url, params=params, json=data, verify=False)
				if resp.ok:
					print(f"Rebooting device {device_id}")
					print(resp.text)
					print("Status here is:")
					x=resp.json()
					print(x["CommandExecList"][0]["state"])
					return True, resp.json()
				else:
					print(f"Error rebooting device: {device_id}")
					print(resp.json())
					print(resp.text)
					return False, resp.json()

			elif resp.ok:
				print(f"Device rebooted: {device_id}")
				print(resp.text)
				print("Status here is:")
				x = resp.json()
				print(x["CommandExecList"][0]["state"])
				return True, resp.json()


		except Exception as e:
			print(f"Exception rebooting: {e}")
			return False, {e}

	def cleanup(self):
		try:
			self.session.close()
			print("UMS Session closed")

		except Exception as e:
			print(f"Exception cleaning up UMS session: {e}")

