"""
Chunk validation — runs before any chunk is written to the database.
Hard failures block insertion. Warnings are logged but allowed through.
"""
import re
from dataclasses import dataclass, field


STEP_PATTERNS = [
    r"^\s*\d+\.\s",
    r"^\s*Step\s*\d+",
    r"^\s*[a-z]\)\s",
    r"^\s*[•\-\*]\s",
    r"^\s*\[\s*\]\s",
    r"(^|\s)(First|Then|Next|Finally|After that|Once|Now),?\s",
]

SENTENCE_ENDINGS = {".", ":", ";", "?", "!", ")", "]", '"', "|", ">"}

IGEL_PRODUCTS = ["UMS", "IGEL OS", "COSMOS", "Cloud Gateway", "ICG", "IMI", "IGEL Cloud"]

CHUNK_TOKEN_LIMITS = {
    "procedure":      (50, 750),
    "concept":        (50, 950),
    "table":          (30, 550),
    "troubleshoot":   (50, 650),
    "configuration":  (50, 750),
    "api":            (30, 650),
    "default":        (50, 950),
}


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate_chunk(content: str, token_count: int, chunk_type: str, metadata: dict) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    stripped = content.strip()
    if not stripped:
        errors.append("EMPTY_CHUNK")
        return ValidationResult(passed=False, errors=errors)

    # 1. Sentence completeness (last char must be a meaningful ending)
    last_char = stripped[-1]
    if last_char not in SENTENCE_ENDINGS:
        errors.append(f"INCOMPLETE_END: chunk ends with '{last_char}' — likely cut mid-sentence")

    # 2. Token size bounds
    min_t, max_t = CHUNK_TOKEN_LIMITS.get(chunk_type, CHUNK_TOKEN_LIMITS["default"])
    if token_count < min_t:
        errors.append(f"TOO_SMALL: {token_count} tokens (min {min_t} for type '{chunk_type}')")
    if token_count > max_t:
        errors.append(f"TOO_LARGE: {token_count} tokens (max {max_t} for type '{chunk_type}')")

    # 3. Step integrity — if steps detected, must have at least 2
    step_matches = _find_steps(stripped)
    if 0 < len(step_matches) < 2:
        errors.append(
            f"ORPHANED_STEP: only 1 step found ('{step_matches[0][:30]}') — "
            "likely cut mid-procedure"
        )

    # 4. Table header presence — if table rows exist, header divider must too
    if "|" in stripped and stripped.count("|") > 4:
        if "---" not in stripped and "===" not in stripped:
            warnings.append("TABLE_NO_HEADER: table rows present without markdown header divider")

    # 5. Mixed product warning
    products_found = [p for p in IGEL_PRODUCTS if p.lower() in stripped.lower()]
    if len(products_found) > 1:
        warnings.append(f"MIXED_PRODUCTS: chunk references {products_found} — consider splitting")

    # 6. Cross-reference flag
    if re.search(r"(see section|refer to section|as described in section|page \d+)", stripped, re.IGNORECASE):
        warnings.append("CROSS_REF: chunk contains a reference to another section")

    return ValidationResult(
        passed=len(errors) == 0,
        warnings=warnings,
        errors=errors,
    )


def validate_coverage(original_token_count: int, chunk_token_counts: list[int]) -> float:
    """
    Ensure chunking didn't lose content.
    Returns coverage ratio. Raises if below 90%.
    """
    if original_token_count == 0:
        return 1.0
    chunked_total = sum(chunk_token_counts)
    ratio = chunked_total / original_token_count
    if ratio < 0.90:
        raise ValueError(
            f"Coverage too low: {ratio:.1%} — {(1 - ratio) * 100:.1f}% of content lost during chunking"
        )
    return ratio


def contains_steps(text: str) -> bool:
    for pattern in STEP_PATTERNS:
        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            return True
    return False


def _find_steps(text: str) -> list[str]:
    matches = []
    for pattern in STEP_PATTERNS[:5]:   # numbered/bullet patterns only
        found = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        matches.extend(found)
    return matches


def classify_chunk_type(text: str, section_title: str = "") -> str:
    title_lower = section_title.lower()
    text_lower = text.lower()

    if contains_steps(text):
        return "procedure"
    if any(w in title_lower for w in ["troubleshoot", "error", "fail", "issue", "problem", "debug"]):
        return "troubleshoot"
    if any(w in title_lower for w in ["configure", "setup", "install", "enable", "disable", "settings"]):
        return "configuration"
    if any(w in text_lower for w in ["api", "endpoint", "request", "response", "curl", "http", "json"]):
        return "api"
    if "|" in text and text.count("|") > 4:
        return "table"
    return "concept"


def detect_product(text: str, file_name: str = "") -> str:
    combined = (text + " " + file_name).lower()
    for product in IGEL_PRODUCTS:
        if product.lower() in combined:
            return product
    return "IGEL"   # default — everything is IGEL-related
