"""GraphRAG helpers: query expansion over knowledge_graph_nodes / knowledge_graph_edges."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from knowledge_base.db.client import get_conn
from knowledge_base.db.kg_introspect import get_kg_layout

logger = logging.getLogger(__name__)


@dataclass
class KGContext:
    """Structured graph context fused into prompts."""

    text_block: str
    node_ids: list[str]
    node_count: int
    edge_count: int


def classify_query_style(query: str) -> str:
    if re.search(r"app\.[a-z0-9_.]+", query, re.IGNORECASE):
        return "exact"
    if re.search(r"\b(step|workflow|scenario|procedure)\b", query, re.IGNORECASE):
        return "workflow"
    return "semantic"


def _q(col: str) -> str:
    return '"' + col.replace('"', '""') + '"'


def _search_terms(query: str) -> list[str]:
    q = query.strip()
    keys = re.findall(r"app\.[a-z0-9_.]+", q, flags=re.IGNORECASE)
    tokens = [t for t in re.split(r"[^\w\-./]+", q) if len(t) >= 3]
    out: list[str] = []
    for x in keys + tokens[:12]:
        lx = x.lower()
        if lx not in {y.lower() for y in out}:
            out.append(x)
        if len(out) >= 16:
            break
    return out


def _find_matching_node_ids(
    *,
    lay,
    terms: list[str],
    seed_parent_ids: list[str] | None,
    limit: int,
) -> list[str]:
    if not lay.node_id or not lay.value_col:
        return []

    nid = _q(lay.node_id)
    vcol = _q(lay.value_col)
    tname = _q(lay.nodes_table)

    clauses: list[str] = []
    params: list[object] = []

    pat_clauses: list[str] = []
    for t in terms:
        esc = "%" + t.replace("%", r"\%").replace("_", r"\_") + "%"
        pat_clauses.append(f"{vcol} ILIKE %s")
        params.append(esc)

    if lay.normalized_col:
        ncol = _q(lay.normalized_col)
        for t in terms:
            esc = "%" + t.lower() + "%"
            pat_clauses.append(f"{ncol} ILIKE %s")
            params.append(esc)

    if pat_clauses:
        clauses.append("(" + " OR ".join(pat_clauses) + ")")

    if lay.parent_chunk_col and seed_parent_ids:
        pcol = _q(lay.parent_chunk_col)
        clauses.append(f"{pcol}::uuid = ANY(%s::uuid[])")
        params.append(seed_parent_ids[:512])

    if not clauses:
        return []

    where_sql = "(" + (" OR ".join(clauses)) + ")" if len(clauses) > 1 else clauses[0]
    sql = f"SELECT {nid} FROM {tname} WHERE {where_sql} LIMIT %s"
    params.append(limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [str(r[0]) for r in cur.fetchall()]


def _expand_neighbors(
    layout,
    frontier: list[str],
    *,
    exclude: set[str],
) -> tuple[list[str], int]:
    if (
        not frontier
        or not getattr(layout, "source_col", None)
        or not getattr(layout, "target_col", None)
    ):
        return [], 0

    src_q = _q(layout.source_col)
    tgt_q = _q(layout.target_col)
    tbl = _q(layout.edges_table)

    sql = (
        f"SELECT {src_q}::text, {tgt_q}::text FROM {tbl} WHERE "
        f"{src_q}::uuid = ANY(%s::uuid[]) OR {tgt_q}::uuid = ANY(%s::uuid[])"
    )
    batch = frontier[:512]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (batch, batch))
            rows = cur.fetchall()

    new_neighbors: list[str] = []
    for a, b in rows:
        for nid in (a, b):
            if nid and nid not in exclude:
                new_neighbors.append(str(nid))
                exclude.add(str(nid))
    return new_neighbors, len(rows)


def retrieve_kg_context(
    query: str,
    max_hops: int = 2,
    max_nodes: int = 48,
    seed_parent_chunk_ids: list[str] | None = None,
) -> KGContext:
    """
    Expand around nodes matching query terms (+ optional anchor parent chunks).
    """
    lay = get_kg_layout()
    if lay is None or not lay.node_id or not lay.value_col:
        return KGContext(text_block="", node_ids=[], node_count=0, edge_count=0)

    hops = max(0, min(int(max_hops), 3))
    terms = _search_terms(query)
    seeds_parent = seed_parent_chunk_ids or []

    matched = _find_matching_node_ids(
        lay=lay,
        terms=terms,
        seed_parent_ids=seeds_parent or None,
        limit=max_nodes * 4,
    )

    expanded_ids = list(dict.fromkeys(matched))
    exclude = set(expanded_ids)
    total_edges = 0

    can_expand = (
        hops > 0
        and bool(lay.edges_table)
        and lay.source_col
        and lay.target_col
    )

    frontier = expanded_ids[:]
    for _ in range(hops):
        if not can_expand or not frontier:
            break
        new_nodes, ec = _expand_neighbors(lay, frontier, exclude=exclude)
        total_edges += ec
        frontier = []
        for nid in new_nodes:
            if nid not in expanded_ids and len(expanded_ids) < max_nodes * 4:
                expanded_ids.append(nid)
                frontier.append(nid)
            if len(expanded_ids) >= max_nodes * 4:
                break

    capped = expanded_ids[: max_nodes * 2]
    text_block = _format_nodes_block(lay, capped)

    return KGContext(
        text_block=text_block,
        node_ids=capped,
        node_count=len(expanded_ids),
        edge_count=total_edges,
    )


def _format_nodes_block(layout, node_ids: list[str]) -> str:
    if not node_ids or not layout.node_id or not layout.value_col:
        return ""

    nid = _q(layout.node_id)
    vcol = _q(layout.value_col)
    tname = _q(layout.nodes_table)

    select_list = [nid, vcol]
    head = layout.node_type_col
    norm = layout.normalized_col
    if head:
        select_list.append(_q(head))
    if norm:
        select_list.append(_q(norm))

    sql = (
        "SELECT DISTINCT " + ", ".join(select_list) + " FROM " + tname + " WHERE "
        f"{nid}::uuid = ANY(%s::uuid[])"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (node_ids[:200],))
            rows = cur.fetchall()

    if not rows:
        return ""

    lines = ["—— Knowledge graph entities (relational context) ——"]
    for row in rows:
        cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
        if cells:
            lines.append(" • " + " | ".join(cells[:8]))
    return "\n".join(lines)
