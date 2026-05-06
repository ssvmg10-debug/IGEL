"""
Creates and manages the PostgreSQL schema for the IGEL Knowledge Base.
Tables:
  kb_documents     - one row per source file
  kb_parent_chunks - large sections (800-1200 tokens), returned as context
  kb_chunks        - small indexed units (150-300 tokens) with vector embeddings
"""
from knowledge_base.db.client import get_conn
from knowledge_base.config import cfg

_SCHEMA_SQL = f"""
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Source documents registry
CREATE TABLE IF NOT EXISTS kb_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_hash       TEXT UNIQUE NOT NULL,
    product         TEXT,
    total_parent_chunks INT DEFAULT 0,
    total_chunks    INT DEFAULT 0,
    ingested_at     TIMESTAMP DEFAULT NOW(),
    metadata        JSONB DEFAULT '{{}}'::jsonb
);

-- Parent chunks: full sections returned during retrieval for full context
CREATE TABLE IF NOT EXISTS kb_parent_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    section_title   TEXT,
    chunk_type      TEXT,
    page_number     INT,
    metadata        JSONB DEFAULT '{{}}'::jsonb,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Child chunks: indexed for vector + full-text search
CREATE TABLE IF NOT EXISTS kb_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_chunk_id UUID NOT NULL REFERENCES kb_parent_chunks(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       VECTOR({cfg.EMBEDDING_DIM}),
    token_count     INT,
    contains_steps  BOOLEAN DEFAULT FALSE,
    has_table       BOOLEAN DEFAULT FALSE,
    chunk_type      TEXT,
    metadata        JSONB DEFAULT '{{}}'::jsonb,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Note: no ANN index on `embedding` — text-embedding-3-large is 3072-dim,
-- which exceeds pgvector's 2000-dim cap for IVFFlat/HNSW with vector_cosine_ops.
-- For this corpus size (~100 docs, a few thousand chunks) sequential scan
-- via vector_cosine_ops operator class is fast enough. If we ever exceed
-- ~50k chunks, switch to halfvec(3072) + HNSW (4000-dim cap).

-- Full-text search index (BM25-style fallback)
CREATE INDEX IF NOT EXISTS kb_chunks_fts_idx
    ON kb_chunks USING gin(to_tsvector('english', content));

-- Lookup indexes
CREATE INDEX IF NOT EXISTS kb_chunks_doc_idx      ON kb_chunks(document_id);
CREATE INDEX IF NOT EXISTS kb_chunks_parent_idx   ON kb_chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS kb_chunks_type_idx     ON kb_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS kb_parent_doc_idx      ON kb_parent_chunks(document_id);
CREATE INDEX IF NOT EXISTS kb_docs_hash_idx       ON kb_documents(file_hash);
CREATE INDEX IF NOT EXISTS kb_docs_product_idx    ON kb_documents(product);

-- ─────────────────────────────────────────────────────────────────────────────
-- Images table: every image extracted from any source document.
-- Hard FK to kb_documents (cascades on doc delete) and soft FK to nearest section.
-- Stores binary + multiple text representations (OCR-grade verbatim + semantic).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_images (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id        UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    parent_chunk_id    UUID REFERENCES kb_parent_chunks(id) ON DELETE SET NULL,

    -- Position / identity
    page_number        INT,
    sequence_index     INT NOT NULL,                  -- order across the whole document
    bbox               JSONB,                         -- {{x0,y0,x1,y1}} on page (PDFs)
    image_hash         TEXT NOT NULL,                 -- sha256 of bytes (per-document, not globally unique)
    image_format       TEXT NOT NULL,                 -- png, jpeg, etc.
    width              INT,
    height             INT,
    image_bytes        BYTEA NOT NULL,                -- raw image preserved

    -- Captured text representations (no context loss)
    image_type         TEXT,                          -- ui_screenshot, diagram, photo, icon, ...
    verbatim_text      TEXT,                          -- every visible label/button/value
    ui_elements        JSONB,                         -- structured controls + state
    semantic_description TEXT,                        -- 2-4 sentence narrative
    test_relevance     TEXT,                          -- what test cases this illustrates
    surrounding_text   TEXT,                          -- paragraph above/below in source doc
    caption            TEXT,                          -- explicit caption if any

    -- Vector embedding of the combined description (for similarity search)
    description_embedding VECTOR({cfg.EMBEDDING_DIM}),

    metadata           JSONB DEFAULT '{{}}'::jsonb,
    created_at         TIMESTAMP DEFAULT NOW(),

    UNIQUE (document_id, sequence_index)              -- per-doc dedup; same image in different docs ok
);

CREATE INDEX IF NOT EXISTS kb_images_doc_idx        ON kb_images(document_id);
CREATE INDEX IF NOT EXISTS kb_images_parent_idx     ON kb_images(parent_chunk_id);
CREATE INDEX IF NOT EXISTS kb_images_page_idx       ON kb_images(document_id, page_number);
CREATE INDEX IF NOT EXISTS kb_images_hash_idx       ON kb_images(image_hash);
CREATE INDEX IF NOT EXISTS kb_images_fts_idx
    ON kb_images USING gin(to_tsvector('english',
        coalesce(verbatim_text,'') || ' ' ||
        coalesce(semantic_description,'') || ' ' ||
        coalesce(surrounding_text,'')));
"""

