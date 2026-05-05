"""
IGEL Knowledge Base — Document Ingestion Pipeline
==================================================
Usage:
  python -m knowledge_base.ingest               # Ingest all new documents
  python -m knowledge_base.ingest --file x.pdf  # Single file
  python -m knowledge_base.ingest --reset       # Drop + rebuild schema, then ingest all
  python -m knowledge_base.ingest --dry-run     # Parse + chunk without writing to DB
  python -m knowledge_base.ingest --stats       # Show DB statistics and exit
"""
import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table

from knowledge_base.config import cfg
from knowledge_base.db.client import init_pool, test_connection, close_pool
from knowledge_base.db.schema import (
    create_schema, drop_schema, document_exists,
    insert_document, insert_parent_chunk, insert_chunks_batch,
    update_document_counts, get_stats,
)
from knowledge_base.parsers.pdf_parser import parse_pdf
from knowledge_base.parsers.markdown_parser import parse_markdown_file
from knowledge_base.parsers.doc_parser import parse_doc
from knowledge_base.parsers.csv_parser import parse_csv
from knowledge_base.chunking.chunker import chunk_sections
from knowledge_base.chunking.validators import detect_product
from knowledge_base.embeddings.azure_embedder import embed_texts, format_for_pgvector

console = Console()
logging.basicConfig(level=getattr(logging, cfg.LOG_LEVEL), format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── File discovery ────────────────────────────────────────────────────────────

def discover_files(kb_dir: Path, single_file: str | None = None) -> list[Path]:
    if single_file:
        p = kb_dir / single_file
        if not p.exists():
            console.print(f"[red]File not found: {p}[/red]")
            sys.exit(1)
        return [p]

    files = []
    for f in sorted(kb_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in cfg.SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ── Parsing dispatcher ────────────────────────────────────────────────────────

def parse_file(path: Path) -> tuple[list, str]:
    """Returns (sections, parse_method_label)."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(path, cfg.MARKDOWN_OUTPUT_DIR)

    if suffix == ".md":
        return parse_markdown_file(path), "markdown"

    if suffix in (".doc", ".docx"):
        return parse_doc(path), "docx"

    if suffix in (".csv", ".xlsx", ".xls"):
        return parse_csv(path), "csv"

    if suffix == ".mht":
        return _parse_mht(path), "mht"

    raise ValueError(f"No parser for: {suffix}")


def _parse_mht(path: Path) -> list:
    """MHT = MIME HTML archive — extract readable text."""
    from knowledge_base.parsers.markdown_parser import Section
    import re

    raw = path.read_bytes().decode("utf-8", errors="replace")
    # Strip MIME headers and HTML tags
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s{3,}", "\n\n", text).strip()
    return [Section(title=path.stem, level=0, content=text)]


# ── Core ingestion ────────────────────────────────────────────────────────────

def ingest_file(path: Path, dry_run: bool = False) -> dict:
    result = {
        "file": path.name,
        "status": "ok",
        "parse_method": "?",
        "parents": 0,
        "chunks": 0,
        "warnings": 0,
        "skipped": False,
        "error": None,
        "elapsed": 0.0,
    }
    t0 = time.time()

    try:
        # Deduplication check
        fhash = file_hash(path)
        if not dry_run and document_exists(fhash):
            result["status"] = "skipped"
            result["skipped"] = True
            return result

        # Parse
        sections, parse_method = parse_file(path)
        result["parse_method"] = parse_method

        if not sections:
            result["status"] = "empty"
            return result

        # Chunk
        product = detect_product("", path.name)
        parents, warnings = chunk_sections(sections, path.name, product)
        result["parents"] = len(parents)
        result["warnings"] = len(warnings)

        if warnings:
            for w in warnings[:5]:   # log first 5 to avoid noise
                logger.warning(w)

        if dry_run:
            total_children = sum(len(p.children) for p in parents)
            result["chunks"] = total_children
            return result

        # Insert document record
        doc_id = insert_document(
            file_name=path.name,
            file_path=str(path),
            file_type=path.suffix.lower().lstrip("."),
            file_hash=fhash,
            product=product,
            metadata={"parse_method": parse_method, "section_count": len(sections)},
        )

        total_children = 0

        # Insert parent chunks + embed children in batches
        for p_idx, parent in enumerate(parents):
            parent_id = insert_parent_chunk(
                document_id=doc_id,
                chunk_index=p_idx,
                content=parent.content,
                section_title=parent.section_title,
                chunk_type=parent.chunk_type,
                page_number=parent.page_number,
                metadata=parent.metadata,
            )

            if not parent.children:
                continue

            # Collect child texts for batch embedding
            child_texts = [c.content for c in parent.children]
            embeddings = embed_texts(child_texts, batch_size=cfg.BATCH_SIZE)

            rows = []
            for c_idx, (child, embedding) in enumerate(zip(parent.children, embeddings)):
                rows.append({
                    "parent_chunk_id": parent_id,
                    "document_id": doc_id,
                    "chunk_index": total_children + c_idx,
                    "content": child.content,
                    "embedding": format_for_pgvector(embedding),
                    "token_count": child.token_count,
                    "contains_steps": child.contains_steps,
                    "has_table": child.has_table,
                    "chunk_type": child.chunk_type,
                    "metadata": {**child.metadata, "parent_chunk_index": p_idx},
                })

            insert_chunks_batch(rows)
            total_children += len(rows)

        update_document_counts(doc_id, len(parents), total_children)
        result["chunks"] = total_children

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.exception("Failed to ingest %s", path.name)

    result["elapsed"] = round(time.time() - t0, 1)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IGEL Knowledge Base Ingestion Pipeline")
    parser.add_argument("--file", type=str, help="Ingest a single file by name")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate schema before ingesting")
    parser.add_argument("--dry-run", action="store_true", help="Parse + chunk without writing to DB")
    parser.add_argument("--stats", action="store_true", help="Show DB stats and exit")
    args = parser.parse_args()

    console.rule("[bold blue]IGEL Knowledge Base Ingestion Pipeline[/bold blue]")
    console.print(f"  KB directory : {cfg.KB_DIR}")
    console.print(f"  Database     : {cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}")
    console.print(f"  Embeddings   : {cfg.AZURE_EMBEDDING_DEPLOYMENT} ({cfg.EMBEDDING_DIM}d)")
    console.print(f"  Dry run      : {args.dry_run}")
    console.print()

    if not args.dry_run:
        console.print("[bold]Connecting to PostgreSQL...[/bold]")
        init_pool()
        if not test_connection():
            console.print("[red]Cannot connect to database. Check .env settings.[/red]")
            sys.exit(1)

    if args.stats:
        stats = get_stats()
        t = Table(title="Knowledge Base Statistics")
        t.add_column("Metric")
        t.add_column("Value", justify="right")
        for k, v in stats.items():
            t.add_row(k.replace("_", " ").title(), str(v))
        console.print(t)
        close_pool()
        return

    if args.reset and not args.dry_run:
        console.print("[yellow]Resetting schema (drop + recreate)...[/yellow]")
        drop_schema()

    if not args.dry_run:
        console.print("[bold]Initializing schema...[/bold]")
        create_schema()

    files = discover_files(cfg.KB_DIR, args.file)
    console.print(f"\nFound [bold]{len(files)}[/bold] files to process\n")

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=len(files))

        for path in files:
            progress.update(task, description=f"[cyan]{path.name[:50]}[/cyan]")
            r = ingest_file(path, dry_run=args.dry_run)
            results.append(r)
            progress.advance(task)

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold green]Ingestion Complete[/bold green]")

    summary = Table(title="Results Summary")
    summary.add_column("File", style="cyan", max_width=45)
    summary.add_column("Status", justify="center")
    summary.add_column("Method")
    summary.add_column("Parents", justify="right")
    summary.add_column("Chunks", justify="right")
    summary.add_column("Warnings", justify="right")
    summary.add_column("Time(s)", justify="right")

    ok = skipped = errors = total_parents = total_chunks = 0
    for r in results:
        if r["skipped"]:
            skipped += 1
            status_str = "[yellow]SKIP[/yellow]"
        elif r["status"] == "error":
            errors += 1
            status_str = f"[red]ERROR[/red]"
        elif r["status"] == "empty":
            status_str = "[dim]EMPTY[/dim]"
        else:
            ok += 1
            status_str = "[green]OK[/green]"

        total_parents += r["parents"]
        total_chunks += r["chunks"]

        summary.add_row(
            r["file"],
            status_str,
            r["parse_method"],
            str(r["parents"]),
            str(r["chunks"]),
            str(r["warnings"]) if r["warnings"] else "",
            str(r["elapsed"]),
        )

    console.print(summary)
    console.print()
    console.print(f"  Processed : [green]{ok}[/green]  |  Skipped: [yellow]{skipped}[/yellow]  |  Errors: [red]{errors}[/red]")
    console.print(f"  Total parent chunks : {total_parents}")
    console.print(f"  Total child chunks  : {total_chunks} (these are vector-indexed)")

    if not args.dry_run:
        stats = get_stats()
        console.print(f"\n  DB totals → docs: {stats['documents']}  |  parents: {stats['parent_chunks']}  |  chunks: {stats['chunks']}")
        if stats["missing_embeddings"] > 0:
            console.print(f"  [yellow]Warning: {stats['missing_embeddings']} chunks have no embedding[/yellow]")
        close_pool()

    if errors > 0:
        console.print(f"\n[red]{errors} file(s) failed — check logs above for details[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
