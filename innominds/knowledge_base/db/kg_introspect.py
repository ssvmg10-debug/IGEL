"""Introspect existing knowledge_graph_* tables and build dynamic SQL snippets."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from knowledge_base.db.client import get_conn

logger = logging.getLogger(__name__)

_NODE_TABLE = "knowledge_graph_nodes"
_EDGE_TABLE = "knowledge_graph_edges"


@dataclass
class KGTableLayout:
    nodes_table: str
    edges_table: str
    node_id: str | None
    node_type_col: str | None
    value_col: str | None
    normalized_col: str | None
    parent_chunk_col: str | None
    metadata_node_col: str | None

    edge_id: str | None
    source_col: str | None
    target_col: str | None
    relation_col: str | None
    weight_col: str | None
    metadata_edge_col: str | None


_CACHE: KGTableLayout | None = None
_TABLE_EXISTS: dict[str, bool] = {"nodes": False, "edges": False}


def _first(existing: set[str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in existing:
            return c
    return None


def get_kg_layout(force_refresh: bool = False) -> KGTableLayout | None:
    global _CACHE
    if _CACHE is not None and not force_refresh:
        return _CACHE

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                ([_NODE_TABLE, _EDGE_TABLE],),
            )
            found = {r[0] for r in cur.fetchall()}
            _TABLE_EXISTS["nodes"] = _NODE_TABLE in found
            _TABLE_EXISTS["edges"] = _EDGE_TABLE in found

            if not _TABLE_EXISTS["nodes"]:
                logger.debug("Knowledge graph nodes table missing — KG retrieval disabled.")
                _CACHE = None
                return None

            def cols(table: str) -> set[str]:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table,),
                )
                return {r[0] for r in cur.fetchall()}

            nc = cols(_NODE_TABLE)
            ec = cols(_EDGE_TABLE) if _TABLE_EXISTS["edges"] else set()

    layout = KGTableLayout(
        nodes_table=_NODE_TABLE,
        edges_table=_EDGE_TABLE,
        node_id=_first(nc, ("id", "node_id")),
        node_type_col=_first(nc, ("node_type", "entity_type", "type", "kind")),
        value_col=_first(nc, ("value", "label", "name", "text", "content")),
        normalized_col=_first(nc, ("normalized", "normalized_value", "norm_value")),
        parent_chunk_col=_first(nc, ("parent_chunk_id", "source_parent_chunk_id", "kb_parent_chunk_id")),
        metadata_node_col=_first(nc, ("metadata", "props", "attributes")),
        edge_id=_first(ec, ("id", "edge_id")),
        source_col=_first(ec, ("source_node_id", "source_id", "from_node_id")),
        target_col=_first(ec, ("target_node_id", "target_id", "to_node_id")),
        relation_col=_first(ec, ("relation", "relation_type", "edge_type", "predicate")),
        weight_col=_first(ec, ("weight", "confidence")),
        metadata_edge_col=_first(ec, ("metadata", "props")),
    )

    if not layout.node_id or not layout.value_col:
        logger.warning(
            "knowledge_graph_nodes missing required-like columns (need id-like + text value)."
        )

    _CACHE = layout
    return _CACHE


def tables_available() -> bool:
    lay = get_kg_layout()
    return lay is not None and lay.node_id and lay.value_col


def clear_kg_layout_cache() -> None:
    global _CACHE
    _CACHE = None