_KG_GRAPH_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_type       TEXT NOT NULL,
    value           TEXT NOT NULL,
    normalized      TEXT NOT NULL DEFAULT '',
    metadata        JSONB DEFAULT '{}'::jsonb,
    parent_chunk_id UUID REFERENCES kb_parent_chunks(id) ON DELETE SET NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (node_type, normalized)
);

CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_node_id  UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_node_id  UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL DEFAULT 'related_to',
    weight          DOUBLE PRECISION DEFAULT 1.0,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (source_node_id, target_node_id, relation)
);

CREATE INDEX IF NOT EXISTS ix_kgn_chunk ON knowledge_graph_nodes(parent_chunk_id);
CREATE INDEX IF NOT EXISTS ix_kgn_type ON knowledge_graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS ix_kgn_norm ON knowledge_graph_nodes(normalized);
CREATE INDEX IF NOT EXISTS ix_kge_src ON knowledge_graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS ix_kge_tgt ON knowledge_graph_edges(target_node_id);
"""


def ensure_knowledge_graph_tables() -> None:
    """Create KG tables if absent. Safe when tables were pre-created with different DDL."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_KG_GRAPH_SQL)
    try:
        from knowledge_base.db.kg_introspect import clear_kg_layout_cache
        clear_kg_layout_cache()
    except Exception:
        pass




def create_schema() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
    ensure_knowledge_graph_tables()
    print("  Schema ready (kb_documents, kb_parent_chunks, kb_chunks, knowledge_graph_*)")


def drop_schema() -> None:
    """Full reset — drops all KB tables. Use only for clean re-ingestion."""
    sql = """
    DROP TABLE IF EXISTS kb_chunks CASCADE;
    DROP TABLE IF EXISTS kb_parent_chunks CASCADE;
    DROP TABLE IF EXISTS kb_documents CASCADE;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("  Schema dropped.")


def document_exists(file_hash: str) -> str | None:
    """Return document id if already ingested, else None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM kb_documents WHERE file_hash = %s",
                (file_hash,)
            )
            row = cur.fetchone()
            return str(row[0]) if row else None


def insert_document(
    file_name: str,
    file_path: str,
    file_type: str,
    file_hash: str,
    product: str,
    metadata: dict,
) -> str:
    sql = """
    INSERT INTO kb_documents (file_name, file_path, file_type, file_hash, product, metadata)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
    RETURNING id
    """
    import json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (file_name, file_path, file_type, file_hash, product, json.dumps(metadata)))
            return str(cur.fetchone()[0])


def insert_parent_chunk(
    document_id: str,
    chunk_index: int,
    content: str,
    section_title: str,
    chunk_type: str,
    page_number: int,
    metadata: dict,
) -> str:
    sql = """
    INSERT INTO kb_parent_chunks (document_id, chunk_index, content, section_title, chunk_type, page_number, metadata)
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
    RETURNING id
    """
    import json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                document_id, chunk_index, content, section_title,
                chunk_type, page_number, json.dumps(metadata)
            ))
            return str(cur.fetchone()[0])


def insert_chunks_batch(rows: list[dict]) -> None:
    """Batch insert child chunks with embeddings."""
    import json
    from psycopg2.extras import execute_values

    sql = """
    INSERT INTO kb_chunks
        (parent_chunk_id, document_id, chunk_index, content, embedding,
         token_count, contains_steps, has_table, chunk_type, metadata)
    VALUES %s
    """
    values = [
        (
            r["parent_chunk_id"],
            r["document_id"],
            r["chunk_index"],
            r["content"],
            r["embedding"],
            r["token_count"],
            r["contains_steps"],
            r["has_table"],
            r["chunk_type"],
            json.dumps(r["metadata"]),
        )
        for r in rows
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values, template=None, page_size=50)


def update_document_counts(document_id: str, parent_count: int, chunk_count: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE kb_documents SET total_parent_chunks=%s, total_chunks=%s WHERE id=%s",
                (parent_count, chunk_count, document_id)
            )


