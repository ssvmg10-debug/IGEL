"""Unit tests for knowledge_base.chunking.chunker."""
import pytest

from knowledge_base.parsers.markdown_parser import Section
from knowledge_base.chunking.chunker import (
    count_tokens,
    decode_tokens,
    chunk_sections,
    _split_by_paragraph,
    _split_by_line,
    _split_by_sentence,
    _split_by_token_limit,
    _apply_overlap,
    _extract_step_block,
    _is_new_section,
    _split_between_step_groups,
    _make_parent,
    _make_child,
    PARENT_MAX_TOKENS,
    CHILD_MAX_TOKENS,
    OVERLAP_TOKENS,
)


# ── count_tokens / decode_tokens ──────────────────────────────────────────────

class TestTokenCounting:

    def test_count_empty(self):
        assert count_tokens("") == 0

    def test_count_short_text(self):
        tokens = count_tokens("hello world")
        assert tokens >= 2

    def test_roundtrip(self):
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        text = "The quick brown fox."
        encoded = enc.encode(text)
        decoded = decode_tokens(encoded)
        assert decoded == text


# ── _split_by_paragraph ───────────────────────────────────────────────────────

class TestSplitByParagraph:

    def test_small_text_single_chunk(self):
        text = "Short paragraph."
        chunks = _split_by_paragraph(text, 500)
        assert len(chunks) == 1
        assert chunks[0] == "Short paragraph."

    def test_splits_at_double_newline(self):
        # Each paragraph needs to exceed the token limit when combined
        text = "Para one is a long enough paragraph. " * 5 + "\n\n" + "Para two is also long enough. " * 5
        chunks = _split_by_paragraph(text, 20)
        assert len(chunks) >= 2

    def test_no_empty_chunks(self):
        text = "A.\n\nB.\n\nC."
        chunks = _split_by_paragraph(text, 500)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_respects_max_tokens(self):
        paras = ["Word " * 50 + "." for _ in range(10)]
        text = "\n\n".join(paras)
        chunks = _split_by_paragraph(text, 100)
        for chunk in chunks:
            assert count_tokens(chunk) <= 100 + 10  # small tolerance for edge cases


# ── _split_by_line ────────────────────────────────────────────────────────────

class TestSplitByLine:

    def test_small_text_single_chunk(self):
        text = "Line one.\nLine two."
        chunks = _split_by_line(text, 500)
        assert len(chunks) == 1

    def test_splits_at_newline(self):
        lines = ["Line " + str(i) + "." for i in range(20)]
        text = "\n".join(lines)
        chunks = _split_by_line(text, 20)
        assert len(chunks) >= 2


# ── _split_by_sentence ────────────────────────────────────────────────────────

class TestSplitBySentence:

    def test_short_text_single_chunk(self):
        text = "One sentence."
        chunks = _split_by_sentence(text, 500)
        assert len(chunks) == 1

    def test_splits_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = _split_by_sentence(text, 10)
        assert len(chunks) >= 2

    def test_preserves_all_content(self):
        text = "A. B. C. D."
        chunks = _split_by_sentence(text, 500)
        rejoined = " ".join(chunks)
        assert "A." in rejoined
        assert "D." in rejoined


# ── _split_by_token_limit ─────────────────────────────────────────────────────

class TestSplitByTokenLimit:

    def test_short_text_single_chunk(self):
        text = "short"
        chunks = _split_by_token_limit(text, 100)
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        text = "word " * 500
        chunks = _split_by_token_limit(text, 50)
        assert len(chunks) > 1
        for chunk in chunks[:-1]:
            assert count_tokens(chunk) <= 50


# ── _apply_overlap ────────────────────────────────────────────────────────────

