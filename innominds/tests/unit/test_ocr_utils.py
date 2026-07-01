"""Unit tests for core.utils.ocr_utils (pure text functions only).

The ocr_utils module imports PIL and pytesseract at module level (Windows
OCR dependencies). We mock those imports so the pure-logic functions can
be tested on any platform.
"""
import sys
import types
from unittest.mock import MagicMock

# Provide stub modules so ocr_utils can be imported without PIL/pytesseract
_pil_mod = types.ModuleType("PIL")
_pil_mod.ImageGrab = MagicMock()
_pil_mod.Image = MagicMock()
sys.modules.setdefault("PIL", _pil_mod)
sys.modules.setdefault("PIL.ImageGrab", MagicMock())
sys.modules.setdefault("PIL.Image", MagicMock())
sys.modules.setdefault("pytesseract", MagicMock())

import pytest

from core.utils.ocr_utils import normalize_text, derive_keywords_from_app_name


# ── normalize_text ────────────────────────────────────────────────────────────

class TestNormalizeText:

    def test_lowercase(self):
        assert normalize_text("Hello World") == "hello world"

    def test_underscore_to_space(self):
        assert normalize_text("hello_world") == "hello world"

    def test_dash_to_space(self):
        assert normalize_text("hello-world") == "hello world"

    def test_dot_removed(self):
        # dots are removed (not replaced with space)
        assert normalize_text("v1.2.3") == "v123"

    def test_newline_to_space(self):
        assert normalize_text("line1\nline2") == "line1 line2"

    def test_strip_whitespace(self):
        assert normalize_text("  padded  ") == "padded"

    def test_combined_normalization(self):
        result = normalize_text("  IGEL_OS-12.4\nTest  ")
        assert result == "igel os 124 test"

    def test_empty_string(self):
        assert normalize_text("") == ""


# ── derive_keywords_from_app_name ─────────────────────────────────────────────

class TestDeriveKeywords:

    def test_basic_keywords(self):
        keywords = derive_keywords_from_app_name("Citrix Workspace App")
        assert "citrix" in keywords
        assert "workspace" in keywords
        assert "app" in keywords

    def test_short_tokens_filtered(self):
        keywords = derive_keywords_from_app_name("MS RDP")
        assert "rdp" in keywords
        assert "ms" not in keywords

    def test_single_long_word(self):
        keywords = derive_keywords_from_app_name("Chromium")
        assert keywords == ["chromium"]

    def test_single_short_word_fallback(self):
        keywords = derive_keywords_from_app_name("RD")
        assert len(keywords) == 1
        assert keywords[0] == "rd"

    def test_underscore_and_dash_handling(self):
        keywords = derive_keywords_from_app_name("igel_smart-card")
        assert "igel" in keywords
        assert "smart" in keywords
        assert "card" in keywords

    def test_dots_removed(self):
        keywords = derive_keywords_from_app_name("v2.1.0")
        assert len(keywords) >= 1