def get_stats() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kb_documents")
            docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM kb_parent_chunks")
            parents = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM kb_chunks")
            chunks = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM kb_chunks WHERE embedding IS NULL")
            missing_emb = cur.fetchone()[0]
            try:
                cur.execute("SELECT COUNT(*) FROM kb_images")
                images = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM kb_images WHERE description_embedding IS NULL")
                images_missing_emb = cur.fetchone()[0]
            except Exception:
                images, images_missing_emb = 0, 0
    return {
        "documents": docs,
        "parent_chunks": parents,
        "chunks": chunks,
        "missing_embeddings": missing_emb,
        "images": images,
        "images_missing_embeddings": images_missing_emb,
    }


# ── Image helpers ─────────────────────────────────────────────────────────────

def insert_image(
    document_id: str,
    parent_chunk_id: str | None,
    sequence_index: int,
    page_number: int | None,
    bbox: dict | None,
    image_hash: str,
    image_format: str,
    width: int | None,
    height: int | None,
    image_bytes: bytes,
    image_type: str,
    verbatim_text: str,
    ui_elements: list | dict | None,
    semantic_description: str,
    test_relevance: str,
    surrounding_text: str,
    caption: str | None,
    description_embedding: str,
    metadata: dict,
) -> str:
    import json
    sql = """
    INSERT INTO kb_images (
        document_id, parent_chunk_id, sequence_index, page_number, bbox,
        image_hash, image_format, width, height, image_bytes,
        image_type, verbatim_text, ui_elements, semantic_description,
        test_relevance, surrounding_text, caption,
        description_embedding, metadata
    ) VALUES (
        %s, %s, %s, %s, %s::jsonb,
        %s, %s, %s, %s, %s,
        %s, %s, %s::jsonb, %s,
        %s, %s, %s,
        %s, %s::jsonb
    )
    ON CONFLICT (document_id, sequence_index) DO UPDATE SET
        parent_chunk_id      = EXCLUDED.parent_chunk_id,
        page_number          = EXCLUDED.page_number,
        bbox                 = EXCLUDED.bbox,
        image_hash           = EXCLUDED.image_hash,
        image_format         = EXCLUDED.image_format,
        width                = EXCLUDED.width,
        height               = EXCLUDED.height,
        image_bytes          = EXCLUDED.image_bytes,
        image_type           = EXCLUDED.image_type,
        verbatim_text        = EXCLUDED.verbatim_text,
        ui_elements          = EXCLUDED.ui_elements,
        semantic_description = EXCLUDED.semantic_description,
        test_relevance       = EXCLUDED.test_relevance,
        surrounding_text     = EXCLUDED.surrounding_text,
        caption              = EXCLUDED.caption,
        description_embedding = EXCLUDED.description_embedding,
        metadata             = EXCLUDED.metadata
    RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                document_id, parent_chunk_id, sequence_index, page_number,
                json.dumps(bbox) if bbox else None,
                image_hash, image_format, width, height, image_bytes,
                image_type, verbatim_text,
                json.dumps(ui_elements) if ui_elements is not None else None,
                semantic_description, test_relevance, surrounding_text, caption,
                description_embedding,
                json.dumps(metadata),
            ))
            return str(cur.fetchone()[0])


def find_nearest_parent_chunk(document_id: str, page_number: int | None) -> str | None:
    """Return the kb_parent_chunks.id whose page_number is closest to the given page,
    so an image can be linked to the most relevant section."""
    if page_number is None:
        # Just pick the first parent chunk for this document
        sql = "SELECT id FROM kb_parent_chunks WHERE document_id = %s ORDER BY chunk_index ASC LIMIT 1"
        params = (document_id,)
    else:
        sql = """
        SELECT id FROM kb_parent_chunks
        WHERE document_id = %s
        ORDER BY ABS(COALESCE(page_number, 0) - %s) ASC, chunk_index ASC
        LIMIT 1
        """
        params = (document_id, page_number)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return str(row[0]) if row else None


def list_documents_for_image_pass() -> list[dict]:
    """Documents already ingested as text — for the image pass to iterate over."""
    sql = """
    SELECT id, file_name, file_path, file_type
    FROM kb_documents
    ORDER BY ingested_at ASC
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [
                {"id": str(r[0]), "file_name": r[1], "file_path": r[2], "file_type": r[3]}
                for r in cur.fetchall()
            ]


def document_has_images(document_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM kb_images WHERE document_id = %s LIMIT 1", (document_id,))
            return cur.fetchone() is not None
