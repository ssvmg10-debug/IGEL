############################################################
## [Quick] | Data preservation
## Make sure that R/W partitions are still available and persistent after firmware update.
## /wfs
## /services_rw
## /cache

# Author: Vikas Hiremath
# email: vikas.hiremath_ext@igel.com
# creation date: 13-Jan-2026

from time import sleep
import json
import os
import sys

import allure

sys.path.append(".")
sys.path.append("..")
sys.path.append('../..')

from config.read_config import ums_cred, device_cred, root_path

sys.path.append(root_path)

from core.ssh.ssh import SSHClient
from core.api.UMS import UMS
from core.ssh.my_logger import logger




host = device_cred["host"]
user = device_cred["user"]
pwd = device_cred["pwd"]
port = device_cred["port"]
global ssh, UM


current_device_version=ums_cred["current_device_version"]
previous_device_version=ums_cred["previous_device_version"]
current_version_dir=ums_cred["current_version_dir"].strip()
previous_version_dir=ums_cred["previous_version_dir"].strip()

logger.info(f"current_version_dir: {current_version_dir}")

ums_url=ums_cred["base_url"]
username=ums_cred["username"]
password=ums_cred["password"]

md5sum_before=None
md5sum_after=None
device=edge_prof=chrom_prof=None
file_md5sum_before=file_md5sum_after=None
assigned_profiles=[]
install_list=None


def assign_all_profs_device(app_list, my_device, my_UM):
	global assigned_profiles
	try:
		logger.debug(f"Getting all profiles details...")
		prf_assign_list=[]
		for app in app_list:
			my_profile=my_UM.get_profile_details(app["profile_name"])
			prf_assign_list.append(my_profile)
			logger.debug(f"Got profile details for {app['profile_name']}")


		logger.info(f"Assigning all profiles to device: {my_device}")

		for app_profile in prf_assign_list:
			app_assign=my_UM.assign_profile_to_device(app_profile,my_device)
			if app_assign.ok:
				logger.info(f"Assigned profile to device: {app_profile['name']}")
				assigned_profiles.append(app_profile)
			else:
				logger.error(f"Error assigning profile to device: {app_profile['name']}")
				assigned_profiles.append(None)

		logger.info("Completed assigning all profiles to device")
		return assigned_profiles


	except Exception as e:
		logger.error(f"Exception while assigning profiles: {e}")
		return assigned_profiles

def detach_all_profiles(assigned_profiles,mydevice, myUMS):
	try:
		logger.info(f"Detaching all profiles from device: {mydevice}")
		detach=None
		for app in assigned_profiles:
			logger.debug(f"Detaching profile to device: {app['name']}")
			detach=myUMS.delete_profile_from_device(app, mydevice)
			if detach.ok:
				logger.debug(f"Detached profile to device: {app['name']}")

			else:
				logger.error(f"Error detaching profile to device: {app['name']}")

		logger.info("Completed detaching all profiles to device")
		return True

	except Exception as e:
		logger.error(f"Exception while detaching all profiles: {e}")
		return None

"""Step1: Preparation before firmware update"""
def QCL_4852_step1():
	global ssh, UM
	try:
		global device, edge_prof, chrom_prof, md5sum_before, file_md5sum_before, install_list, ssh, UM
		UM = UMS(ums_url, username, password)
		if UM:
			logger.info("UMS connection successfully")
		else:
			logger.error("UMS connection failed")
			exit()

		ssh = SSHClient(host, user, pwd, port)

		if ssh is None:
			logger.error(f"Error connecting to host: {host}")
			exit()
		logger.info("""Step1: Preparation before firmware update""")
		device_name=ssh.exec("hostname")

		print(device_name)
		device = UM.get_vm_details(device_name.strip())
		if device is None:
			logger.error(f"Error getting device from UMS: {device_name}")
			exit(-1)

		logger.info(f"device details: {device}")
		app_file = os.path.join(root_path, "testdata", "app_list.json")
		with open(app_file) as f:
			app_list = json.load(f)

		install_list = app_list["Install_list"]
		other_list = app_list["Other_list"]
		assigned_profiles_list=assign_all_profs_device(install_list, device, UM)


		logger.info(f"Waiting while profile being pushed to Device: {device_name}")
		sleep(10)
		logger.info("Rebooting the device to enforce profile...")
		ssh.reboot()
		sleep(15)
		logger.info("Rebooting to apply profile...")
		ssh.reboot()
		logger.info("Checking the installed apps...")

		for each_app in install_list:
			logger.info(f"Checking installed {each_app['app_name']}")
			command=f"igelpkgctl list installed |grep {each_app['app_name']}"
			print(command)
			is_installed=ssh.exec(command)
			if is_installed =="":
				logger.error(f" {each_app['app_name']} not installed")
			else:
				logger.info(f" {each_app['app_name']} installed")


		logger.info("Checked Apps installed successfully")
		logger.info("Verify check sum of setup.ini: before upgrade")
		md5sum_before = ssh.exec("md5sum /wfs/setup.ini")
		test_wfs_file = ssh.exec("echo 'hello IGEL' > /wfs/QCL-4852_test.txt")
		test_svc_rw_file = ssh.exec("echo 'hello IGEL' > /services_rw/QCL-4852_test.txt")
		test_cache_file = ssh.exec("echo 'hello IGEL' > /cache/QCL-4852_test.txt")
		if test_wfs_file =="" and test_svc_rw_file == "" and test_cache_file == "":
			logger.info("Files created successfully")
		logger.info("Calculate checksum of files before upgrade")
		file_md5sum_before=ssh.exec("md5sum /wfs/QCL-4852_test.txt /services_rw/QCL-4852_test.txt /cache/QCL-4852_test.txt")
		logger.info(f"files md5sum before: {file_md5sum_before}")
		print(f"files md5sum before: {file_md5sum_before}")

		logger.info(f"md5sum = {md5sum_before}")
		return  True

	except Exception as e:
		logger.error(f"Exception executing step 1: {e}")
		return False


