"""Fuse RAG hits, KG text, and image snippets under a dynamic token budget."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge_base.retriever import ImageHit, SearchResult

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 3.8


def _truncate_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated


def _est_tokens(text: str) -> int:
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _format_image_snippets(image_hits: list, max_images: int = 4) -> str:
    lines: list[str] = []
    for h in image_hits[:max_images]:
        lines.append(
            f"[{h.image_type}] ({h.file_name} p.{h.page_number or '?'}) "
            f"{getattr(h, 'semantic_description', '') or ''}\n"
            f"Visible text: {(getattr(h, 'verbatim_text', '') or '')[:800]}\n"
            f"Test hints: {(getattr(h, 'test_relevance', '') or '')[:800]}"
        )
    if not lines:
        return ""
    return "—— Related documentation images ——\n" + "\n\n".join(lines)


def apply_dynamic_budget(
    results: list,
    kg_text: str,
    image_hits: list | None,
    *,
    token_budget: int,
    reserve_prompt: int,
    kg_ratio: float,
    image_ratio: float,
    min_score: float | None,
    max_chunks: int,
) -> tuple[list, str, str, int]:
    """
    Select RAG parent sections + trim KG + images to fit token_budget.
    min_score applies to rerank_score if set, else rrf_score normalized heuristically.

    Returns:
        (selected_SearchResult_list, kg_trimmed, image_block, rag_tokens_used_approx)
    """
    available = max(200, token_budget - reserve_prompt)
    kg_cap = int(available * kg_ratio)
    img_cap = int(available * image_ratio)
    rag_cap = max(200, available - kg_cap - img_cap)

    filtered: list = []
    for r in results:
        score = getattr(r, "rerank_score", None)
        if score is None:
            score = float(getattr(r, "rrf_score", 0.0))
        if min_score is not None and score < min_score:
            continue
        filtered.append(r)

    filtered = filtered[: max(1, max_chunks)]

    selected: list = []
    rag_used = 0
    for r in filtered:
        body = getattr(r, "parent_content", "") or ""
        need = _est_tokens(body)
        if rag_used + need <= rag_cap:
            selected.append(r)
            rag_used += need
        elif rag_cap - rag_used > 150:
            remain = int((rag_cap - rag_used) * _CHARS_PER_TOKEN)
            shortened = _truncate_words(body, max(0, remain))
            import copy as _copy

            cp = _copy.copy(r)
            cp.parent_content = shortened + "\n[...truncated by context budget]"
            selected.append(cp)
            rag_used += _est_tokens(shortened)
            break
        else:
            break

    kg_out = (kg_text or "").strip()
    if kg_out and _est_tokens(kg_out) > kg_cap:
        kg_out = _truncate_words(kg_out, int(kg_cap * _CHARS_PER_TOKEN)) + "\n[...kg truncated]"

    img_block = _format_image_snippets(image_hits or [], max_images=max(1, int(3 + img_cap // 400)))
    if img_block and _est_tokens(img_block) > img_cap:
        img_block = _truncate_words(img_block, int(img_cap * _CHARS_PER_TOKEN)) + "\n[...images truncated]"

    total = rag_used + _est_tokens(kg_out) + _est_tokens(img_block)
    logger.debug(
        "context_fusion: rag_chunks=%d rag_tok~%d kg_tok~%d img_tok~%d budget=%d",
        len(selected),
        rag_used,
        _est_tokens(kg_out),
        _est_tokens(img_block),
        token_budget,
    )

    return selected, kg_out, img_block, rag_used
