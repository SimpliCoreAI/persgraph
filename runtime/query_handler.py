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
    from second_brain.query import retrieve
    from second_brain.llm import complete_stream
    # Retrieve context
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Searching second brain...", total=None)
        chunks = retrieve(question, top_k=top_k)

    if not chunks:
        console.print("[red]No relevant content found. Try ingesting some documents first.[/red]")
        raise typer.Exit(1)

    # Build prompt
    from second_brain.query import SYSTEM_PROMPT
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("filename", chunk["collection"])
        context_parts.append(f"[{i}] ({source}):\n{chunk['text']}")
    context = "\n\n".join(context_parts)
    prompt = f"{SYSTEM_PROMPT}\n\n### CONTEXT DOCUMENTS:\n{context}\n\n### QUESTION:\n{question}\n\n### ANSWER (based only on the context above):"

    # Stream answer live to terminal
    console.print(f"\n[bold blue]🧠 Answer[/bold blue]\n")
    from second_brain.tracing import trace_event
    trace_event(
        name="query_script_answer",
        input=f"question: {question[:100]}",
        tags=["query", "script", "litellm"]
    )
    response = ""
    for token in complete_stream(prompt, tier="smart"):
        response += token
        print(token, end="", flush=True)
    trace_event(
        name="query_script_answer_result",
        output=f"response_len: {len(response)}",
        tags=["query", "script", "litellm"]
    )
    print("\n")

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
