"""
IGEL Test Case Generator — CLI Entry Point
==========================================
Usage:
  python -m knowledge_base.generate "Entra ID SSO login validation"
  python -m knowledge_base.generate "UMS profile assignment" --product UMS --format py
  python -m knowledge_base.generate "Device factory reset" --format md --test-id TC015
  python -m knowledge_base.generate --interactive
  python -m knowledge_base.generate --batch "SSO login,UMS profile,factory reset" --format both
  python -m knowledge_base.generate "SSO topic" --debug
"""
import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from knowledge_base.db.client import init_pool, test_connection, close_pool
from knowledge_base.test_generator import (
    generate_test_cases,
    batch_generate,
    DEFAULT_OUTPUT_DIR,
    GeneratedTestCase,
)

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IGEL RAG-Powered Test Case Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "topic", nargs="?",
        help="Test topic (e.g. 'Entra ID SSO login validation')",
    )
    parser.add_argument(
        "--format", choices=["md", "py", "both"], default="both",
        help="Output format: markdown, python, or both (default: both)",
    )
    parser.add_argument(
        "--product",
        choices=["UMS", "IGEL OS", "COSMOS", "ICG", "IMI", "IGEL Cloud"],
        default=None,
        help="Filter KB search by product",
    )
    parser.add_argument(
        "--test-id", dest="test_id", default=None,
        help="Custom test ID e.g. TC015 (auto-generated if omitted)",
    )
    parser.add_argument(
        "--feature", dest="feature_area", default=None,
        help="Allure feature group e.g. 'SSO Validation'",
    )
    parser.add_argument(
        "--top-k", dest="top_k", type=int, default=8,
        help="Number of KB chunks to retrieve (default: 8)",
    )
    parser.add_argument(
        "--output-dir", dest="output_dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Prompt for topic interactively",
    )
    parser.add_argument(
        "--batch", default=None,
        help="Comma-separated list of topics for batch generation",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print full V3 retrieval debug report (scores, ranks, fusion) after generation",
    )

    args = parser.parse_args()

    # ── Header ────────────────────────────────────────────────────────────────
    console.rule("[bold blue]IGEL Test Case Generator[/bold blue]")
    console.print(f"  Knowledge Base  : PostgreSQL @ 192.168.204.65/genai")
    console.print(f"  LLM             : gpt-4.1 (Azure)")
    console.print(f"  Output Dir      : {args.output_dir}")
    console.print()

    # ── DB Connection ─────────────────────────────────────────────────────────
    console.print("[bold]Connecting to PostgreSQL...[/bold] ", end="")
    init_pool()
    if not test_connection():
        console.print("[red]FAILED[/red]")
        console.print("[red]Cannot reach DB. Check knowledge_base/.env settings.[/red]")
        sys.exit(1)

    # ── Dispatch mode ─────────────────────────────────────────────────────────
    try:
        if args.batch:
            topics = [t.strip() for t in args.batch.split(",") if t.strip()]
            if not topics:
                console.print("[red]No valid topics in --batch string.[/red]")
                sys.exit(1)
            _run_batch(topics, args)

        elif args.interactive:
            topic = _prompt_interactive()
            _run_single(topic, args)

        elif args.topic:
            _run_single(args.topic, args)

        else:
            parser.print_help()
            console.print("\n[yellow]Provide a topic, use --interactive, or --batch.[/yellow]")
            sys.exit(0)

    except ValueError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"\n[red]LLM Error:[/red] {e}")
        sys.exit(1)
    finally:
        close_pool()


# ── Single Generation ─────────────────────────────────────────────────────────

def _run_single(topic: str, args: argparse.Namespace) -> None:
    console.print(f"\n[bold]Generating test case for:[/bold] [cyan]{topic}[/cyan]")
    if args.product:
        console.print(f"  Product filter : {args.product}")
    console.print(f"  Format         : {args.format}")
    console.print(f"  top-k          : {args.top_k}")
    console.print()

    with console.status("[bold green]Retrieving KB context and calling GPT-4.1...[/bold green]"):
        result = generate_test_cases(
            topic=topic,
            output_format=args.format,
            product=args.product,
            test_id=args.test_id,
            feature_area=args.feature_area,
            top_k=args.top_k,
            output_dir=args.output_dir,
            debug_retrieval=args.debug,
        )

    _print_result(result, show_debug=args.debug)


# ── Batch Generation ──────────────────────────────────────────────────────────

