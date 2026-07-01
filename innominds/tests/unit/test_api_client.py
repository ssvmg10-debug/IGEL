"""Unit tests for core.api.api_client.APIClient."""
import pytest
from unittest.mock import patch, MagicMock

from core.api.api_client import APIClient


class TestAPIClientInit:

    def test_base_url_trailing_slash_stripped(self):
        client = APIClient("https://example.com/api/")
        assert client.base_url == "https://example.com/api"

    def test_base_url_without_trailing_slash(self):
        client = APIClient("https://example.com/api")
        assert client.base_url == "https://example.com/api"

    def test_session_created(self):
        client = APIClient("https://example.com")
        assert client.session is not None

    def test_ssl_verification_disabled(self):
        client = APIClient("https://example.com")
        assert client.session.verify is False


class TestAPIClientMethods:

    @patch("core.api.api_client.requests.Session")
    def test_get_calls_session_get(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        client = APIClient("https://example.com")
        client.get("/path")
        mock_session.get.assert_called_once_with("https://example.com/path")

    @patch("core.api.api_client.requests.Session")
    def test_post_calls_session_post(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        client = APIClient("https://example.com")
        client.post("/path", json={"key": "val"})
        mock_session.post.assert_called_once_with(
            "https://example.com/path", json={"key": "val"}
        )

    @patch("core.api.api_client.requests.Session")
    def test_put_calls_session_put(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        client = APIClient("https://example.com")
        client.put("/path", data="body")
        mock_session.put.assert_called_once_with(
            "https://example.com/path", data="body"
        )

    @patch("core.api.api_client.requests.Session")
    def test_patch_calls_session_patch(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        client = APIClient("https://example.com")
        client.patch("/path", headers={"X-Custom": "1"})
        mock_session.patch.assert_called_once_with(
            "https://example.com/path", headers={"X-Custom": "1"}
        )

    def test_url_concatenation(self):
        client = APIClient("https://host:8443/api")
        # Verify base_url is properly set for concatenation
        assert client.base_url == "https://host:8443/api"