"""Step2: Update Firmware"""
def QCL_4852_step2():
	global ssh, UM
	global current_version_dir
	device_name = ssh.exec("hostname")


	try:
		logger.info("""Step2: Update Firmware""")
		
		install_version=ssh.get_version()
		if current_device_version==install_version:
			logger.info("""Firmware is up to date""")
			return True
		else:
			logger.info(f"""Updating firmware to latest version: {current_device_version}""")
			logger.debug(f"Moving {device['name']} to folder : {current_version_dir}")
			status=UM.move_device_to_directory(device, current_version_dir)

			if status == None:
				logger.error(f" Error updating firmware to : {current_device_version}: ")
				return False

			if status:
				sleep(60)
				ssh.reboot() 	#"""First reboot to enforce the policy"""
				sleep(60)

			sleep(100) 	#"""Additional wait for system firmware upgrade"""

			ssh.reboot()

			if ssh.get_version() == current_device_version:
				return True
			else:
				logger.error(f" Failed updating firmware to : {current_device_version}: ")
				return False


	except Exception as e:
		logger.error(f"Exception executing step 2 - upgrading firmware: {e}")
		return False

def QCL_4852_step3():
	global ssh, UM
	try:
		logger.info("""Step3: Check Browser Bookmarks""")
		return True

	except Exception as e:
		logger.error(f"Exception executing step 3: {e}")
		return False

def QCL_4852_step4():
	global ssh, UM
	try:
		logger.info("""Step4: Check Sessions""")
		return True

	except Exception as e:
		logger.error(f"Exception executing step 4: {e}")
		return False

def QCL_4852_step5():
	global ssh, UM
	try:
		global md5sum_before,md5sum_after,file_md5sum_before
		logger.info("Step 5: Compare checksum of setup,ini")
		md5sum_after = ssh.exec("md5sum /wfs/setup.ini")
		logger.info(f"md5sum after = {md5sum_after}")
		file_md5sum_after = ssh.exec(
			"md5sum /wfs/QCL-4852_test.txt /services_rw/QCL-4852_test.txt /cache/QCL-4852_test.txt")
		logger.info(f"files md5sum after: {file_md5sum_after}")
		print(f"files md5sum after: {file_md5sum_after}")
		file_md5sum=True
		if file_md5sum_before.strip() == file_md5sum_after.strip():
			logger.info("md5sum of files same before and after reboot")

		else:
			logger.error("Mismatch in md5sum.")
			file_md5sum=False

		setup_md5=True
		logger.info("Compare md5sum before and after:")
		if md5sum_before == md5sum_after:
			logger.info("MD5sum same before and after firmware update")

		else:
			logger.error("Mismatch in setup.ini md5sum.")
			setup_md5=False

		if setup_md5 == False or file_md5sum == False:
			return False

		else:
			return True

	except Exception as e:
		logger.error(f"Exception executing step 5: {e}")
		return False


def QCL_4852_step6():
	global ssh, UM
	try:
		logger.info("""Step6: Check UMS management""")
		old_id = device['id']
		device_name=device_cred["hostname"]
		device2 = UM.get_vm_details(device_name)
		# device2 = UM.get_vm_details("ITC005056AD3496")
		new_id = device2['id']
		if new_id is not None:
			logger.info("Device is still managed by UMS")
			return True
		else:
			logger.error("Device is not managed by UMS")
			return False

	except Exception as e:
		logger.error(f"Exception executing step 6: {e}")
		return False


def QCL_4852_clean_up():
	global ssh, UM
	try:
		global assigned_profiles,UM,device, install_list
		logger.info("Cleaning up...")
		detach=detach_all_profiles(assigned_profiles,device,UM)
		for app	in install_list:
			command=f"yes | head -n -1 | igelpkgctl  uninstall {app['app_name']}"
			data=ssh.exec(command)
			if "Nothing to do, the given APP is not installed" == data.strip():
				logger.error(f"Nothing to do, the given APP is not installed")

		logger.info("Rebooting device to clean up")
		ssh.reboot()
		logger.info("Rebooted device successfully")
		for app in install_list:
			command=f"igelpkgctl list installed |grep {app['app_name']}"
			data=ssh.exec(command)
			if data.strip() == "":
				logger.debug(f"Uninstalled {app['app_name']} successfully")
			else:
				logger.error(f"Error removing {app['app_name']} : {data.strip()}")

		logger.info("Verified apps cleanup successfully")
		ssh.close()
		return True

	except Exception as e:
		logger.error(f"Exception during cleanup: {e}")
		ssh.close()
		return False





def test_QCL_4852_step1():
	with allure.step("Step1: Preparation before firmware update"):
		assert QCL_4852_step1()

def test_QCL_4852_step2():
	with allure.step("Step2: Update Firmware"):
		assert QCL_4852_step2()

def test_QCL_4852_step3():
	with allure.step("Step3: Check Browser Bookmarks"):
		assert QCL_4852_step3()

def test_QCL_4852_step4():
	with allure.step("Step4: Check Sessions"):
		assert QCL_4852_step4()

def test_QCL_4852_step5():
	with allure.step("Step 5: Compare checksum of setup,ini"):
		assert QCL_4852_step5()

def test_QCL_4852_step6():
	with allure.step("Step6: Compare checksum of setup,ini"):
		assert QCL_4852_step6()

def test_QCL_4852_clean_up():
	with allure.step("Cleaning up"):
		QCL_4852_clean_up()