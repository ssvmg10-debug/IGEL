"""Unit tests for knowledge_base.chunking.validators."""
import pytest

from knowledge_base.chunking.validators import (
    ValidationResult,
    validate_chunk,
    validate_coverage,
    contains_steps,
    classify_chunk_type,
    detect_product,
    CHUNK_TOKEN_LIMITS,
    SENTENCE_ENDINGS,
)


# ── validate_chunk ────────────────────────────────────────────────────────────

class TestValidateChunk:

    def test_empty_content_fails(self):
        result = validate_chunk("", 0, "concept", {})
        assert not result.passed
        assert "EMPTY_CHUNK" in result.errors

    def test_whitespace_only_fails(self):
        result = validate_chunk("   \n\t  ", 0, "concept", {})
        assert not result.passed
        assert "EMPTY_CHUNK" in result.errors

    def test_valid_concept_chunk(self):
        content = "This is a valid concept chunk about IGEL OS configuration."
        result = validate_chunk(content, 100, "concept", {})
        assert result.passed
        assert result.errors == []

    def test_incomplete_end_detected(self):
        content = "This sentence is cut off mid"
        result = validate_chunk(content, 100, "concept", {})
        assert any("INCOMPLETE_END" in e for e in result.errors)

    def test_valid_endings_accepted(self):
        for ending in SENTENCE_ENDINGS:
            content = f"Some content here{ending}"
            result = validate_chunk(content, 100, "concept", {})
            assert not any("INCOMPLETE_END" in e for e in result.errors), (
                f"Ending '{ending}' should be accepted"
            )

    def test_too_small_chunk(self):
        content = "Short."
        result = validate_chunk(content, 10, "concept", {})
        assert any("TOO_SMALL" in e for e in result.errors)

    def test_too_large_chunk(self):
        content = "A very long chunk." + " word" * 200
        result = validate_chunk(content, 1000, "concept", {})
        assert any("TOO_LARGE" in e for e in result.errors)

    def test_token_bounds_per_type(self):
        for chunk_type, (min_t, max_t) in CHUNK_TOKEN_LIMITS.items():
            result_small = validate_chunk("x.", min_t - 1, chunk_type, {})
            assert any("TOO_SMALL" in e for e in result_small.errors)

            result_large = validate_chunk("x.", max_t + 1, chunk_type, {})
            assert any("TOO_LARGE" in e for e in result_large.errors)

    def test_orphaned_step_detected(self):
        content = "1. First step only."
        result = validate_chunk(content, 100, "procedure", {})
        assert any("ORPHANED_STEP" in e for e in result.errors)

    def test_multiple_steps_pass(self):
        content = "1. First step.\n2. Second step."
        result = validate_chunk(content, 100, "procedure", {})
        assert not any("ORPHANED_STEP" in e for e in result.errors)

    def test_table_without_header_warning(self):
        content = "| A | B |\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |"
        result = validate_chunk(content, 100, "table", {})
        assert any("TABLE_NO_HEADER" in w for w in result.warnings)

    def test_table_with_header_no_warning(self):
        content = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        result = validate_chunk(content, 100, "table", {})
        assert not any("TABLE_NO_HEADER" in w for w in result.warnings)

    def test_mixed_products_warning(self):
        content = "UMS manages IGEL OS and Cloud Gateway devices."
        result = validate_chunk(content, 100, "concept", {})
        assert any("MIXED_PRODUCTS" in w for w in result.warnings)

    def test_single_product_no_warning(self):
        content = "UMS is the management server."
        result = validate_chunk(content, 100, "concept", {})
        assert not any("MIXED_PRODUCTS" in w for w in result.warnings)

    def test_cross_reference_warning(self):
        content = "For more info, see section 3.2."
        result = validate_chunk(content, 100, "concept", {})
        assert any("CROSS_REF" in w for w in result.warnings)

    def test_no_cross_reference(self):
        content = "This chunk is self-contained."
        result = validate_chunk(content, 100, "concept", {})
        assert not any("CROSS_REF" in w for w in result.warnings)


# ── validate_coverage ─────────────────────────────────────────────────────────

class TestValidateCoverage:

    def test_full_coverage(self):
        ratio = validate_coverage(1000, [500, 500])
        assert ratio == 1.0

    def test_high_coverage_passes(self):
        ratio = validate_coverage(1000, [950])
        assert ratio >= 0.90

    def test_low_coverage_raises(self):
        with pytest.raises(ValueError, match="Coverage too low"):
            validate_coverage(1000, [100])

    def test_zero_original_returns_one(self):
        ratio = validate_coverage(0, [])
        assert ratio == 1.0

    def test_overlap_above_one(self):
        ratio = validate_coverage(100, [120])
        assert ratio > 1.0


# ── contains_steps ────────────────────────────────────────────────────────────

class TestContainsSteps:

    def test_numbered_list(self):
        assert contains_steps("1. Do something\n2. Do another")

    def test_step_keyword(self):
        assert contains_steps("Step 1: Open the app")

    def test_lettered_list(self):
        assert contains_steps("a) First option")

    def test_bullet_list(self):
        assert contains_steps("- Install the package")
        assert contains_steps("* Start the service")

    def test_sequential_keywords(self):
        assert contains_steps("First, open the terminal")
        assert contains_steps("Then run the command")

    def test_plain_text_no_steps(self):
        assert not contains_steps("This is plain text about IGEL OS.")


# ── classify_chunk_type ───────────────────────────────────────────────────────

class TestClassifyChunkType:

    def test_procedure_by_steps(self):
        assert classify_chunk_type("1. Do this\n2. Do that", "") == "procedure"

    def test_troubleshoot_by_title(self):
        assert classify_chunk_type("Some text", "Troubleshooting Guide") == "troubleshoot"

    def test_configuration_by_title(self):
        assert classify_chunk_type("Some text", "Configure Network Settings") == "configuration"

    def test_api_by_content(self):
        assert classify_chunk_type("Use the REST API endpoint to get data", "") == "api"

    def test_table_by_content(self):
        assert classify_chunk_type("| A | B | C |\n| 1 | 2 | 3 |", "") == "table"

    def test_concept_fallback(self):
        assert classify_chunk_type("General information about the product.", "") == "concept"

    def test_error_title_is_troubleshoot(self):
        assert classify_chunk_type("text", "Common Error Messages") == "troubleshoot"

    def test_install_title_is_configuration(self):
        assert classify_chunk_type("text", "Install IGEL OS") == "configuration"


# ── detect_product ────────────────────────────────────────────────────────────

class TestDetectProduct:

    def test_detect_ums(self):
        assert detect_product("Configure the UMS server", "") == "UMS"

    def test_detect_igel_os(self):
        assert detect_product("Install IGEL OS on the device", "") == "IGEL OS"

    def test_detect_from_filename(self):
        assert detect_product("some text", "COSMOS_guide.pdf") == "COSMOS"

    def test_default_igel(self):
        assert detect_product("Generic text", "generic.pdf") == "IGEL"

    def test_detect_icg(self):
        assert detect_product("Connect through the ICG proxy", "") == "ICG"
