"""
Pluggable cross-encoder reranking for retrieval (after RRF, before budget assembly).

Backends:
  local  — sentence-transformers CrossEncoder
  cohere — Cohere Rerank API
  none   — passthrough (scores inferred from rank order)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from knowledge_base.config import cfg

logger = logging.getLogger(__name__)

_CROSS_ENCODER = None


@dataclass
class RerankItem:
    child_chunk_id: str
    passage: str


def rerank_passages(query: str, items: list[RerankItem]) -> list[tuple[str, float]]:
    """
    Return list of (child_chunk_id, score) sorted by descending relevance.
    Scores normalized roughly to [0, 1] within the batch where applicable.
    """
    if not items:
        return []
    backend = (cfg.RERANKER_BACKEND or "none").lower().strip()

    if backend == "none":
        return _score_by_rank_fallback(items)

    if backend == "cohere":
        return _rerank_cohere(query, items)

    if backend == "local":
        return _rerank_local(query, items)

    logger.warning("Unknown RERANKER_BACKEND=%r; using rank fallback", backend)
    return _score_by_rank_fallback(items)


def _score_by_rank_fallback(items: list[RerankItem]) -> list[tuple[str, float]]:
    n = len(items)
    if n == 0:
        return []
    return [(it.child_chunk_id, 1.0 - (i / max(n, 1))) for i, it in enumerate(items)]


def _normalize_scores(pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if not pairs:
        return []
    vals = [s for _, s in pairs]
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [(cid, 0.5) for cid, _ in pairs]
    return [(cid, (s - lo) / (hi - lo)) for cid, s in pairs]


def _rerank_local(query: str, items: list[RerankItem]) -> list[tuple[str, float]]:
    global _CROSS_ENCODER
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as e:
        logger.error("sentence-transformers not installed: %s", e)
        return _score_by_rank_fallback(items)

    model_name = cfg.RERANKER_MODEL or "cross-encoder/ms-marco-MiniLM-L-6-v2"
    if _CROSS_ENCODER is None:
        logger.info("Loading CrossEncoder model: %s", model_name)
        _CROSS_ENCODER = CrossEncoder(model_name)

    pairs = [(query, it.passage[:8000]) for it in items]
    raw = _CROSS_ENCODER.predict(pairs, show_progress_bar=False)
    scored = [(items[i].child_chunk_id, float(raw[i])) for i in range(len(items))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return _normalize_scores(scored)


def _rerank_cohere(query: str, items: list[RerankItem]) -> list[tuple[str, float]]:
    try:
        import cohere
    except ImportError as e:
        logger.error("cohere package not installed: %s", e)
        return _score_by_rank_fallback(items)

    key = getattr(cfg, "COHERE_API_KEY", "") or ""
    if not key:
        logger.error("COHERE_API_KEY not set — cannot use cohere reranker")
        return _score_by_rank_fallback(items)

    client = cohere.Client(key)
    docs = [it.passage[:8000] for it in items]
    model = getattr(cfg, "COHERE_RERANK_MODEL", None) or "rerank-english-v3.0"
    top_n = min(len(docs), max(len(docs), cfg.RERANKER_TOP_N * 3))
    rsp = client.rerank(model=model, query=query, documents=docs, top_n=top_n)

    out: list[tuple[str, float]] = []
    for r in rsp.results:
        out.append((items[r.index].child_chunk_id, float(r.relevance_score)))
    out.sort(key=lambda x: x[1], reverse=True)
    return _normalize_scores(out)
