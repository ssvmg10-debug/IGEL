"""
############################################################
## QCL-5605: Cache Partition check
# As part of the basic tests, it must be ensured that the Cache Partition (igf239) is restored in the event of an error.
# Procedure
#
# Install any amount of Apps
# Start any App
# Delete Cache Partition (igf239)
# Check if igf239 is deleted.
# When partition check = true. Reboot.
# After reboot. Check Cache Partition (igf239).
# When partition check = true. Start any App.
# Acceptance Criteria
# The Cache Partition (igf239) is created automatically and the App starts without any problems.
#
#
# Author: Vikas Hiremath
# email: vikas.hiremath_ext@igel.com
# creation date: 13-Jan-2026

"""

from time import sleep
import json

import sys
import os
import allure

sys.path.append(".")
sys.path.append("..")
sys.path.append('../..')

from config.read_config import ums_cred, device_cred, root_path

sys.path.append(root_path)

from core.ssh.ssh import SSHClient
from core.api.UMS import UMS
from core.ssh.my_logger import logger
global ssh, UM


host = device_cred["host"]
user = device_cred["user"]
pwd = device_cred["pwd"]
port = device_cred["port"]


ums_url=ums_cred["base_url"]
username=ums_cred["username"]
password=ums_cred["password"]


md5sum_before=None
md5sum_after=None
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


"""Step1: Install the to be tested IGEL OS version"""
def QCL_5605_step1():
	global ssh, UM
	try:
		logger.info("""Step1: Install the to be tested IGEL OS version""")
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

		version=ssh.get_version()
		if device_cred['version'] == version:
			return True
		else:
			logger.error(f"Version mismatch error: found - {version} expected - {device_cred['version']}")
			return False

	except Exception as e:
		logger.error(f"Exception executing step 1: {e}")
		return False

"""Step2: Install any amount of Apps"""
def QCL_5605_step2():
	global ssh, UM
	logger.info("""Step2: Install any amount of Apps""")
	try:
		#global device, edge_prof, chrom_prof, md5sum_before, file_md5sum_before, install_list
		global device,  md5sum_before, file_md5sum_before, install_list
		logger.info("""Preparation before firmware update""")
		device_name=device_cred['hostname']

		device = UM.get_vm_details(device_name.strip())

		logger.info(f"device details: {device}")
		app_file=os.path.join(root_path,"testdata","app_list.json")
		with open(app_file) as f:
			app_list = json.load(f)


		install_list = app_list["Install_list"]

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
			print(each_app)
			command=f"igelpkgctl list installed |grep {each_app['app_name']}"
			print(command)
			is_installed=ssh.exec(command)
			if is_installed =="":
				logger.error(f" {each_app['app_name']} not installed")
			else:
				logger.info(f" {each_app['app_name']} installed")


		logger.info("Checked Apps installed successfully")

		return  True

	except Exception as e:
		logger.error(f"Exception executing step 1: {e}")
		return False



"""Step3: Check cache partition (igf239)"""
def QCL_5605_step3():
	global ssh, UM
	try:
		ssh.reconnect()
		logger.info("""Step3: Check cache partition (igf239)""")
		command="create_directory -t | sed -n '/scanning raw device/,$p'| grep 'partition 239'"  #command to check the partition 239
		data=ssh.exec(command)
		if data=="":
			logger.error(f" Partition 239 not found")
			return False
		pattern = r"partition 239 with "
		if pattern  in data:
			logger.info(f"Partition 239 found: {data}")
			return True
		else:
			logger.error(f" Partition 239 not found")
			logger.debug(f"Output: {data}")
			return False


	except Exception as e:
		logger.error(f"Exception executing step 3: {e}")
		return False

