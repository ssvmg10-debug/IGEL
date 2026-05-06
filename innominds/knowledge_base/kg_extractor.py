"""
Extract registry keys / TC Setup paths from kb_parent_chunks into knowledge_graph_*.

Targets schema from ensure_knowledge_graph_tables(): UNIQUE(node_type,normalized) on nodes,
UNIQUE(source_node_id,target_node_id,relation) on edges.
"""

from __future__ import annotations

import argparse
import logging
import re

from knowledge_base.config import cfg
from knowledge_base.db.client import close_pool, get_conn, init_pool
from knowledge_base.db.kg_introspect import clear_kg_layout_cache
from knowledge_base.db.schema import ensure_knowledge_graph_tables

logger = logging.getLogger(__name__)

_REGISTRY_RE = re.compile(r"\b(app\.[a-z0-9]+(?:\.[a-z0-9_]+)+)", re.IGNORECASE)
_TC_SETUP_RE = re.compile(
    r"(?:TC\s*)?Setup\s*[>:]\s*((?:[^\n=]+)(?:\s*>\s*[^\n=]+)*(?:\s*=\s*[^\n]+)?)",
    re.IGNORECASE,
)


def _upsert_node(cur, *, node_type: str, value: str, normalized: str, parent_chunk_id: str) -> str | None:
    sql_ins = """
    INSERT INTO knowledge_graph_nodes (node_type, value, normalized, parent_chunk_id)
    VALUES (%s, %s, %s, %s::uuid)
    ON CONFLICT (node_type, normalized) DO UPDATE SET
        value = EXCLUDED.value,
        parent_chunk_id = COALESCE(EXCLUDED.parent_chunk_id, knowledge_graph_nodes.parent_chunk_id)
    RETURNING id::text
    """
    try:
        cur.execute(
            sql_ins,
            (node_type, value[:4000], normalized[:2000], parent_chunk_id),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None
    except Exception:
        sel = """
        SELECT id::text FROM knowledge_graph_nodes
        WHERE node_type = %s AND normalized = %s LIMIT 1
        """
        cur.execute(sel, (node_type, normalized[:2000]))
        found = cur.fetchone()
        if found:
            return str(found[0])
        sql_plain = """
        INSERT INTO knowledge_graph_nodes (node_type, value, normalized, parent_chunk_id)
        VALUES (%s, %s, %s, %s::uuid) RETURNING id::text
        """
        cur.execute(
            sql_plain,
            (node_type, value[:4000], normalized[:2000], parent_chunk_id),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def _link_edge(cur, src: str | None, tgt: str | None, relation: str) -> bool:
    if not src or not tgt or src == tgt:
        return False
    sql = """
    INSERT INTO knowledge_graph_edges (source_node_id, target_node_id, relation)
    VALUES (%s::uuid, %s::uuid, %s)
    ON CONFLICT (source_node_id, target_node_id, relation) DO NOTHING
    """
    try:
        cur.execute(sql, (src, tgt, relation[:200]))
        return cur.rowcount > 0
    except Exception:
        return False


def extract_from_parents(limit: int | None = None, offset: int = 0) -> tuple[int, int]:
    ensure_knowledge_graph_tables()
    clear_kg_layout_cache()

    sql = """
        SELECT id::text, content, section_title FROM kb_parent_chunks
        ORDER BY created_at NULLS LAST, id
    """
    params: list = []
    if limit is not None:
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    node_ops = 0
    edges_ok = 0

    with get_conn() as connection:
        with connection.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

            for pid, content, title in rows:
                blob = f"{title or ''}\n{content}"
                feature_name = (title or "").strip()[:240] or ("section_" + pid[:8])

                fid = _upsert_node(
                    cur,
                    node_type="feature",
                    value=feature_name,
                    normalized=feature_name.lower()[:2000],
                    parent_chunk_id=pid,
                )
                if fid:
                    node_ops += 1

                for m in _REGISTRY_RE.findall(blob):
                    val = m.strip()
                    rid = _upsert_node(
                        cur,
                        node_type="registry_key",
                        value=val,
                        normalized=val.lower(),
                        parent_chunk_id=pid,
                    )
                    if rid:
                        node_ops += 1
                        if fid and _link_edge(cur, fid, rid, "uses"):
                            edges_ok += 1

                for m in _TC_SETUP_RE.findall(blob):
                    path = m.strip()[:2000]
                    if len(path) < 8:
                        continue
                    uid = _upsert_node(
                        cur,
                        node_type="ui_path",
                        value=path,
                        normalized=path.lower()[:2000],
                        parent_chunk_id=pid,
                    )
                    if uid:
                        node_ops += 1
                        if fid and _link_edge(cur, fid, uid, "configured_via"):
                            edges_ok += 1

    return node_ops, edges_ok


def main() -> None:
    logging.basicConfig(level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))
    parser = argparse.ArgumentParser(description="Extract KG entities from kb_parent_chunks.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    init_pool()
    n, e = extract_from_parents(limit=args.limit, offset=args.offset)
    print(f"Done. Node upserts / inserts touched ≈ {n}, new edges inserted ≈ {e}")
    close_pool()


if __name__ == "__main__":
    main()
