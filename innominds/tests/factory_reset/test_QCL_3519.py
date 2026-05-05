"""
Summary

Perform these steps to test the four options of resetting an endpoint to factory defaults.

Environment

Additional information

Knowledge Base: Resetting a Device to Factory Defaults via the IGEL UMS Web App
IGEL Community Tech Videos: How to Reset IGEL OS to Factory Defaults

# Author: Vikas Hiremath
# email: vikas.hiremath_ext@igel.com
# creation date: 13-Feb-2026

"""

from time import sleep
import sys

import allure

sys.path.append(".")
sys.path.append("..")
sys.path.append('../..')

from config.read_config import ums_cred, device_cred, root_path

sys.path.append(root_path)

from core.ssh.ssh import SSHClient
from core.api.UMS import UMS
from core.api.wums_api import UMSWUMSApi
from core.ssh.my_logger import logger


host = device_cred["host"]
user = device_cred["user"]
pwd = device_cred["pwd"]
port = device_cred["port"]
global ssh, UM, WUMS


ums_url=ums_cred["base_url"]
username=ums_cred["username"]
password=ums_cred["password"]
wums_url=ums_cred["weburl"]

"""
Set up
"""
def QCL_3519_set_up():
    global ssh, UM, WUMS
    logger.info("***Step 1: Set up***")
    try:
        logger.info("connecting via ssh:")
        ssh = SSHClient(host, user, pwd)
        if ssh is None:
            logger.error("SSH connection failed")
            return False

        UM = UMS(ums_url, username, password)
        if UM :
            logger.info("UMS connection successful")

        else:
            logger.error("UMS connection failed")
            return False

        WUMS = UMSWUMSApi(wums_url, username, password)
        if WUMS:
            logger.info("WUMS connection successful")

        else:
            logger.error("WUMS connection failed: ")
            return False

    except Exception as e:
        logger.error(f"Exception occurred during set up: {e}")
        return False

"""
Step 1: Reset to factory defaults after reboot
"""
def QCL_3519_step1():
    global ssh, UM, WUMS
    try:
        logger.info("***Step 1: Reset to factory defaults after reboot***")

        return True

    except Exception as e:
        logger.error(f"Exception occurred during factory defaults reset: {e}")
        return False


"""
Step 2: Reset to factory defaults via UMS
"""
def QCL_3519_step2():
    global ssh, UM, WUMS
    try:
        logger.info("***Step 2: Reset to factory defaults via UMS***")
        logger.info("connecting via ssh:")
        ssh = SSHClient(host, user, pwd)
        if ssh is None:
            logger.error("SSH connection failed")
            return False, "SSH connection failed"
        device_hostname = device_cred["hostname"]
        device = UM.get_vm_details(device_hostname)
        logger.info("Sending factory reset api command...")
        status, data = UM.reset_to_defaults(device)
        if status:
            logger.info(f"Factory reset api command successful:{data}")
            logger.info("rebooting device")
            ssh.exec("reboot")
            sleep(120)
            logger.info("Scanning for device")
            scanned_deices=WUMS.scan_devices()
            device_dir = ums_cred["current_version_dir"]
            current_directory=UM.get_tc_directory_details(device_dir)
            device_found=False
            for vm in scanned_deices:
                logger.debug(f"{vm}")
                if device_hostname in vm["hostName"] and vm["alreadyManaged"] is False:
                    logger.info("Scanned device successfully after factory resset.")
                    logger.info(f"Registering device {device_hostname} to directory {device_dir}")
                    status = WUMS.register_device(current_directory['id'], vm['macAddr'], vm['ipAddr'])
                    if status.status_code in [200, 201]:
                        logger.info(f"Registered device {device_hostname} to directory {device_dir} successfully")
                        device_found = True
                        sleep(120)

                    else:
                        logger.error(f"Failed to register device {device_hostname} to directory {device_dir}")
                        return False, status.text
                    break
            if not device_found:
                logger.error(f"{device_hostname} not found during scanning.")
                return False, f"{device_hostname} not found during scanning."



            device = UM.get_vm_details(device_hostname)

            logger.info(f"Enabling ssh on  {device_hostname}")
            status = WUMS.enable_ssh_vnc(device['id'])
            logger.debug(f"{status}, {dir(status)}")
            if status.ok:
                logger.info(f"Successfully enabled ssh on  {device_hostname}")
            else:
                logger.error(f"Failed to enable ssh on  {device_hostname}: {status.text}")

            status, message = UM.device_reboot(device)
            logger.info("Waiting for device to reboot")
            sleep(30)
            retry_count=6
            while retry_count > 0:
                retry_count -= 1

                status=UM.get_device_online_status(device)
                if status:
                    logger.info("Device rebooted successfully")
                    break
                else:
                    logger.info(f"Waiting for device to reboot: {retry_count}")
                    sleep(60)

            if retry_count == 0 and not status:
                logger.error("Device failed to reboot")
                return False, "Device failed to reboot"

            ssh.reconnect()
            version = ssh.get_version()
            logger.info(f"After factory reset Version: {version}")



        else:
                logger.error(f"Factory reset api command failed: {data}")
                ssh.reboot()
                sleep(120)
                return False, f"Factory reset api command failed: {data}"


        return True, None
    except Exception as e:
        logger.error(f"Exception occurred during factory defaults reset via UMS: {e}")
        return False


