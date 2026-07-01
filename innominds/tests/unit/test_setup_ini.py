"""Unit tests for core.utils.setup_ini (pure string functions)."""
import pytest

from core.utils.setup_ini import add_qa_repo, add_browser_session


# ── add_qa_repo ───────────────────────────────────────────────────────────────

class TestAddQaRepo:

    def test_adds_repo_block(self):
        content = "<existing>data</existing>"
        uuid = "abc-123"
        url = "https://repo.example.com/qa"
        result = add_qa_repo(content, uuid, url)
        assert uuid in result
        assert url in result
        assert "<update>" in result
        assert content in result

    def test_skips_if_url_exists(self):
        url = "https://repo.example.com/qa"
        content = f"<existing>data with {url}</existing>"
        result = add_qa_repo(content, "abc-123", url)
        assert result == content

    def test_preserves_original_content(self):
        content = "original content here"
        result = add_qa_repo(content, "uuid1", "http://new.url")
        assert result.startswith("original content here")

    def test_multiple_repos(self):
        content = ""
        content = add_qa_repo(content, "uuid1", "http://url1")
        content = add_qa_repo(content, "uuid2", "http://url2")
        assert "uuid1" in content
        assert "uuid2" in content
        assert "http://url1" in content
        assert "http://url2" in content


# ── add_browser_session ───────────────────────────────────────────────────────

class TestAddBrowserSession:

    def test_adds_session_block(self):
        content = "<existing>data</existing>"
        result = add_browser_session(content, "chromium", "sess-uuid")
        assert "<app>" in result
        assert "chromium" in result
        assert "sess-uuid" in result
        assert "<sessions>" in result

    def test_skips_if_session_exists(self):
        content = "<existing><chromium$sess-uuid></existing>"
        result = add_browser_session(content, "chromium", "sess-uuid")
        assert result == content

    def test_preserves_original_content(self):
        content = "original"
        result = add_browser_session(content, "firefox", "uuid1")
        assert result.startswith("original")

    def test_session_structure(self):
        result = add_browser_session("", "myapp", "u1")
        assert "<myapp>" in result
        assert "</myapp>" in result
        assert "uuid=<u1>" in result
        assert "name=<myapp>" in result
