"""Unit tests for core.ssh.ssh_client.SSHClientIGEL."""
import pytest
from unittest.mock import patch, MagicMock

from core.ssh.ssh_client import SSHClientIGEL


class TestSSHClientInit:

    def test_attributes_set(self):
        ssh = SSHClientIGEL("192.168.1.1", 22, "root", "pass")
        assert ssh.host == "192.168.1.1"
        assert ssh.port == 22
        assert ssh.username == "root"
        assert ssh.client is None

    def test_password_defaults_empty(self):
        ssh = SSHClientIGEL("host", 22, "user")
        assert ssh.password == ""


class TestSSHClientConnect:

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_successful_connect(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        result = client.connect()
        assert result is True
        assert client.client is mock_ssh
        mock_ssh.connect.assert_called_once()

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_failed_connect(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh.connect.side_effect = Exception("Connection refused")
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        result = client.connect()
        assert result is False
        assert client.client is None


class TestSSHClientRunCommand:

    def test_run_command_no_connection(self):
        client = SSHClientIGEL("host", 22, "root")
        code, out, err = client.run_command("ls")
        assert code == -1
        assert err == "SSH not connected"

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_run_command_success(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output text"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.connect()
        code, out, err = client.run_command("ls /tmp")
        assert code == 0
        assert out == "output text"
        assert err == ""

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_run_command_exception(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh.exec_command.side_effect = Exception("Timeout")
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.connect()
        code, out, err = client.run_command("hang")
        assert code == -1
        assert "exec_command error" in err


class TestSSHClientClose:

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_close_connected(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.connect()
        client.close()
        mock_ssh.close.assert_called_once()
        assert client.client is None

    def test_close_not_connected(self):
        client = SSHClientIGEL("host", 22, "root")
        client.close()
        assert client.client is None


class TestSSHClientRun:

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_run_returns_stdout(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"version 12.7"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.connect()
        result = client.run("cat /etc/os-release")
        assert result == "version 12.7"

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    def test_run_raises_on_failure(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"command not found"
        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.connect()
        with pytest.raises(RuntimeError, match="SSH command failed"):
            client.run("nonexistent_cmd")


class TestSSHClientReconnect:

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    @patch("core.ssh.ssh_client.time.sleep")
    def test_reconnect_success_on_first_attempt(self, mock_sleep, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        client.client = MagicMock()  # simulate existing connection
        result = client.reconnect_with_retry(attempts=3, delay_sec=1)
        assert result is True

    @patch("core.ssh.ssh_client.paramiko.SSHClient")
    @patch("core.ssh.ssh_client.time.sleep")
    def test_reconnect_all_attempts_fail(self, mock_sleep, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh.connect.side_effect = Exception("refused")
        mock_ssh_cls.return_value = mock_ssh

        client = SSHClientIGEL("host", 22, "root")
        result = client.reconnect_with_retry(attempts=2, delay_sec=0)
        assert result is False
