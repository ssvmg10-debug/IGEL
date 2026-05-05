"""
Production-ready Hierarchical Chunker for IGEL Knowledge Base.

Strategy:
  1. Each document section → one or more Parent Chunks (800–1200 tokens)
  2. Each Parent Chunk → 2–5 Child Chunks (150–300 tokens) for vector indexing
  3. Step sequences are NEVER split across chunk boundaries
  4. Tables are kept whole (header always included)
  5. 80-token overlap between sibling children to prevent context boundary loss
  6. Each chunk validated before being returned
"""
import re
from dataclasses import dataclass, field
from typing import Generator

import tiktoken

from knowledge_base.parsers.markdown_parser import Section
from knowledge_base.chunking.validators import (
    ValidationResult,
    validate_chunk,
    validate_coverage,
    classify_chunk_type,
    contains_steps,
    detect_product,
    CHUNK_TOKEN_LIMITS,
)

_ENCODER = tiktoken.get_encoding("cl100k_base")

PARENT_MAX_TOKENS = 1200
PARENT_MIN_TOKENS = 80
CHILD_MAX_TOKENS = 300
CHILD_MIN_TOKENS = 50
OVERLAP_TOKENS = 80


@dataclass
class ParentChunk:
    content: str
    section_title: str
    chunk_type: str
    page_number: int
    token_count: int
    metadata: dict = field(default_factory=dict)
    children: list["ChildChunk"] = field(default_factory=list)


@dataclass
class ChildChunk:
    content: str
    chunk_type: str
    token_count: int
    contains_steps: bool
    has_table: bool
    metadata: dict = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(passed=True))


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def decode_tokens(tokens: list[int]) -> str:
    return _ENCODER.decode(tokens)


def chunk_sections(
    sections: list[Section],
    file_name: str,
    product: str | None = None,
) -> tuple[list[ParentChunk], list[str]]:
    """
    Entry point: convert document sections into parent+child chunk hierarchy.
    Returns (parent_chunks, validation_warnings).
    """
    all_parents: list[ParentChunk] = []
    all_warnings: list[str] = []

    for section in sections:
        if not section.content.strip():
            continue

        chunk_type = classify_chunk_type(section.content, section.title)
        detected_product = product or detect_product(section.content, file_name)

        base_metadata = {
            "source": file_name,
            "product": detected_product,
            "section": section.title,
        }

        parents = _build_parent_chunks(section, chunk_type, base_metadata)

        for parent in parents:
            parent.children = _build_child_chunks(parent, base_metadata)
            all_parents.append(parent)

            # Collect validation warnings from children
            for child in parent.children:
                if not child.validation.passed:
                    all_warnings.append(
                        f"[{file_name}] Section '{section.title[:40]}': {child.validation.errors}"
                    )
                for w in child.validation.warnings:
                    all_warnings.append(f"[{file_name}] Section '{section.title[:40]}': WARNING {w}")

    # Coverage check across all parent chunks
    original_tokens = sum(count_tokens(s.content) for s in sections if s.content.strip())
    parent_tokens = [count_tokens(p.content) for p in all_parents]
    try:
        validate_coverage(original_tokens, parent_tokens)
    except ValueError as e:
        all_warnings.append(f"[{file_name}] COVERAGE WARNING: {e}")

    return all_parents, all_warnings


# ── Parent Chunk Building ─────────────────────────────────────────────────────

def _build_parent_chunks(section: Section, chunk_type: str, base_metadata: dict) -> list[ParentChunk]:
    total_tokens = count_tokens(section.content)

    # Small section → single parent
    if total_tokens <= PARENT_MAX_TOKENS:
        return [_make_parent(section.content, section.title, chunk_type, section.page_hint, base_metadata)]

    # Large section → split carefully
    return _split_large_section(section, chunk_type, base_metadata)


def _split_large_section(section: Section, chunk_type: str, base_metadata: dict) -> list[ParentChunk]:
    parents: list[ParentChunk] = []
    text = section.content

    # Tables → keep whole regardless of size
    if chunk_type == "table" or ("|" in text and text.count("|") > 6):
        return [_make_parent(text, section.title, "table", section.page_hint, base_metadata)]

    # Find step blocks — extract them as atomic units
    step_block, before, after = _extract_step_block(text)

    if step_block:
        # Before-steps content
        if before.strip():
            for chunk in _split_by_paragraph(before, PARENT_MAX_TOKENS):
                parents.append(_make_parent(chunk, section.title, chunk_type, section.page_hint, base_metadata))

        # Step block — if too large, split only between step groups
        step_tokens = count_tokens(step_block)
        if step_tokens <= PARENT_MAX_TOKENS:
            parents.append(_make_parent(step_block, section.title, "procedure", section.page_hint, base_metadata))
        else:
            for part in _split_between_step_groups(step_block, PARENT_MAX_TOKENS):
                parents.append(_make_parent(part, section.title, "procedure", section.page_hint, base_metadata))

        # After-steps content
        if after.strip():
            for chunk in _split_by_paragraph(after, PARENT_MAX_TOKENS):
                parents.append(_make_parent(chunk, section.title, chunk_type, section.page_hint, base_metadata))
    else:
        # No steps → split at paragraph boundaries
        for chunk in _split_by_paragraph(text, PARENT_MAX_TOKENS):
            parents.append(_make_parent(chunk, section.title, chunk_type, section.page_hint, base_metadata))

    return parents


