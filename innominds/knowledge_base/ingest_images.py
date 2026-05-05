"""
IGEL Knowledge Base — Image Ingestion Pipeline
==============================================
Iterates over every document already ingested into kb_documents, extracts
embedded images, runs them through GPT-4.1 Vision for verbatim + semantic
description, embeds the combined context, and links each image back to:

  • its source document (kb_documents.id, hard FK, ON DELETE CASCADE)
  • the nearest text section (kb_parent_chunks.id, soft FK)

Idempotent at the document level: a document already covered (has ≥1 row in
kb_images) is skipped unless --force is passed.

Usage:
  python -m knowledge_base.ingest_images                   # all docs
  python -m knowledge_base.ingest_images --document NAME   # single doc by file_name
  python -m knowledge_base.ingest_images --force           # re-process even covered docs
  python -m knowledge_base.ingest_images --stats           # show image stats and exit
  python -m knowledge_base.ingest_images --limit N         # process at most N docs
"""
import argparse
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
    create_schema, get_stats,
    insert_image, find_nearest_parent_chunk,
    list_documents_for_image_pass, document_has_images,
)
from knowledge_base.parsers.image_extractor import extract_images
from knowledge_base.embeddings.azure_embedder import embed_texts, format_for_pgvector
from knowledge_base.vision.image_describer import describe_image, build_embedding_text

console = Console()
logging.basicConfig(level=getattr(logging, cfg.LOG_LEVEL), format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Quiet down noisy HTTP loggers from openai/httpx during long runs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


def get_section_title_for_chunk(parent_chunk_id: str | None) -> str:
    """Look up section_title for the nearest parent chunk (best-effort)."""
    if not parent_chunk_id:
        return ""
    from knowledge_base.db.client import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT section_title FROM kb_parent_chunks WHERE id = %s",
                (parent_chunk_id,)
            )
            row = cur.fetchone()
            return (row[0] if row and row[0] else "") or ""


def ingest_one_document(doc: dict, force: bool = False) -> dict:
    result = {
        "file": doc["file_name"],
        "status": "ok",
        "extracted": 0,
        "described": 0,
        "inserted": 0,
        "errors": 0,
        "elapsed": 0.0,
    }
    t0 = time.time()

    # Skip if already covered
    if not force and document_has_images(doc["id"]):
        result["status"] = "skipped"
        return result

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        # Fall back to KB_DIR
        candidate = cfg.KB_DIR / doc["file_name"]
        if candidate.exists():
            file_path = candidate
        else:
            result["status"] = "missing_file"
            return result

    try:
        images = extract_images(file_path)
    except Exception as e:
        logger.exception("extract_images failed for %s", file_path.name)
        result["status"] = "extract_error"
        result["errors"] += 1
        result["elapsed"] = round(time.time() - t0, 1)
        return result

    result["extracted"] = len(images)
    if not images:
        result["status"] = "no_images"
        result["elapsed"] = round(time.time() - t0, 1)
        return result

    # Process images: describe + embed + insert
    embed_texts_buffer: list[str] = []
    pending: list[dict] = []   # accumulate metadata to insert after batch embedding

    from knowledge_base.vision.image_describer import ImageDescription

    for img in images:
        parent_chunk_id = find_nearest_parent_chunk(doc["id"], img.page_number)
        section_title = get_section_title_for_chunk(parent_chunk_id)

        if img.is_recurring:
            # Recurring header/logo/footer — describe ONCE per unique image (already
            # deduped by hash), but with a cheap, fixed description so we don't burn
            # vision tokens on the same logo. Binary is still preserved.
            desc = ImageDescription(
                image_type="recurring_header_or_logo",
                verbatim_text="",
                ui_elements=[],
                semantic_description=(
                    f"Recurring page element appearing on {len(img.occurrence_pages)} of "
                    f"the document's pages (e.g. header, footer, logo, watermark). "
                    f"First seen on page {img.page_number}."
                ),
                test_relevance="Reference image only",
                raw_json={"recurring": True, "occurrence_pages": img.occurrence_pages},
            )
        else:
            try:
                desc = describe_image(
                    image_bytes=img.image_bytes,
                    image_format=img.image_format,
                    document_name=doc["file_name"],
                    section_title=section_title,
                    page_number=img.page_number,
                    caption=img.caption,
                    surrounding_text=img.surrounding_text,
                )
            except Exception as e:
                logger.exception("describe_image failed for %s img#%d", file_path.name, img.sequence_index)
                result["errors"] += 1
                continue

            if desc.error:
                result["errors"] += 1
            else:
                result["described"] += 1

        embed_text = build_embedding_text(
            desc, doc["file_name"], section_title, img.page_number,
            img.caption, img.surrounding_text,
        )

        embed_texts_buffer.append(embed_text)
        pending.append({
            "img": img,
            "desc": desc,
            "parent_chunk_id": parent_chunk_id,
            "section_title": section_title,
            "embed_text": embed_text,
        })

    # Batch-embed all images for this document
    if not pending:
        result["status"] = "no_described"
        result["elapsed"] = round(time.time() - t0, 1)
        return result

    try:
        embeddings = embed_texts(embed_texts_buffer, batch_size=cfg.BATCH_SIZE)
    except Exception as e:
        logger.exception("embed_texts failed for %s", file_path.name)
        result["status"] = "embed_error"
        result["errors"] += len(pending)
        result["elapsed"] = round(time.time() - t0, 1)
        return result

    # Insert
    for p, embedding in zip(pending, embeddings):
        img = p["img"]
        desc = p["desc"]
        try:
            insert_image(
                document_id=doc["id"],
                parent_chunk_id=p["parent_chunk_id"],
                sequence_index=img.sequence_index,
                page_number=img.page_number,
                bbox=img.bbox,
                image_hash=img.image_hash,
                image_format=img.image_format,
                width=img.width,
                height=img.height,
                image_bytes=img.image_bytes,
                image_type=desc.image_type,
                verbatim_text=desc.verbatim_text,
                ui_elements=desc.ui_elements,
                semantic_description=desc.semantic_description,
                test_relevance=desc.test_relevance,
                surrounding_text=img.surrounding_text,
                caption=img.caption,
                description_embedding=format_for_pgvector(embedding),
                metadata={
                    "section_title": p["section_title"],
                    "raw_response": desc.raw_json,
                    "describer_error": desc.error,
                    "occurrence_pages": img.occurrence_pages,
                    "is_recurring": img.is_recurring,
                },
            )
            result["inserted"] += 1
        except Exception as e:
            logger.exception("insert_image failed for %s img#%d", file_path.name, img.sequence_index)
            result["errors"] += 1

    result["elapsed"] = round(time.time() - t0, 1)
    return result


