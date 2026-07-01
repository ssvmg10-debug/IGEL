"""Unit tests for knowledge_base.parsers.markdown_parser."""
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from knowledge_base.parsers.markdown_parser import (
    Section,
    parse_markdown_file,
    _split_into_sections,
    _merge_orphan_sections,
    find_markdown_for_pdf,
    _fuzzy_match,
)


# ── _split_into_sections ─────────────────────────────────────────────────────

class TestSplitIntoSections:

    def test_single_section_no_heading(self):
        text = "Just some plain text content.\nAnother line."
        sections = _split_into_sections(text, "source.md")
        assert len(sections) == 1
        assert sections[0].title == "source.md"
        assert sections[0].level == 0
        assert "Just some plain text" in sections[0].content

    def test_h1_heading_splits(self):
        # With orphan merging, small sections get merged into the next one.
        # Use sections with content > 60 chars to avoid merge.
        text = (
            "# First Heading\n"
            + "Content under first heading with enough text to avoid orphan merge easily. " * 2
            + "\n# Second Heading\n"
            + "Content under second heading with enough text to avoid orphan merge easily. " * 2
        )
        sections = _split_into_sections(text, "doc.md")
        assert len(sections) == 2
        titles = [s.title for s in sections]
        assert "First Heading" in titles
        assert "Second Heading" in titles

    def test_multiple_heading_levels(self):
        # Use long content to prevent orphan merging
        text = (
            "# H1\n" + "Some text about the topic that is long enough. " * 3
            + "\n## H2\n" + "More text about the sub-topic that is long enough. " * 3
            + "\n### H3\n" + "Deep text about the sub-sub-topic that is long enough. " * 3
        )
        sections = _split_into_sections(text, "doc.md")
        levels = [s.level for s in sections]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_html_comments_stripped(self):
        text = "<!-- This is a comment -->\n# Heading\nContent."
        sections = _split_into_sections(text, "doc.md")
        for s in sections:
            assert "<!--" not in s.content

    def test_page_hint_from_image_ref(self):
        text = "# Section\nSome text\n![img](images/page_5_img_1.png)\nMore text."
        sections = _split_into_sections(text, "doc.md")
        assert any(s.page_hint == 5 for s in sections)

    def test_empty_sections_filtered(self):
        text = "# Heading\n\n\n# Another Heading\nContent."
        sections = _split_into_sections(text, "doc.md")
        for s in sections:
            assert s.content.strip() != "" or s.title != ""

    def test_h4_heading_detected(self):
        text = "#### Sub-sub-heading\nDeep content."
        sections = _split_into_sections(text, "doc.md")
        assert any(s.level == 4 for s in sections)


# ── _merge_orphan_sections ────────────────────────────────────────────────────

class TestMergeOrphanSections:

    def test_no_orphans(self):
        sections = [
            Section(title="A", level=1, content="A" * 100),
            Section(title="B", level=1, content="B" * 100),
        ]
        merged = _merge_orphan_sections(sections)
        assert len(merged) == 2

    def test_orphan_merged_into_next(self):
        sections = [
            Section(title="Orphan", level=2, content="tiny"),
            Section(title="Full", level=2, content="This is a full section with enough content."),
        ]
        merged = _merge_orphan_sections(sections)
        assert len(merged) == 1
        assert "Orphan" in merged[0].content
        assert "full section" in merged[0].content

    def test_last_section_orphan_kept(self):
        sections = [
            Section(title="Full", level=2, content="A" * 100),
            Section(title="Orphan", level=2, content="tiny"),
        ]
        merged = _merge_orphan_sections(sections)
        assert len(merged) == 2


# ── parse_markdown_file ───────────────────────────────────────────────────────

class TestParseMarkdownFile:

    def test_parse_real_file(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "# Title\n" + "First paragraph content that is long enough to avoid merge. " * 3
            + "\n## Subtitle\n" + "Second paragraph content that is long enough. " * 3,
            encoding="utf-8"
        )
        sections = parse_markdown_file(md)
        assert len(sections) >= 2
        titles = [s.title for s in sections]
        assert "Title" in titles
        assert "Subtitle" in titles


# ── find_markdown_for_pdf ─────────────────────────────────────────────────────

class TestFindMarkdownForPdf:

    def test_exact_match(self, tmp_path):
        md_dir = tmp_path / "markdown_output"
        sub = md_dir / "My_Document"
        sub.mkdir(parents=True)
        md_file = sub / "My Document.md"
        md_file.write_text("# Hello", encoding="utf-8")
        result = find_markdown_for_pdf("My Document.pdf", md_dir)
        assert result == md_file

    def test_no_match_returns_none(self, tmp_path):
        md_dir = tmp_path / "markdown_output"
        md_dir.mkdir()
        assert find_markdown_for_pdf("nonexistent.pdf", md_dir) is None

    def test_fuzzy_match_by_folder(self, tmp_path):
        md_dir = tmp_path / "markdown_output"
        sub = md_dir / "igel_guide"
        sub.mkdir(parents=True)
        md_file = sub / "igel_guide.md"
        md_file.write_text("# Guide", encoding="utf-8")
        result = find_markdown_for_pdf("IGEL Guide.pdf", md_dir)
        assert result == md_file


# ── _fuzzy_match ──────────────────────────────────────────────────────────────

class TestFuzzyMatch:

    def test_case_insensitive(self):
        assert _fuzzy_match("Hello", "hello")

    def test_underscore_space_equivalence(self):
        assert _fuzzy_match("my_document", "My Document")

    def test_dash_ignored(self):
        assert _fuzzy_match("igel-guide", "IGEL Guide")

    def test_substring_match(self):
        assert _fuzzy_match("guide", "igel_guide_v2")

    def test_no_match(self):
        assert not _fuzzy_match("apples", "oranges")
