"""
Hybrid Knowledge Base Retriever — Vector similarity + PostgreSQL full-text, merged with RRF.

Flow:
  1. Embed query via Azure text-embedding-3-large
  2. Run pgvector cosine similarity search  (top_k * 2 candidates)
  3. Run PostgreSQL plainto_tsquery full-text search (top_k * 2 candidates)
  4. Merge both result sets with Reciprocal Rank Fusion (RRF, k=60)
  5. Deduplicate: keep best-scoring child per parent_chunk_id
  6. Bulk-fetch parent_chunk content (full section, 800-1200 tokens) for LLM context
  7. Return top_k SearchResult objects
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import perf_counter

import psycopg2

from knowledge_base.db.client import get_conn, init_pool
from knowledge_base.embeddings.azure_embedder import embed_single, format_for_pgvector
from knowledge_base.knowledge_graph import (
    KGContext,
    classify_query_style,
    retrieve_kg_context,
)

logger = logging.getLogger(__name__)
_POOL_INITIALISED = False


def _ensure_pool() -> None:
    global _POOL_INITIALISED
    if not _POOL_INITIALISED:
        init_pool()
        _POOL_INITIALISED = True


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    child_chunk_id: str
    parent_chunk_id: str
    document_id: str
    child_content: str
    parent_content: str      # full section text — sent to LLM as context
    section_title: str
    file_name: str
    product: str
    chunk_type: str
    rrf_score: float
    vector_rank: int | None = None
    fts_rank: int | None = None
    rerank_score: float | None = None
    metadata: dict = field(default_factory=dict)


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    top_k: int = 8,
    product: str | None = None,
    chunk_type: str | None = None,
) -> list[SearchResult]:
    """
    Hybrid search returning top_k SearchResult objects with full parent context loaded.

    Args:
        query:      Natural language search query
        top_k:      Number of results to return (after deduplication)
        product:    Optional product filter — "UMS", "IGEL OS", "COSMOS", "ICG", "IMI"
        chunk_type: Optional type filter — "procedure", "concept", "configuration", "table"

    Returns:
        List of SearchResult sorted by rrf_score descending. Empty list if nothing found.
    """
    if not query.strip():
        logger.warning("retrieve() called with empty query")
        return []

    _ensure_pool()

    candidate_limit = top_k * 3   # fetch extra candidates before dedup

    # Step 1: embed query
    query_vec = _embed_query(query)
    vec_available = any(v != 0.0 for v in query_vec)

    # Step 2: vector search (skip if embedding failed)
    vector_rows: list[tuple] = []
    if vec_available:
        try:
            vector_rows = _vector_search(query_vec, candidate_limit, product, chunk_type)
            logger.debug("Vector search returned %d candidates", len(vector_rows))
        except psycopg2.ProgrammingError as e:
            if "vector" in str(e).lower():
                logger.error(
                    "pgvector extension not available. Run: CREATE EXTENSION IF NOT EXISTS vector; "
                    "then re-run knowledge_base.ingest"
                )
            else:
                logger.error("Vector search failed: %s", e)

    # Step 3: full-text search
    fts_rows: list[tuple] = []
    try:
        fts_rows = _fts_search(query, candidate_limit, product, chunk_type)
        logger.debug("FTS search returned %d candidates", len(fts_rows))
    except Exception as e:
        logger.error("FTS search failed: %s", e)

    if not vector_rows and not fts_rows:
        # If product filter was used and both returned nothing, retry without filter
        if product:
            logger.warning(
                "No results for product='%s'. Retrying without product filter.", product
            )
            return retrieve(query, top_k=top_k, product=None, chunk_type=chunk_type)
        logger.warning("No KB results found for query: %r", query)
        return []

    # Step 4: RRF merge
    # Build lookup: child_id -> row metadata (from whichever result set has it)
    row_meta: dict[str, tuple] = {}
    for row in vector_rows + fts_rows:
        child_id = row[0]
        if child_id not in row_meta:
            row_meta[child_id] = row

    vector_ranks = {row[0]: idx + 1 for idx, row in enumerate(vector_rows)}
    fts_ranks    = {row[0]: idx + 1 for idx, row in enumerate(fts_rows)}
    merged = _rrf_merge(vector_ranks, fts_ranks)

    # Step 5: deduplicate by parent_chunk_id (keep highest-scored child per parent)
    child_to_parent = {row[0]: row[1] for row in (vector_rows + fts_rows)}
    merged_dedup = _deduplicate_by_parent(merged, child_to_parent)

    # Take top candidates before fetching parents (avoid unnecessary DB calls)
    top_candidates = merged_dedup[:top_k]

    # Step 6: bulk-fetch parent content
    parent_ids = list({child_to_parent[cid] for cid, _ in top_candidates if cid in child_to_parent})
    parent_data = _fetch_parent_chunks(parent_ids)   # {parent_id: (content, chunk_type)}

    # Step 7: build SearchResult objects
    results: list[SearchResult] = []
    for child_id, rrf_score in top_candidates:
        if child_id not in row_meta:
            continue
        row = row_meta[child_id]
        # row shape: (child_id, parent_id, doc_id, child_content, section_title, file_name, product, rank_pos)
        parent_id = row[1]
        parent_content, parent_chunk_type = parent_data.get(parent_id, ("", "concept"))

        results.append(SearchResult(
            child_chunk_id=child_id,
            parent_chunk_id=parent_id,
            document_id=row[2],
            child_content=row[3],
            parent_content=parent_content,
            section_title=row[4] or "",
            file_name=row[5] or "",
            product=row[6] or "IGEL",
            chunk_type=parent_chunk_type or "concept",
            rrf_score=rrf_score,
            vector_rank=vector_ranks.get(child_id),
            fts_rank=fts_ranks.get(child_id),
        ))

    logger.info(
        "retrieve('%s') → %d results (vec=%d fts=%d dedup=%d)",
        query[:60], len(results), len(vector_rows), len(fts_rows), len(merged_dedup),
    )
    return results


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _embed_query(query: str) -> list[float]:
    try:
        return embed_single(query)
    except Exception as e:
        logger.warning("Embedding failed for query, falling back to FTS only: %s", e)
        from knowledge_base.config import cfg
        return [0.0] * cfg.EMBEDDING_DIM


def _vector_search(
    query_vec: list[float],
    limit: int,
    product: str | None,
    chunk_type: str | None,
) -> list[tuple]:
    vec_literal = format_for_pgvector(query_vec)

    sql = """
        SELECT
            c.id::text,
            c.parent_chunk_id::text,
            c.document_id::text,
            c.content,
            p.section_title,
            d.file_name,
            d.product,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> %s::vector) AS rank_pos
        FROM kb_chunks c
        JOIN kb_parent_chunks p ON c.parent_chunk_id = p.id
        JOIN kb_documents d     ON c.document_id     = d.id
        WHERE c.embedding IS NOT NULL
          AND (%s IS NULL OR d.product ILIKE %s)
          AND (%s IS NULL OR c.chunk_type = %s)
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """
    params = (
        vec_literal,
        product, f"%{product}%" if product else None,
        chunk_type, chunk_type,
        vec_literal,
        limit,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _fts_search(
    query: str,
    limit: int,
    product: str | None,
    chunk_type: str | None,
) -> list[tuple]:
    sql = """
        SELECT
            c.id::text,
            c.parent_chunk_id::text,
            c.document_id::text,
            c.content,
            p.section_title,
            d.file_name,
            d.product,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(
                    to_tsvector('english', c.content),
                    plainto_tsquery('english', %s)
                ) DESC
            ) AS rank_pos
        FROM kb_chunks c
        JOIN kb_parent_chunks p ON c.parent_chunk_id = p.id
        JOIN kb_documents d     ON c.document_id     = d.id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s)
          AND (%s IS NULL OR d.product ILIKE %s)
          AND (%s IS NULL OR c.chunk_type = %s)
        ORDER BY ts_rank_cd(
            to_tsvector('english', c.content),
            plainto_tsquery('english', %s)
        ) DESC
        LIMIT %s
    """
    params = (
        query, query,
        product, f"%{product}%" if product else None,
        chunk_type, chunk_type,
        query,
        limit,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _rrf_merge(
    vector_ranks: dict[str, int],
    fts_ranks: dict[str, int],
    rrf_k: int = 60,
) -> list[tuple[str, float]]:
    all_ids = set(vector_ranks) | set(fts_ranks)
    scores: dict[str, float] = {}
    for cid in all_ids:
        v_score = 1.0 / (vector_ranks.get(cid, 9999) + rrf_k)
        f_score = 1.0 / (fts_ranks.get(cid, 9999) + rrf_k)
        scores[cid] = v_score + f_score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _deduplicate_by_parent(
    merged: list[tuple[str, float]],
    child_to_parent: dict[str, str],
) -> list[tuple[str, float]]:
    seen_parents: set[str] = set()
    deduped: list[tuple[str, float]] = []
    for child_id, score in merged:
        parent_id = child_to_parent.get(child_id, child_id)
        if parent_id not in seen_parents:
            seen_parents.add(parent_id)
            deduped.append((child_id, score))
    return deduped


def _fetch_parent_chunks(parent_ids: list[str]) -> dict[str, tuple[str, str]]:
    if not parent_ids:
        return {}
    sql = """
        SELECT id::text, content, chunk_type
        FROM kb_parent_chunks
        WHERE id = ANY(%s::uuid[])
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (parent_ids,))
            return {row[0]: (row[1], row[2] or "concept") for row in cur.fetchall()}


