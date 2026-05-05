"""
The rmagent uses a client certificate to authenticate itself in the UMS, otherwise the UMS refuses the TLS connection
from rmagent. As the certificate is issued for one year (365 days), it must be renewed. This is automatically done by
the rmagent before expiration date. This test must ensure that the automatic renewal works during boot.

The certificate is enrolled during registering (= onboarding) process and it saved in the file /wfs/igel-rmagent/cert.pem.

All test steps must be executed by root.



# Author: Vikas Hiremath
# email: vikas.hiremath_ext@igel.com
# creation date: 5-Mar-2026

"""

from time import sleep
import sys

import allure
from pathlib import Path

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

ums_url=ums_cred["base_url"]
username=ums_cred["username"]
password=ums_cred["password"]

global ssh, UM
global cert_file
cert_file='/wfs/igel-rmagent/cert.pem'

"""
# Set up and Precondition
"""

def QCL_5011_set_up():
    global ssh, UM
    try:
        logger.info("connecting via ssh:")
        ssh = SSHClient(host, user, pwd)
        if ssh is None:
            logger.error("SSH connection failed")
            return False, "SSH connection failed"

        UM = UMS(ums_url, username, password)
        if UM :
            logger.info("UMS connection successful")

        else:
            logger.error("UMS connection failed")
            return False, "UMS connection failed"

        device = UM.get_vm_details(device_cred["hostname"])
        if device is None:
            logger.error("Device not found")
            return False, "Device not found in UMS"

        return True, None

    except Exception as e:
        logger.error(f"Exception occurred during set up: {e}")
        return False, str(e)


"""
Step 1: Configure certificate renewal period
"""
def QCL_5011_step1():
    global ssh, UM
    try:
        logger.info("***Step 1: Configure certificate renewal period***")
        cert_file_bk = cert_file+".bk"
        command = f"cp {cert_file} {cert_file_bk}"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Cert file backed up successfully: {cert_file_bk}")
        else:
            logger.error(f"Cert file backed up failed: {output}")

        logger.info("Changing the cert expiry time to 400 days")
        command="setparam system.remotemanager.days_left_certificate 400"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Cert file renewal set successfully to 400")
        else:
            logger.error(f"Cert file renewal set failed: {output}")
            return False, f"Cert file renewal set failed: {output}"

        return True, None
    except Exception as e:
        logger.error(f"Exception occurred during set up: {e}")
        return False, str(e)


"""
Step 2: Copy and compare certificates
"""
def QCL_5011_step2():
    global ssh, UM, cert_file
    try:
        logger.info("***Step 2: Copy and compare certificates***")
        """
        Copying should not modify the file content
        """
        cert_file_old = cert_file + ".old"
        command = f"cp {cert_file} {cert_file_old}"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Cert file backed up successfully: {cert_file_old}")
        else:
            logger.error(f"Cert file back up failed: {output}")
            return False, f"Cert file back up failed: {output}"

        command=f"diff -q {cert_file_old} {cert_file}"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Both cert files are same {cert_file_old}, {cert_file}")
            return True, "Both cert files are same"
        else:
            logger.error(f"Both cert files are different: {output}")
            return False, "Both cert files are different" + str(output)


    except Exception as e:
        logger.error(f"Exception occurred during copy and compare certificates: {e}")
        return False, "Exception occurred during copy and compare certificates: " + str(e)


"""
*** Step 3: Reboot the endpoint ***
"""
def QCL_5011_step3():
    global ssh, UM
    try:
        logger.info("***Step 3: Reboot the endpoint***")
        """
        Rebooting the device should update the certificate after renewal extension
        """
        ssh.reboot()
        sleep(5)
        logger.info(f"Rebooted the device")
        device_name=device_cred['hostname']
        device=UM.get_vm_details(device_name)
        if device['id']:
            logger.info("Device is still managed by UMS.")
            return True, None
        else:
            logger.error("Device is not managed by UMS.")
            return False, "Device is not managed by UMS"


    except Exception as e:
        logger.error(f"Exception occurred during reboot: {e}")
        return False, "Exception occurred during reboot: " + str(e)

