#!/usr/bin/env python3
"""
Second Brain — Ingest CLI

Usage:
    sb-ingest pdf /path/to/file.pdf --tag financial --tag 2025
    python scripts/ingest.py pdf /path/to/file.pdf
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from second_brain.ingesters import PDFIngester, URLIngester, ObsidianIngester

app = typer.Typer(
    name="sb-ingest",
    help="Ingest documents into your Second Brain.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def pdf(
    path: str = typer.Argument(..., help="Path to PDF file"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Tag (repeatable)"),
) -> None:
    """Ingest a PDF file."""
    ingester = PDFIngester()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"Ingesting {path}...", total=None)
        result = ingester.ingest(path, tags=list(tag))

    if result.success:
        console.print(Panel(
            f"[green]✅ Done![/green]\n\n"
            f"📄 Source: [bold]{result.source}[/bold]\n"
            f"📦 Collection: [bold]{result.collection}[/bold]\n"
            f"✂️  Chunks total: [bold]{result.chunks_total}[/bold]\n"
            f"🆕 Chunks new: [bold]{result.chunks_new}[/bold]\n"
            f"🏷️  Tags: {', '.join(result.tags) or 'none'}",
            title="Ingestion Complete",
        ))
    else:
        for error in result.errors:
            console.print(f"[red]❌ {error}[/red]")
        raise typer.Exit(1)


@app.command()
def url(
    source: str = typer.Argument(..., help="URL to ingest"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Tag (repeatable)"),
) -> None:
    """Ingest a web page by URL."""
    ingester = URLIngester()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"Fetching {source}...", total=None)
        result = ingester.ingest(source, tags=list(tag))

    if result.success:
        console.print(Panel(
            f"[green]✅ Done![/green]\n\n"
            f"🌐 Source: [bold]{result.source}[/bold]\n"
            f"📦 Collection: [bold]{result.collection}[/bold]\n"
            f"✂️  Chunks total: [bold]{result.chunks_total}[/bold]\n"
            f"🆕 Chunks new: [bold]{result.chunks_new}[/bold]\n"
            f"🏷️  Tags: {', '.join(result.tags) or 'none'}",
            title="Ingestion Complete",
        ))
    else:
        for error in result.errors:
            console.print(f"[red]❌ {error}[/red]")
        raise typer.Exit(1)


@app.command()
def obsidian(
    vault: str = typer.Argument(
        default="",
        help="Vault path (default: reads from config.yaml)"
    ),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Extra tag (repeatable)"),
) -> None:
    """Ingest Obsidian vault — incremental, skips unchanged notes."""
    ingester = ObsidianIngester(vault_path=vault if vault else None)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"Scanning vault...", total=None)
        result = ingester.ingest(tags=list(tag) or ["obsidian"])

    if result.success:
        console.print(Panel(
            f"[green]✅ Done![/green]\n\n"
            f"📂 Vault: [bold]{result.source}[/bold]\n"
            f"📦 Collection: [bold]{result.collection}[/bold]\n"
            f"✂️  Chunks total: [bold]{result.chunks_total}[/bold]\n"
            f"🆕 Chunks new: [bold]{result.chunks_new}[/bold]\n"
            f"🏷️  Tags: {', '.join(result.tags) or 'none'}",
            title="Obsidian Ingestion Complete",
        ))
    else:
        for error in result.errors:
            console.print(f"[red]❌ {error}[/red]")
        if not result.success:
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