"""
Step 3: Reset to factory defaults via WUMS (UMS Web App)
"""

def QCL_3519_step3():
    global ssh, UM, WUMS
    try:
        logger.info("Step 3: Reset to factory defaults via WUMS")


    except Exception as e:
        logger.error(f"Exception occurred during factory defaults via WUMS: {e}")
        return False


"""
Step 4: Reset to factory defaults via terminal
"""
def QCL_3519_step4():
    global ssh, UM, WUMS
    try:
        logger.info("***Step 4: Reset to factory defaults via terminal***")

        ssh = SSHClient(host, user, pwd)
        if ssh is None:
            logger.error("SSH connection failed")
            return False, "SSH connection failed"
        else:
            logger.info(f"*connected to ssh successfully*: {host}")

        status = ssh.exec("echo yes| reset_to_defaults")
        logger.info(f"status = {status}")
        if status is None:
            logger.error("Reset to factory defaults via terminal failed")
            return False, "Reset to factory defaults via terminal failed"
        logger.info("Waiting for device to reboot")
        ssh.reboot()


        sleep(120)
        logger.info("Scanning for device to register to ums...")

        scanned_deices = WUMS.scan_devices()
        device_dir = ums_cred["current_version_dir"]
        current_directory = UM.get_tc_directory_details(device_dir)
        device_found = False
        device_hostname = device_cred["hostname"]
        for vm in scanned_deices:
            logger.debug(f"{vm}")
            if device_hostname in vm["hostName"] and vm["alreadyManaged"] is False:
                logger.info("Scanned device successfully after factory resset.")
                logger.info(f"Registering device {device_hostname} to directory {device_dir}")
                status = WUMS.register_device(current_directory['id'], vm['macAddr'], vm['ipAddr'])
                if status.status_code in [200, 201]:
                    logger.info(f"Registered device {device_hostname} to directory {device_dir} successfully")
                    device_found = True
                    sleep(120)
                else:
                    logger.error(f"Failed to register device {device_hostname} to directory {device_dir}")
                    return False, status.text
                break

        if not device_found:
            logger.error(f"{device_hostname} not found during scanning.")
            return False, f"{device_hostname} not found during scanning."

        device = UM.get_vm_details(device_hostname)
        logger.info(f"Enabling ssh on  {device_hostname}")
        status = WUMS.enable_ssh_vnc(device['id'])
        if status.ok:
            logger.info(f"Enabling ssh on  {device_hostname}")
        else:
            logger.error(f"Failed to enable ssh on  {device_hostname}: {status.text}")
        logger.debug(f"{status}")
        status, message = UM.device_reboot(device)
        logger.info("Waiting for device to reboot")

        retry_count = 6
        while retry_count > 0:
            retry_count -= 1

            status = UM.get_device_online_status(device)
            if status:
                logger.info("Device rebooted successfully")
                break
            else:
                logger.info(f"Waiting for device to reboot: {retry_count}")
                sleep(60)

        if retry_count == 0 and not status:
            logger.error("Device failed to reboot")
            return False, "Device failed to reboot"

        ssh.reconnect()
        version=ssh.get_version()
        logger.info(f"Version: {version}")

        return True, "None"

    except Exception as e:
        logger.error(f"Exception occurred during factory defaults via terminal: {e}")
        return False, f"Exception occurred during factory defaults via terminal: {e}"



def QCL_3519_cleanup():
    global ssh, UM, WUMS
    try:
        logger.info("***Clean Up started...***")
        ssh.close()
        UM.cleanup()

        logger.info("Clean Up finished")

    except Exception as e:
        logger.error(f"Exception occurred during cleanup: {e}")

    return True, "None"




def test_QCL_3519_set_up():
    with allure.step("Step 1: Install the to be tested IGEL OS"):
        QCL_3519_set_up()

def test_QCL_3519_step2():
    with allure.step("Step 2: Install the to be tested IGEL OS"):
        status, message = QCL_3519_step2()
        assert status is True, message

def test_QCL_3519_step4():
    with allure.step("Step 4: Reset to factory defaults via terminal"):
        status, message = QCL_3519_step4()
        assert status is True, message

def test_QCL_3519_cleanup():
    with allure.step("Step 5: Cleanup"):
        QCL_3519_cleanup()