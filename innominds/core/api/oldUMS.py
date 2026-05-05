"""
############################################################
## Author       : Laxmikanth Ghali
## Email        : laxmikanth.ghali_ext@igel.com
## Created On   : Jan-2026
## Version      : 1.0
############################################################
"""
import json
import requests

#from test.test.test import payload


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



	def enable_ssh(self,device):
		try:
			payload={  "sshEnabled": True }
			id=device["id"]
			url = (f"{self.base_url}/clients/{id}/apply")
			###Incomplete

		except Exception as e:
			print(f"Exception enabling ssh: {e}")
			return None
	




#ums_url = "https://192.168.10.28:8443/umsapi/v3"
#username = "vikas.hiremath.ums"
#password = "igelxinnominds"

#UM=UMS(ums_url,username,password)
#vm=UM.get_vm_details("ITC005056AD3496")
#print(vm)
#prfs=UM.get_profile_assigned_device(vm)
#print(prfs)

#prof=UM.get_profile__details("vikas_edge")
#print(f"Profile id = {prof['id']}")
#print(f"Profile is {prof['name']}")
#assmt=UM.assign_profile_to_device(prof,vm)
#print(assmt)
#delete = UM.delete_profile_from_device(prof,vm)
#print(delete)
#get_profs=UM.get_all_profile_directories()
#print(get_profs)
#dirs=UM.get_all_tc_directories()
#print(dirs)
#prt_profs=UM.get_all_priority_profiles()
#print(prt_profs)