"""Step4: Delete Cache Partition (igf239)"""
def QCL_5605_step4():
	global ssh, UM
	try:
		logger.info("""Step4: Delete Cache Partition (igf239)""")
		remote_file = "/wfs/igfdelete_fixed.sh"

		local_file = os.path.join(root_path,"testdata", "igfdelete_fixed.sh")


		"""upload the file to device to delete partition, the .sh file deletes the partition safely"""

		status = ssh.copy_file_to_remote(local_file, remote_file)
		if status==None or status==False:
			logger.error(f" Unable to copy file: {local_file}")
			return False
		else:
			logger.info(f" Successfully copied file: {remote_file}")

		"""Change permissions of remote file for execution and delete cache partition"""

		command=f"chmod +x {remote_file}"
		ssh.exec(command)
		command=f". {remote_file} 239"
		status=ssh.exec(command)
		if "bash <minor>" in status:
			print("Incorrect command")
			return False
		elif "Make partition 239 unusable with destroying section" in status:
			logger.info(f" Successfully executed file: {remote_file}")
			command = " create_directory -t | sed -n '/scanning raw device/,$p'| grep 'partition 239'"
			data = ssh.exec(command)
			if data=="":
				logger.info(f" Partition 239 deleted successfully")
				return True
			else:
				logger.error(f" Partition 239 still exists, deletion failed")
				logger.debug(f"{data}")
				return False

		else:
			logger.error(f" Error occurred to execute command: {command}")
			return False


	except Exception as e:
		logger.error(f"Exception executing step 4: {e}")
		return False

"""Step 5: Reboot device, and verify the deleted cache partition is restored"""
def QCL_5605_step5():
	global ssh, UM
	try:
		logger.info("Step 5: Reboot device.")
		ssh.reboot()
		sleep(15)
		logger.info("Device rebooted successfully")
		return True

	except Exception as e:
		logger.error(f"Exception executing step 5: {e}")
		return False

"""Step6: After reboot check if the cache partition igf239 is recreated by using the attached script"""
def QCL_5605_step6():
	global ssh, UM
	try:
		logger.info("""Step6: After reboot check if the cache partition igf239 is recreated by using the attached script""")
		command = "create_directory -t | sed -n '/scanning raw device/,$p'| grep 'partition 239'"
		data = ssh.exec(command)
		if data=="":
			logger.error(f" Partition 239 not found")
			return False
		pattern = r"partition 239 with "
		"""partition 239 with 4162 sections found, generation 9"""
		logger.debug(f"Pattern match: {data}")
		if pattern  in data:
			logger.info(f"Partition 239 found: {data}")
			return True
		else:
			logger.error(f" Partition 239 not found")
			logger.debug(f"{data}")
			return False


	except Exception as e:
		logger.error(f"Exception executing step 6: {e}")
		return False

def QCL_5605_step7():
	global ssh, UM
	logger.info("Step 7: Start any app on the device.")
	return True


""" clean all the installed apps"""
def QCL_5605_clean_up():
	global ssh, UM
	try:
		global assigned_profiles,UM,device, install_list, assigned_profiles_list
		logger.info("Cleaning up...")
		detach=detach_all_profiles(assigned_profiles,device,UM)
		logger.info("Removing all installed apps...")
		for app	in install_list:
			logger.debug(f"Removing {app['app_name']}")
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

		ssh.close()
		logger.info("Verified apps cleanup successfully")
		return True

	except Exception as e:
		logger.error(f"Exception during cleanup: {e}")
		ssh.close()
		return False


def test_QCL_5605_step1():
	with allure.step("Step1: Install the to be tested IGEL OS version"):
		assert QCL_5605_step1() == True

def test_QCL_5605_step2():
	with allure.step("Step2: Install any amount of Apps"):
		assert QCL_5605_step2() == True

def test_QCL_5605_step3():
	with allure.step("Step3: Check cache partition (igf239)"):
		assert QCL_5605_step3() == True

def test_QCL_5605_step4():
	with allure.step("Step4: Delete Cache Partition (igf239)"):
		assert QCL_5605_step4() == True

def test_QCL_5605_step5():
	with allure.step("Step 5: Reboot device, and verify the deleted cache partition is restored"):
		assert QCL_5605_step5() == True

def test_QCL_5605_step6():
	with allure.step("Step6: After reboot check if the cache partition igf239 is recreated by using the attached script"):
		assert QCL_5605_step6() == True

def test_QCL_5605_step7():
	with allure.step("Step 7: Start any app on the device."):
		assert QCL_5605_step7() == True

def test_cleanup():
	with allure.step("Cleanup: remove all installed apps"):
		QCL_5605_clean_up()