def _run_batch(topics: list[str], args: argparse.Namespace) -> None:
    console.print(f"\n[bold]Batch mode:[/bold] {len(topics)} topics")
    for i, t in enumerate(topics, 1):
        console.print(f"  {i}. {t}")
    console.print()

    with console.status(f"[bold green]Generating {len(topics)} test cases...[/bold green]"):
        results = batch_generate(
            topics=topics,
            output_format=args.format,
            product=args.product,
            feature_area=args.feature_area,
            top_k=args.top_k,
            output_dir=args.output_dir,
            debug_retrieval=args.debug,
        )

    if args.debug:
        console.print("\n[dim]Batch + --debug: per-topic JSON is attached to each result; "
                      "dumping full reports for all rows can be large. Showing summary only.[/dim]\n")
        for r in results:
            if r.retrieval_debug:
                try:
                    payload = json.loads(r.retrieval_debug)
                    console.print(
                        f"  [bold]{r.test_id}[/bold]  final_chunks={payload.get('final_chunk_count')} "
                        f"kg_nodes={payload.get('kg_nodes_found')} tokens~{payload.get('total_tokens_used')}"
                    )
                except json.JSONDecodeError:
                    console.print(f"  [bold]{r.test_id}[/bold]  [yellow](invalid debug JSON)[/yellow]")

    console.rule("[bold green]Batch Complete[/bold green]")
    summary = Table(title="Batch Results")
    summary.add_column("Test ID")
    summary.add_column("Topic", max_width=40)
    summary.add_column("Chunks", justify="right")
    summary.add_column("Tokens", justify="right")
    summary.add_column("Syntax")
    summary.add_column("Time(s)", justify="right")
    summary.add_column("Status")

    for r in results:
        has_warn = bool(r.warnings)
        status = "[red]FAILED[/red]" if not r.kb_sources else ("[yellow]WARN[/yellow]" if has_warn else "[green]OK[/green]")
        summary.add_row(
            r.test_id, r.topic[:40],
            str(r.kb_chunk_count), str(r.tokens_used),
            "[green]✓[/green]" if r.syntax_valid else "[red]✗[/red]",
            str(r.generation_time_sec), status,
        )
    console.print(summary)


# ── Output Formatting ─────────────────────────────────────────────────────────

def _print_result(r: GeneratedTestCase, *, show_debug: bool = False) -> None:
    console.rule("[bold green]Generation Complete[/bold green]")

    info = Table.grid(padding=(0, 2))
    info.add_row("Test ID",      f"[bold cyan]{r.test_id}[/bold cyan]")
    info.add_row("Feature Area", r.feature_area)
    info.add_row("KB Chunks",    str(r.kb_chunk_count))
    info.add_row("Context Tokens", f"~{r.tokens_used:,}")
    info.add_row("Generation Time", f"{r.generation_time_sec}s")
    info.add_row("Syntax Valid",
                 "[green]YES[/green]" if r.syntax_valid else "[red]NO — saved as .invalid[/red]")
    console.print(info)
    console.print()

    # Files written
    if r.markdown_path:
        console.print(f"  [green]✓[/green] Markdown : {r.markdown_path}")
    if r.python_path:
        console.print(f"  [green]✓[/green] Python   : {r.python_path}")

    # KB sources
    if r.kb_sources:
        console.print("\n  [bold]KB Sources Used:[/bold]")
        for src in r.kb_sources:
            console.print(f"    • {src}")

    # Warnings
    if r.warnings:
        console.print(f"\n  [yellow]Warnings ({len(r.warnings)}):[/yellow]")
        for w in r.warnings[:5]:
            console.print(f"    [yellow]⚠[/yellow] {w}")

    if show_debug and r.retrieval_debug:
        console.print()
        console.rule("[bold magenta]Retrieval Debug (V3)[/bold magenta]")
        try:
            pretty = json.dumps(json.loads(r.retrieval_debug), indent=2)
        except json.JSONDecodeError:
            pretty = r.retrieval_debug
        console.print(Panel(pretty, title="retrieval_debug.json", expand=False))

    console.print()
    console.print(
        "[dim]To run the generated test:[/dim]\n"
        f"  [cyan]pytest {r.python_path} -v --alluredir=reports/allure[/cyan]"
        if r.python_path and r.syntax_valid else ""
    )


# ── Interactive Mode ──────────────────────────────────────────────────────────

def _prompt_interactive() -> str:
    for attempt in range(3):
        try:
            topic = input("\nEnter test topic (e.g. 'Entra ID SSO login validation'): ").strip()
            if topic:
                return topic
            console.print("[yellow]Topic cannot be empty. Try again.[/yellow]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled.[/yellow]")
            sys.exit(0)
    console.print("[red]No topic provided after 3 attempts.[/red]")
    sys.exit(1)


if __name__ == "__main__":
    main()