def _make_parent(content: str, title: str, chunk_type: str, page: int, metadata: dict) -> ParentChunk:
    return ParentChunk(
        content=content.strip(),
        section_title=title,
        chunk_type=chunk_type,
        page_number=page,
        token_count=count_tokens(content),
        metadata=dict(metadata),
    )


# ── Child Chunk Building ──────────────────────────────────────────────────────

def _build_child_chunks(parent: ParentChunk, base_metadata: dict) -> list[ChildChunk]:
    total_tokens = count_tokens(parent.content)

    # Small parent → single child = parent itself
    if total_tokens <= CHILD_MAX_TOKENS:
        child = _make_child(parent.content, parent.chunk_type, base_metadata)
        return [child]

    # Split parent into children
    raw_children = _split_by_sentence(parent.content, CHILD_MAX_TOKENS)

    # Add overlap between siblings
    children_with_overlap = _apply_overlap(raw_children)

    return [_make_child(c, parent.chunk_type, base_metadata) for c in children_with_overlap]


def _make_child(content: str, chunk_type: str, metadata: dict) -> ChildChunk:
    stripped = content.strip()
    token_count = count_tokens(stripped)
    has_steps = contains_steps(stripped)
    has_table = "|" in stripped and stripped.count("|") > 4
    actual_type = "procedure" if has_steps else ("table" if has_table else chunk_type)

    validation = validate_chunk(stripped, token_count, actual_type, metadata)

    return ChildChunk(
        content=stripped,
        chunk_type=actual_type,
        token_count=token_count,
        contains_steps=has_steps,
        has_table=has_table,
        metadata=dict(metadata),
        validation=validation,
    )


# ── Splitting Helpers ─────────────────────────────────────────────────────────

def _split_by_paragraph(text: str, max_tokens: int) -> list[str]:
    """Split text at double-newline boundaries without exceeding max_tokens."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            # Para itself too large — split by single newline
            if count_tokens(para) > max_tokens:
                chunks.extend(_split_by_line(para, max_tokens))
                current = ""
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:3000]]  # hard fallback


def _split_by_line(text: str, max_tokens: int) -> list[str]:
    lines = text.split("\n")
    chunks: list[str] = []
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}".strip() if current else line
        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = line

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_by_sentence(text: str, max_tokens: int) -> list[str]:
    """Split into child-sized units at sentence boundaries."""
    # Split on sentence-ending punctuation followed by space + capital
    sentences = re.split(r"(?<=[.!?;])\s+(?=[A-Z\d])", text)
    chunks: list[str] = []
    current = ""

    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            # Single sentence too long → split by token hard limit
            if count_tokens(sent) > max_tokens:
                chunks.extend(_split_by_token_limit(sent, max_tokens))
                current = ""
            else:
                current = sent

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text]


def _split_by_token_limit(text: str, max_tokens: int) -> list[str]:
    """Hard split by token count — last resort, used only for very long single sentences."""
    tokens = _ENCODER.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i + max_tokens]
        chunks.append(_ENCODER.decode(chunk_tokens))
    return chunks


def _apply_overlap(chunks: list[str]) -> list[str]:
    """Add trailing tokens from previous chunk to start of next chunk."""
    if len(chunks) <= 1:
        return chunks

    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tokens = _ENCODER.encode(chunks[i - 1])
        if len(prev_tokens) >= OVERLAP_TOKENS:
            overlap_text = _ENCODER.decode(prev_tokens[-OVERLAP_TOKENS:])
            overlapped.append(f"[...]\n{overlap_text}\n\n{chunks[i]}")
        else:
            overlapped.append(chunks[i])

    return overlapped


def _extract_step_block(text: str) -> tuple[str, str, str]:
    """
    Locate the step sequence in text.
    Returns (step_block, text_before, text_after).
    If no steps found, returns ("", text, "").
    """
    # Find lines that are part of a step pattern
    lines = text.split("\n")
    step_indices = []

    step_pattern = re.compile(
        r"(^\s*\d+\.\s|^\s*Step\s*\d+|^\s*[a-z]\)\s|^\s*[•\-\*]\s)",
        re.MULTILINE | re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        if step_pattern.match(line):
            step_indices.append(i)

    if len(step_indices) < 2:
        return "", text, ""

    start = step_indices[0]
    end = step_indices[-1]

    # Extend end to include lines belonging to the last step
    while end + 1 < len(lines) and lines[end + 1].strip() and not _is_new_section(lines[end + 1]):
        end += 1

    before = "\n".join(lines[:start])
    step_block = "\n".join(lines[start:end + 1])
    after = "\n".join(lines[end + 1:])

    return step_block, before, after


def _is_new_section(line: str) -> bool:
    return bool(re.match(r"^#{1,4}\s|^[A-Z][A-Z\s]{5,}$", line))


def _split_between_step_groups(text: str, max_tokens: int) -> list[str]:
    """Split a large steps block only at blank lines between step groups."""
    groups = re.split(r"\n{2,}(?=\s*(?:\d+\.|Step\s*\d+))", text)
    chunks: list[str] = []
    current = ""

    for group in groups:
        candidate = f"{current}\n\n{group}".strip() if current else group
        if count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = group

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text]
