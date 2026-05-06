"""Retrieval observability: scores, ranks, inclusion reasons for tuning GraphRAG."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChunkScoreTrace:
    child_chunk_id: str
    parent_chunk_id: str
    source_file: str
    section_title: str
    vector_rank: int | None
    fts_rank: int | None
    rrf_score: float
    rerank_score: float | None
    included: bool
    exclusion_reason: str  # "" when included


@dataclass
class RetrievalDebugReport:
    query: str
    query_classification: str
    total_vector_candidates: int
    total_fts_candidates: int
    rrf_merged_count: int
    reranker_applied: bool
    post_rerank_count: int
    kg_nodes_found: int
    kg_edges_traversed: int
    final_chunk_count: int
    total_tokens_used: int
    token_budget: int
    traces: list[ChunkScoreTrace] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def log_summary(self) -> None:
        logger.info(
            "retrieval_debug: class=%s vec=%d fts=%d rrf_merged=%d rerank=%s "
            "final=%d kg_nodes=%d kg_edges=%d tokens~%d/%d",
            self.query_classification,
            self.total_vector_candidates,
            self.total_fts_candidates,
            self.rrf_merged_count,
            self.reranker_applied,
            self.final_chunk_count,
            self.kg_nodes_found,
            self.kg_edges_traversed,
            self.total_tokens_used,
            self.token_budget,
        )


def merge_traces_into_report(
    base: RetrievalDebugReport,
    traces: list[ChunkScoreTrace],
) -> RetrievalDebugReport:
    base.traces = traces
    return base