class TestApplyOverlap:

    def test_single_chunk_unchanged(self):
        chunks = ["Only one chunk."]
        result = _apply_overlap(chunks)
        assert result == chunks

    def test_overlap_added(self):
        # Previous chunk needs >= OVERLAP_TOKENS tokens for overlap to kick in
        first_chunk = "First chunk. " + "The quick brown fox jumps over the lazy dog. " * 20
        chunks = [first_chunk, "Second chunk."]
        result = _apply_overlap(chunks)
        assert len(result) == 2
        assert result[0] == chunks[0]
        assert "[...]" in result[1]

    def test_empty_list(self):
        assert _apply_overlap([]) == []


# ── _extract_step_block ───────────────────────────────────────────────────────

class TestExtractStepBlock:

    def test_extracts_numbered_steps(self):
        text = "Introduction.\n1. First step.\n2. Second step.\nConclusion."
        step_block, before, after = _extract_step_block(text)
        assert "1. First step" in step_block
        assert "2. Second step" in step_block
        assert "Introduction" in before

    def test_no_steps_returns_empty(self):
        text = "Plain text with no steps at all."
        step_block, before, after = _extract_step_block(text)
        assert step_block == ""
        assert before == text

    def test_bullet_steps_detected(self):
        text = "Intro.\n- Step one.\n- Step two.\nEnd."
        step_block, before, after = _extract_step_block(text)
        assert "- Step one" in step_block
        assert "- Step two" in step_block


# ── _is_new_section ───────────────────────────────────────────────────────────

class TestIsNewSection:

    def test_markdown_heading(self):
        assert _is_new_section("# Heading") is True
        assert _is_new_section("## Sub Heading") is True

    def test_all_caps_heading(self):
        assert _is_new_section("CONFIGURATION GUIDE") is True

    def test_normal_text(self):
        assert _is_new_section("This is a regular line.") is False

    def test_short_caps_not_heading(self):
        assert _is_new_section("OK") is False


# ── _split_between_step_groups ────────────────────────────────────────────────

class TestSplitBetweenStepGroups:

    def test_small_block_single_chunk(self):
        text = "1. Step one.\n2. Step two."
        chunks = _split_between_step_groups(text, 500)
        assert len(chunks) == 1

    def test_large_block_splits(self):
        groups = []
        for i in range(1, 20):
            groups.append(f"{i}. Step {i} with some details about the procedure.")
        text = "\n\n".join(groups)
        chunks = _split_between_step_groups(text, 30)
        assert len(chunks) >= 2


# ── chunk_sections (integration) ──────────────────────────────────────────────

class TestChunkSections:

    def test_single_small_section(self):
        sections = [Section(
            title="Test Section",
            level=1,
            content="This is a test section with enough content to be valid. " * 5,
            page_hint=1,
        )]
        parents, warnings = chunk_sections(sections, "test.md")
        assert len(parents) >= 1
        assert parents[0].section_title == "Test Section"
        assert parents[0].token_count > 0

    def test_empty_section_skipped(self):
        sections = [
            Section(title="Empty", level=1, content="", page_hint=1),
            Section(title="Full", level=1, content="Valid content here. " * 10, page_hint=1),
        ]
        parents, _ = chunk_sections(sections, "test.md")
        titles = [p.section_title for p in parents]
        assert "Empty" not in titles
        assert "Full" in titles

    def test_children_created_for_large_parent(self):
        long_content = "This is a sentence about IGEL OS configuration. " * 100
        sections = [Section(title="Large", level=1, content=long_content, page_hint=1)]
        parents, _ = chunk_sections(sections, "test.md")
        assert any(len(p.children) > 1 for p in parents)

    def test_metadata_propagated(self):
        sections = [Section(
            title="Meta Test",
            level=2,
            content="Content about UMS configuration. " * 10,
            page_hint=3,
        )]
        parents, _ = chunk_sections(sections, "guide.md", product="UMS")
        assert parents[0].metadata["source"] == "guide.md"
        assert parents[0].metadata["product"] == "UMS"
        assert parents[0].page_number == 3

    def test_returns_warnings_list(self):
        sections = [Section(
            title="Test",
            level=1,
            content="Short.",
            page_hint=1,
        )]
        _, warnings = chunk_sections(sections, "test.md")
        assert isinstance(warnings, list)