@dataclass
class RetrievalBundle:
    """V3 retrieval: fused chunks + KG + debug metadata."""
    results: list[SearchResult]
    kg_context: KGContext
    image_block: str
    image_hits: list["ImageHit"]
    debug: "RetrievalDebugReport"


def retrieve_v3(
    query: str,
    top_k: int = 8,
    product: str | None = None,
    chunk_type: str | None = None,
) -> RetrievalBundle:
    """
    Hybrid retrieval with RRF, optional cross-encoder reranking, KG context, fusion, debug traces.
    """
    from knowledge_base.config import cfg
    from knowledge_base.context_fusion import apply_dynamic_budget
    from knowledge_base.reranker import RerankItem, rerank_passages
    from knowledge_base.retrieval_debug import ChunkScoreTrace, RetrievalDebugReport

    timings: dict[str, float] = {}
    debug = RetrievalDebugReport(
        query=query,
        query_classification=classify_query_style(query),
        total_vector_candidates=0,
        total_fts_candidates=0,
        rrf_merged_count=0,
        reranker_applied=(cfg.RERANKER_BACKEND or "").lower().strip() not in ("none", ""),
        post_rerank_count=0,
        kg_nodes_found=0,
        kg_edges_traversed=0,
        final_chunk_count=0,
        total_tokens_used=0,
        token_budget=int(cfg.CONTEXT_TOKEN_BUDGET),
        traces=[],
        timing_ms={},
    )

    if not query.strip():
        return RetrievalBundle(
            results=[],
            kg_context=KGContext("", [], 0, 0),
            image_block="",
            image_hits=[],
            debug=debug,
        )

    _ensure_pool()

    cand_mult = max(3, getattr(cfg, "RETRIEVAL_CANDIDATE_MULTIPLIER", 6))
    candidate_limit = max(top_k * cand_mult, top_k * 3)

    t0 = perf_counter()
    query_vec = _embed_query(query)
    timings["embed_ms"] = (perf_counter() - t0) * 1000
    vec_available = any(v != 0.0 for v in query_vec)

    vector_rows: list[tuple] = []
    if vec_available:
        try:
            t1 = perf_counter()
            vector_rows = _vector_search(query_vec, candidate_limit, product, chunk_type)
            timings["vector_ms"] = (perf_counter() - t1) * 1000
        except psycopg2.ProgrammingError as e:
            if "vector" in str(e).lower():
                logger.error("pgvector not available — check extension: %s", e)
            else:
                logger.error("Vector search failed: %s", e)

    fts_rows = []
    try:
        t2 = perf_counter()
        fts_rows = _fts_search(query, candidate_limit, product, chunk_type)
        timings["fts_ms"] = (perf_counter() - t2) * 1000
    except Exception as e:
        logger.error("FTS search failed: %s", e)

    debug.total_vector_candidates = len(vector_rows)
    debug.total_fts_candidates = len(fts_rows)

    if not vector_rows and not fts_rows:
        if product:
            return retrieve_v3(query, top_k=top_k, product=None, chunk_type=chunk_type)
        return RetrievalBundle(
            results=[],
            kg_context=KGContext("", [], 0, 0),
            image_block="",
            image_hits=[],
            debug=debug,
        )

    row_meta: dict[str, tuple] = {}
    for row in vector_rows + fts_rows:
        cid = row[0]
        if cid not in row_meta:
            row_meta[cid] = row

    vector_ranks = {row[0]: idx + 1 for idx, row in enumerate(vector_rows)}
    fts_ranks = {row[0]: idx + 1 for idx, row in enumerate(fts_rows)}
    merged = _rrf_merge(vector_ranks, fts_ranks)
    debug.rrf_merged_count = len(merged)

    child_to_parent = {row[0]: row[1] for row in (vector_rows + fts_rows)}
    rrf_by_child = dict(merged)

    rerank_take = min(len(merged), max(cfg.RERANKER_TOP_N, top_k * 6))
    pool_pairs = merged[:rerank_take]

    t_rr = perf_counter()
    items = []
    for child_id, _rrf_sc in pool_pairs:
        rw = row_meta.get(child_id)
        passage = rw[3] if rw else ""
        items.append(RerankItem(child_id=child_id, passage=passage[:12000]))

    ranked = rerank_passages(query, items)
    score_map: dict[str, float] = {cid: sc for cid, sc in ranked}
    timings["rerank_ms"] = (perf_counter() - t_rr) * 1000
    debug.post_rerank_count = len(score_map)

    merged_for_sort = sorted(
        pool_pairs,
        key=lambda p: (-score_map.get(p[0], -1e9), -(rrf_by_child.get(p[0], 0.0))),
    )

    merged_dedup = _deduplicate_by_parent(merged_for_sort, child_to_parent)
    prefetch_k = max(top_k * 3, len(merged_dedup))
    shortlist = merged_dedup[: min(prefetch_k, len(merged_dedup))]
    parent_ids_short = [
        child_to_parent[cid] for cid, _ in shortlist if cid in child_to_parent
    ]
    t_fetch = perf_counter()
    parent_data = _fetch_parent_chunks(list(dict.fromkeys(parent_ids_short)))
    timings["parents_ms"] = (perf_counter() - t_fetch) * 1000

    traces: list[ChunkScoreTrace] = []
    for cid, rrfs in merged_for_sort[:rerank_take]:
        row = row_meta.get(cid)
        if row is None:
            continue
        pid = row[1]
        rs = score_map.get(cid)
        traces.append(
            ChunkScoreTrace(
                child_chunk_id=cid,
                parent_chunk_id=pid,
                source_file=row[5] or "",
                section_title=row[4] or "",
                vector_rank=vector_ranks.get(cid),
                fts_rank=fts_ranks.get(cid),
                rrf_score=float(rrf_by_child.get(cid, rrfs)),
                rerank_score=rs,
                included=False,
                exclusion_reason="",
            )
        )

    refined = []
    seen_parent_prefetch: set[str] = set()
    for cid, rrfs in shortlist:
        row = row_meta.get(cid)
        if row is None:
            continue
        pid = row[1]
        if pid in seen_parent_prefetch:
            continue
        seen_parent_prefetch.add(pid)
        pc, ptype = parent_data.get(pid, ("", "concept"))
        refined.append(
            SearchResult(
                child_chunk_id=cid,
                parent_chunk_id=pid,
                document_id=row[2],
                child_content=row[3],
                parent_content=pc,
                section_title=row[4] or "",
                file_name=row[5] or "",
                product=row[6] or "IGEL",
                chunk_type=ptype or "concept",
                rrf_score=float(rrf_by_child.get(cid, rrfs)),
                vector_rank=vector_ranks.get(cid),
                fts_rank=fts_ranks.get(cid),
                rerank_score=score_map.get(cid),
            )
        )

    seed_parents = [r.parent_chunk_id for r in refined[:top_k]]
    kg_ctx = KGContext("", [], 0, 0)
    t_kg = perf_counter()
    if cfg.KG_ENABLED:
        kg_ctx = retrieve_kg_context(
            query,
            max_hops=cfg.KG_MAX_HOPS,
            seed_parent_chunk_ids=seed_parents,
            max_nodes=64,
        )
    timings["kg_ms"] = (perf_counter() - t_kg) * 1000
    debug.kg_nodes_found = kg_ctx.node_count
    debug.kg_edges_traversed = kg_ctx.edge_count

    image_hits: list[ImageHit] = []
    t_img = perf_counter()
    if cfg.CONTEXT_INCLUDE_IMAGES:
        try:
            image_hits = retrieve_images(query, top_k=min(12, max(4, top_k)))
        except Exception as e:
            logger.warning("retrieve_images in v3 skipped: %s", e)
    timings["images_ms"] = (perf_counter() - t_img) * 1000

    fused, kg_trim, img_block, rag_toks = apply_dynamic_budget(
        refined,
        kg_ctx.text_block,
        image_hits,
        token_budget=int(cfg.CONTEXT_TOKEN_BUDGET),
        reserve_prompt=int(cfg.CONTEXT_RESERVE_PROMPT),
        kg_ratio=float(cfg.CONTEXT_KG_BUDGET_RATIO),
        image_ratio=float(cfg.CONTEXT_IMAGE_BUDGET_RATIO),
        min_score=cfg.CONTEXT_MIN_SCORE,
        max_chunks=int(cfg.CONTEXT_MAX_CHUNKS),
    )

    fused_parent_ids = {r.parent_chunk_id for r in fused}
    min_sc = cfg.CONTEXT_MIN_SCORE

    traces_out: list[ChunkScoreTrace] = []
    trace_by_child: dict[str, ChunkScoreTrace] = {}
    for tr in traces:
        trace_by_child.setdefault(tr.child_chunk_id, tr)

    merged_ids_in_order = [p[0] for p in merged_for_sort]
    for cid in merged_ids_in_order:
        base = trace_by_child.get(cid)
        if base is None:
            continue
        incl = base.parent_chunk_id in fused_parent_ids
        if incl:
            why = ""
        elif min_sc is not None and min_sc > 0 and base.rerank_score is not None:
            why = "below_threshold" if base.rerank_score < min_sc else "budget_exceeded"
        else:
            why = "budget_exceeded"

        traces_out.append(
            ChunkScoreTrace(
                child_chunk_id=base.child_chunk_id,
                parent_chunk_id=base.parent_chunk_id,
                source_file=base.source_file,
                section_title=base.section_title,
                vector_rank=base.vector_rank,
                fts_rank=base.fts_rank,
                rrf_score=base.rrf_score,
                rerank_score=base.rerank_score,
                included=incl,
                exclusion_reason=why if not incl else "",
            )
        )
        if len(traces_out) >= 96:
            break

    kg_ctx_out = KGContext(
        text_block=kg_trim,
        node_ids=kg_ctx.node_ids,
        node_count=kg_ctx.node_count,
        edge_count=kg_ctx.edge_count,
    )

    est_total_tokens = int(
        rag_toks
        + len((kg_trim or "").encode("utf-8", errors="ignore")) / 3.8
        + len((img_block or "").encode("utf-8", errors="ignore")) / 3.8
    )

    debug.final_chunk_count = len(fused)
    debug.total_tokens_used = max(est_total_tokens, 1)
    debug.traces = traces_out
    debug.timing_ms = timings

    logger.info(
        "retrieve_v3('%s') → fused=%d kg_nodes=%d rerank=%s",
        query[:60],
        len(fused),
        kg_ctx.node_count,
        debug.reranker_applied,
    )

    return RetrievalBundle(
        results=fused,
        kg_context=kg_ctx_out,
        image_block=img_block,
        image_hits=image_hits,
        debug=debug,
    )