"""
*** Step 4: Check certificate renewal
"""
def QCL_5011_step4():
    global ssh, UM
    try:
        logger.info("***Step 4: Check certificate renewal***")

        old_cert_file = cert_file+".old"
        command = f"diff -q {cert_file} {old_cert_file}"
        output = ssh.exec(command)
        if output == "":
            logger.error(f"Both cert files are same: {old_cert_file}, {cert_file}")
            return False, "Both cert files are same"
        elif 'differ' in output:
            logger.info(f"Both cert files are different: {output}")
            return True, "Both cert files are different" + str(output)
        else:
            logger.error(f"Error comparing files: {output}")
            return False, "Error comparing files: " + str(output)

    except Exception as e:
        logger.error(f"Exception occurred during cert verification after reboot: {e}")
        return False, "Exception occurred during cert verification: " + str(e)

"""
***Step 5:Delete certificate copy
"""
def QCL_5011_step5():
    global ssh, UM, cert_file
    try:
        logger.info("***Step 5: Delete certificate copy***")

        cert_file_old=cert_file+".old"

        command = f"rm -f {cert_file_old}"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Old cert file deleted successfully: {cert_file_old}")
            return True, "Old cert file deleted successfully"
        else:
            logger.error(f"Old cert file deletion failed: {output}")
            return False, "Old cert file deletion failed: " + str(output)

    except Exception as e:
        logger.error(f"Exception occurred during cert file deletion: {e}")
        return False, "Exception occurred during cert file deletion: " + str(e)


"""
***Step 6: Reset certificate renewal period***
"""
def QCL_5011_step6():
    global ssh, UM, cert_file
    try:
        logger.info("***Step 6: Reset certificate renewal period***")
        command="resetvalue system.remotemanager.days_left_certificate"
        output = ssh.exec(command)
        if output == "":
            logger.info(f"Reset certificate renewal period successful")
        else:
            logger.error(f"Reset certificate renewal period failed: {output}")
            return False, "Reset certificate renewal period failed: " + str(output)

        ssh.reboot()
        sleep(5)
        cmd=f"ls -l {cert_file}"
        output = ssh.exec(cmd)
        if cert_file in output:
            return True, "Reset certificate renewal successfully"
        else:
            return False, "Reset certificate renewal failed: " + str(output)

    except Exception as e:
        logger.error(f"Exception occurred during cert verification  {e}")
        return False, "Exception occurred during cert verification: " + str(e)


"""
***Step 7: Cleanup
"""
def QCL_5011_cleanup():
    global ssh, UM
    logger.info("***Step 7: Cleanup***")
    try:
        ssh.close()
        UM.cleanup()
        logger.info(f"Cleanup done")

    except Exception as e:
        logger.error(f"Exception occurred during cleanup: {e}")


def test_QCL_5011_setup():
    with allure.step("Setup : Set up and Precondition"):
        result, status = QCL_5011_set_up()
        assert result is True

def test_QCL_5011_step1():
    with allure.step("Step 1: Configure certificate renewal period"):
        result, message = QCL_5011_step1()
        assert result is True

def test_QCL_5011_step2():
    with allure.step("Step 2: Copy and compare certificates"):
        result, message = QCL_5011_step2()
        assert result is True, message

def test_QCL_5011_step3():
    with allure.step("Step 3: Reboot the endpoint"):
        result, message = QCL_5011_step3()
        assert result is True, message

def test_QCL_5011_step4():
    with allure.step("Step 4: Check certificate renewal"):
        result, message = QCL_5011_step4()
        assert result is True, message

def test_QCL_5011_step5():
    with allure.step("Step 5: Delete certificate copy"):
        result, message = QCL_5011_step5()
        assert result is True, message

def test_QCL_5011_step6():
    with allure.step("Step 6: Reset certificate renewal period"):
        result, message = QCL_5011_step6()
        assert result is True, message

def test_QCL_5011_cleanup():
    with allure.step("Cleanup : Closing all connections"):
        QCL_5011_cleanup()