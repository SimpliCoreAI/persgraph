#!/usr/bin/env python3
"""
Second Brain — Query CLI

Usage:
    sb-query "What are my portfolio returns for 2025?"
    python scripts/query.py "Summarize my dental appointments"
"""

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from second_brain.query import answer

app = typer.Typer(
    name="sb-query",
    help="Query your Second Brain.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def query(
    question: str = typer.Argument(..., help="Your question"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of chunks to retrieve"),
) -> None:
    """Ask your Second Brain a question."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Thinking...", total=None)
        response, chunks = answer(question, top_k=top_k)

    # Print answer
    console.print(Panel(Markdown(response), title="🧠 Answer", border_style="blue"))

    # Print sources
    if chunks:
        table = Table(title="📚 Sources", show_lines=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("File", style="cyan")
        table.add_column("Collection", style="magenta")
        table.add_column("Relevance", justify="right", style="green")

        for i, chunk in enumerate(chunks, 1):
            table.add_row(
                str(i),
                chunk["metadata"].get("filename", "—"),
                chunk["collection"],
                f"{chunk['score']:.2f}",
            )

        console.print(table)


if __name__ == "__main__":
    app()