def main():
    parser = argparse.ArgumentParser(description="IGEL Knowledge Base — image ingestion pass")
    parser.add_argument("--document", type=str, help="Single document by file_name")
    parser.add_argument("--force", action="store_true", help="Re-process docs that already have images")
    parser.add_argument("--stats", action="store_true", help="Show image stats and exit")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N documents")
    args = parser.parse_args()

    console.rule("[bold blue]IGEL KB — Image Ingestion[/bold blue]")
    console.print(f"  Database     : {cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}")
    console.print(f"  Vision LLM   : {cfg.AZURE_DEPLOYMENT}")
    console.print(f"  Embeddings   : {cfg.AZURE_EMBEDDING_DEPLOYMENT} ({cfg.EMBEDDING_DIM}d)")
    console.print()

    init_pool()
    if not test_connection():
        console.print("[red]Cannot connect to database[/red]")
        sys.exit(1)
    create_schema()  # idempotent — ensures kb_images table exists

    if args.stats:
        s = get_stats()
        t = Table(title="KB Stats")
        for k, v in s.items():
            t.add_row(k.replace("_", " ").title(), str(v))
        console.print(t)
        close_pool()
        return

    docs = list_documents_for_image_pass()
    if args.document:
        docs = [d for d in docs if d["file_name"] == args.document]
        if not docs:
            console.print(f"[red]No document found with file_name={args.document}[/red]")
            sys.exit(1)
    if args.limit:
        docs = docs[: args.limit]

    console.print(f"Found [bold]{len(docs)}[/bold] documents to process\n")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Image ingest...", total=len(docs))

        for d in docs:
            progress.update(task, description=f"[cyan]{d['file_name'][:60]}[/cyan]")
            r = ingest_one_document(d, force=args.force)
            results.append(r)
            progress.advance(task)

    # Summary
    console.print()
    console.rule("[bold green]Image Ingest Complete[/bold green]")
    summary = Table(title="Per-Document Image Stats")
    summary.add_column("File", style="cyan", max_width=45)
    summary.add_column("Status", justify="center")
    summary.add_column("Extracted", justify="right")
    summary.add_column("Described", justify="right")
    summary.add_column("Inserted", justify="right")
    summary.add_column("Errors", justify="right")
    summary.add_column("Time(s)", justify="right")

    total_extracted = total_inserted = total_errors = 0
    skipped = no_images = ok = 0
    for r in results:
        status = r["status"]
        if status == "skipped":
            status_str = "[yellow]SKIP[/yellow]"; skipped += 1
        elif status == "no_images":
            status_str = "[dim]NONE[/dim]"; no_images += 1
        elif status == "ok":
            status_str = "[green]OK[/green]"; ok += 1
        else:
            status_str = f"[red]{status.upper()}[/red]"

        total_extracted += r["extracted"]
        total_inserted += r["inserted"]
        total_errors += r["errors"]

        summary.add_row(
            r["file"], status_str,
            str(r["extracted"]), str(r["described"]), str(r["inserted"]),
            str(r["errors"]) if r["errors"] else "",
            str(r["elapsed"]),
        )

    console.print(summary)
    console.print()
    console.print(f"  Processed: [green]{ok}[/green]  |  Skipped: [yellow]{skipped}[/yellow]  |  No images: [dim]{no_images}[/dim]")
    console.print(f"  Total extracted: {total_extracted}  |  Inserted: {total_inserted}  |  Errors: {total_errors}")

    s = get_stats()
    console.print(f"\n  DB totals -> images: {s['images']}  |  missing embeddings: {s['images_missing_embeddings']}")
    close_pool()


if __name__ == "__main__":
    main()
