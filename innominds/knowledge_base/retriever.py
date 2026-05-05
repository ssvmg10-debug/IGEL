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

import psycopg2

from knowledge_base.db.client import get_conn, init_pool
from knowledge_base.embeddings.azure_embedder import embed_single, format_for_pgvector

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
