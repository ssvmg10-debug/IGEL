"""Unit tests for knowledge_base.prompts (pure helper functions)."""
import pytest

from knowledge_base.prompts import (
    _estimate_tokens,
    _truncate_at_word,
    _slugify,
    _format_context_block,
    build_system_prompt,
)


# ── _estimate_tokens ──────────────────────────────────────────────────────────

class TestEstimateTokens:

    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_proportional_to_length(self):
        short = _estimate_tokens("hello")
        long = _estimate_tokens("hello world this is a longer string")
        assert long > short

    def test_returns_int(self):
        result = _estimate_tokens("some text")
        assert isinstance(result, int)


# ── _truncate_at_word ─────────────────────────────────────────────────────────

class TestTruncateAtWord:

    def test_short_text_unchanged(self):
        assert _truncate_at_word("hello", 100) == "hello"

    def test_truncates_at_word_boundary(self):
        result = _truncate_at_word("hello world foo bar", 12)
        assert result == "hello world"
        assert len(result) <= 12

    def test_no_space_returns_truncated(self):
        result = _truncate_at_word("abcdefghij", 5)
        assert result == "abcde"

    def test_exact_length(self):
        text = "hello"
        assert _truncate_at_word(text, 5) == "hello"

    def test_truncation_never_exceeds_max(self):
        text = "The quick brown fox jumps over the lazy dog."
        for max_chars in [5, 10, 15, 20, 30]:
            result = _truncate_at_word(text, max_chars)
            assert len(result) <= max_chars


# ── _slugify ──────────────────────────────────────────────────────────────────

class TestSlugify:

    def test_basic_slug(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars_removed(self):
        result = _slugify("Install IGEL OS (v12)")
        assert "(" not in result
        assert ")" not in result

    def test_max_length_50(self):
        long = "A" * 100
        result = _slugify(long)
        assert len(result) <= 50

    def test_spaces_to_underscores(self):
        assert _slugify("some test name") == "some_test_name"

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_only_special_chars(self):
        result = _slugify("!@#$%")
        assert result == ""


# ── _format_context_block ─────────────────────────────────────────────────────

class TestFormatContextBlock:

    def test_empty_results(self):
        result = _format_context_block([])
        assert "No relevant KB content" in result

    def test_formats_results(self):

        class FakeResult:
            section_title = "Test Section"
            file_name = "guide.md"
            product = "IGEL OS"
            chunk_type = "concept"
            rrf_score = 0.85
            parent_content = "Content about IGEL OS configuration."
            rerank_score = None

        result = _format_context_block([FakeResult()])
        assert "SOURCE 1" in result
        assert "Test Section" in result
        assert "guide.md" in result
        assert "IGEL OS" in result
        assert "0.85" in result

    def test_multiple_results_separated(self):

        class FakeResult:
            def __init__(self, idx):
                self.section_title = f"Section {idx}"
                self.file_name = f"file{idx}.md"
                self.product = "IGEL"
                self.chunk_type = "concept"
                self.rrf_score = 0.5
                self.parent_content = f"Content {idx}."
                self.rerank_score = None

        result = _format_context_block([FakeResult(1), FakeResult(2)])
        assert "SOURCE 1" in result
        assert "SOURCE 2" in result
        assert "---" in result


# ── build_system_prompt ───────────────────────────────────────────────────────

class TestBuildSystemPrompt:

    def test_returns_non_empty(self):
        prompt = build_system_prompt()
        assert len(prompt) > 100

    def test_contains_igel_references(self):
        prompt = build_system_prompt()
        assert "IGEL" in prompt
        assert "UMS" in prompt