# ── Image retrieval ───────────────────────────────────────────────────────────

@dataclass
class ImageHit:
    image_id: str
    document_id: str
    file_name: str
    page_number: int | None
    section_title: str
    image_type: str
    verbatim_text: str
    semantic_description: str
    test_relevance: str
    score: float                  # cosine similarity (1 - distance)
    fts_rank: int | None = None
    parent_chunk_id: str | None = None
    image_format: str = "png"
    width: int | None = None
    height: int | None = None
    is_recurring: bool = False


def retrieve_images(
    query: str,
    top_k: int = 8,
    document_id: str | None = None,
    exclude_recurring: bool = True,
) -> list[ImageHit]:
    """Hybrid (vector + FTS) search over kb_images.

    Returns image hits with FK to document + nearest section so the caller
    knows exactly which doc/page each image is from.
    """
    if not query.strip():
        return []
    _ensure_pool()

    candidate_limit = top_k * 3
    query_vec = _embed_query(query)
    vec_available = any(v != 0.0 for v in query_vec)

    vector_rows: list[tuple] = []
    fts_rows: list[tuple] = []

    base_select = """
        SELECT
            i.id::text,
            i.document_id::text,
            d.file_name,
            i.page_number,
            COALESCE(p.section_title, '') AS section_title,
            i.image_type,
            COALESCE(i.verbatim_text, '') AS verbatim_text,
            COALESCE(i.semantic_description, '') AS semantic_description,
            COALESCE(i.test_relevance, '') AS test_relevance,
            i.image_format,
            i.width,
            i.height,
            i.parent_chunk_id::text,
            COALESCE((i.metadata->>'is_recurring')::boolean, FALSE) AS is_recurring
    """
    where = """
        WHERE i.description_embedding IS NOT NULL
          AND (%s IS NULL OR i.document_id = %s::uuid)
          AND (NOT %s OR COALESCE((i.metadata->>'is_recurring')::boolean, FALSE) = FALSE)
    """

    if vec_available:
        try:
            vec_literal = format_for_pgvector(query_vec)
            with get_conn() as conn:
                with conn.cursor() as cur:
                    sql = f"""
                        {base_select},
                        1 - (i.description_embedding <=> %s::vector) AS score
                        FROM kb_images i
                        JOIN kb_documents d ON d.id = i.document_id
                        LEFT JOIN kb_parent_chunks p ON p.id = i.parent_chunk_id
                        {where}
                        ORDER BY i.description_embedding <=> %s::vector
                        LIMIT %s
                    """
                    cur.execute(sql, (
                        vec_literal,
                        document_id, document_id,
                        exclude_recurring,
                        vec_literal, candidate_limit,
                    ))
                    vector_rows = cur.fetchall()
        except Exception as e:
            logger.error("Image vector search failed: %s", e)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                sql = f"""
                    {base_select},
                    ts_rank_cd(
                        to_tsvector('english',
                            coalesce(i.verbatim_text,'') || ' ' ||
                            coalesce(i.semantic_description,'') || ' ' ||
                            coalesce(i.surrounding_text,'')),
                        plainto_tsquery('english', %s)
                    ) AS score
                    FROM kb_images i
                    JOIN kb_documents d ON d.id = i.document_id
                    LEFT JOIN kb_parent_chunks p ON p.id = i.parent_chunk_id
                    {where}
                    AND to_tsvector('english',
                            coalesce(i.verbatim_text,'') || ' ' ||
                            coalesce(i.semantic_description,'') || ' ' ||
                            coalesce(i.surrounding_text,''))
                        @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s
                """
                cur.execute(sql, (
                    query,
                    document_id, document_id,
                    exclude_recurring,
                    query, candidate_limit,
                ))
                fts_rows = cur.fetchall()
    except Exception as e:
        logger.error("Image FTS search failed: %s", e)

    # RRF merge of image hits (similar pattern to text)
    vec_ranks = {r[0]: idx + 1 for idx, r in enumerate(vector_rows)}
    fts_ranks_map = {r[0]: idx + 1 for idx, r in enumerate(fts_rows)}
    all_ids = set(vec_ranks) | set(fts_ranks_map)
    rrf_k = 60
    scored = sorted(
        ((iid, 1.0 / (vec_ranks.get(iid, 9999) + rrf_k) +
                1.0 / (fts_ranks_map.get(iid, 9999) + rrf_k))
         for iid in all_ids),
        key=lambda kv: kv[1], reverse=True,
    )

    row_meta: dict[str, tuple] = {}
    for r in vector_rows + fts_rows:
        row_meta.setdefault(r[0], r)

    hits: list[ImageHit] = []
    for iid, rrf_score in scored[:top_k]:
        r = row_meta.get(iid)
        if not r:
            continue
        hits.append(ImageHit(
            image_id=r[0], document_id=r[1], file_name=r[2],
            page_number=r[3], section_title=r[4],
            image_type=r[5] or "unknown",
            verbatim_text=r[6], semantic_description=r[7], test_relevance=r[8],
            image_format=r[9] or "png", width=r[10], height=r[11],
            parent_chunk_id=r[12], is_recurring=bool(r[13]),
            score=rrf_score, fts_rank=fts_ranks_map.get(iid),
        ))
    return hits


def retrieve_image_bytes(image_id: str) -> tuple[bytes, str] | None:
    """Fetch the raw image binary + format for a given image_id (e.g. for display)."""
    _ensure_pool()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT image_bytes, image_format FROM kb_images WHERE id = %s::uuid",
                (image_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return bytes(row[0]), row[1]
