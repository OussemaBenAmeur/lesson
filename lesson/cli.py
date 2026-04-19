"""Typer CLI for the lesson package.

Entry point: `lesson` (configured in pyproject.toml).
Supplements the markdown slash commands for standalone use and testing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="lesson",
    help="Algorithmic knowledge graph extraction from AI debugging sessions.",
    no_args_is_help=True,
)
console = Console()


def _get_session_manager(cwd: Path | None = None):
    from lesson.session import SessionManager
    return SessionManager(cwd or Path.cwd())


# ------------------------------------------------------------------
# lesson start
# ------------------------------------------------------------------

@app.command()
def start(
    goal: str = typer.Argument(..., help="Session goal — what you're trying to fix/build"),
    notes: str = typer.Option("", "--notes", "-n", help="Additional context for lesson generation"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
):
    """Start a new lesson tracking session."""
    sm = _get_session_manager(cwd)
    if sm.active_slug():
        console.print(f"[yellow]Active session already exists: {sm.active_slug()}[/yellow]")
        raise typer.Exit(1)
    slug = sm.create(goal=goal, notes=notes)
    console.print(f"[green]✓[/green] Started session [bold]{slug}[/bold]")
    console.print(f"  goal: {goal}")
    console.print(f"  dir:  {sm.session_dir(slug)}")


# ------------------------------------------------------------------
# lesson compress
# ------------------------------------------------------------------

@app.command()
def compress(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
    threshold: float = typer.Option(0.25, "--threshold", "-t", help="Significance score cutoff"),
    no_embed: bool = typer.Option(False, "--no-embed", help="Disable semantic deduplication"),
):
    """Run algorithmic compression on the current session's arc.jsonl."""
    from lesson.graph.builder import EventGraphBuilder
    from lesson.graph.schema import RawEvent, SessionGraph

    sm = _get_session_manager(cwd)
    slug = sm.active_slug()
    if not slug:
        console.print("[red]No active session. Run `lesson start` first.[/red]")
        raise typer.Exit(1)

    arc_path = sm.arc_path(slug)
    graph_path = sm.graph_path(slug)

    events = RawEvent.load_file(arc_path)
    if not events:
        console.print("[yellow]arc.jsonl is empty — nothing to compress.[/yellow]")
        return

    graph = SessionGraph.load(graph_path) if graph_path.exists() else SessionGraph.empty(slug)

    builder = EventGraphBuilder(threshold=threshold, use_embedder=not no_embed)
    result = builder.compress(events, graph)

    # Archive arc.jsonl
    archives = list(sm.session_dir(slug).glob("arc.jsonl.archive.*"))
    n = len(archives) + 1
    arc_path.rename(arc_path.with_suffix(f".jsonl.archive.{n}"))
    arc_path.touch()
    sm.counter_path(slug).write_text("0")

    # Save graph
    chars = result.graph.save(graph_path)
    sm.update_token_tracking(
        slug,
        compression_cycles=1,
        graph_output_chars=chars - sm.meta(slug).get("token_tracking", {}).get("graph_output_chars", 0),
    )

    console.print(
        f"[green]✓[/green] Compressed [bold]{result.events_processed}[/bold] events "
        f"→ [bold]{result.nodes_added}[/bold] nodes, [bold]{result.edges_added}[/bold] edges "
        f"in [bold]{result.elapsed_ms:.1f}ms[/bold]"
    )
    console.print(f"  archived → arc.jsonl.archive.{n}")


# ------------------------------------------------------------------
# lesson stats
# ------------------------------------------------------------------

@app.command()
def stats(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
):
    """Print graph metrics for the current session."""
    from lesson.graph.algorithms import graph_metrics, is_valid
    from lesson.graph.schema import SessionGraph

    sm = _get_session_manager(cwd)
    slug = sm.active_slug()
    if not slug:
        console.print("[red]No active session.[/red]")
        raise typer.Exit(1)

    graph_path = sm.graph_path(slug)
    if not graph_path.exists():
        console.print("[yellow]No session_graph.json yet. Run `lesson compress` first.[/yellow]")
        return

    graph = SessionGraph.load(graph_path)
    metrics = graph_metrics(graph)
    ok, issues = is_valid(graph)

    table = Table(title=f"Session graph: {slug}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    for k, v in metrics.items():
        if k not in ("orphan_ids",):
            table.add_row(k, str(v))

    table.add_row("valid", "[green]yes[/green]" if ok else f"[red]no ({len(issues)} issues)[/red]")

    meta = sm.meta(slug)
    tt = meta.get("token_tracking", {})
    table.add_row("arc_input_chars", str(tt.get("arc_input_chars", 0)))
    table.add_row("total_events", str(sm.arc_event_count(slug)))
    table.add_row("prompt_events", str(sm.prompt_event_count(slug)))
    table.add_row("root_cause_id", str(graph.root_cause_id))
    table.add_row("resolution_id", str(graph.resolution_id))

    console.print(table)

    if issues:
        console.print("[red]Issues:[/red]")
        for issue in issues:
            console.print(f"  • {issue}")


# ------------------------------------------------------------------
# lesson graph
# ------------------------------------------------------------------

@app.command(name="graph")
def show_graph(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
    output: Path = typer.Option(None, "--output", "-o", help="Write HTML to this path"),
    mermaid: bool = typer.Option(False, "--mermaid", help="Print Mermaid syntax instead"),
    dot: bool = typer.Option(False, "--dot", help="Print DOT syntax instead"),
):
    """Visualize the session graph (interactive HTML or text format)."""
    from lesson.graph.schema import SessionGraph
    from lesson.graph.visualize import to_dot, to_mermaid, to_plotly_html

    sm = _get_session_manager(cwd)
    slug = sm.active_slug()
    if not slug:
        console.print("[red]No active session.[/red]")
        raise typer.Exit(1)

    graph_path = sm.graph_path(slug)
    if not graph_path.exists():
        console.print("[yellow]No graph yet. Run `lesson compress` first.[/yellow]")
        return

    graph = SessionGraph.load(graph_path)

    if mermaid:
        print(to_mermaid(graph))
        return
    if dot:
        print(to_dot(graph))
        return

    html = to_plotly_html(graph, title=f"Session: {slug}")
    dest = output or sm.session_dir(slug) / "graph.html"
    dest.write_text(html, encoding="utf-8")
    console.print(f"[green]✓[/green] Graph written to [bold]{dest}[/bold]")

    try:
        import webbrowser
        webbrowser.open(dest.as_uri())
    except Exception:
        pass


# ------------------------------------------------------------------
# lesson resume
# ------------------------------------------------------------------

@app.command()
def resume(
    slug: str = typer.Argument(None, help="Session slug (defaults to last session)"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
):
    """Resume the last (or specified) session."""
    sm = _get_session_manager(cwd)
    result = sm.resume(slug)
    if result:
        console.print(f"[green]✓[/green] Resumed session [bold]{result}[/bold]")
    else:
        console.print("[red]No session to resume.[/red]")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# lesson done
# ------------------------------------------------------------------

@app.command()
def done(
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Project root directory"),
):
    """Finalize session: compress remaining events, then print instructions.

    The narrative lesson generation still requires LLM — run /lesson-done
    inside Claude Code, or pass the graph path to your LLM of choice.
    """
    from lesson.graph.builder import EventGraphBuilder
    from lesson.graph.schema import RawEvent, SessionGraph

    sm = _get_session_manager(cwd)
    slug = sm.active_slug()
    if not slug:
        console.print("[red]No active session.[/red]")
        raise typer.Exit(1)

    # Final compression of any remaining events
    events = RawEvent.load_file(sm.arc_path(slug))
    if events:
        graph_path = sm.graph_path(slug)
        graph = SessionGraph.load(graph_path) if graph_path.exists() else SessionGraph.empty(slug)
        builder = EventGraphBuilder()
        result = builder.compress(events, graph)
        result.graph.save(graph_path)
        console.print(
            f"[green]✓[/green] Final compression: {result.events_processed} events "
            f"→ {result.nodes_added} new nodes"
        )

    console.print(f"\n[bold]Session graph ready:[/bold] {sm.graph_path(slug)}")
    console.print(
        "\nTo generate the lesson narrative, run [bold]/lesson-done[/bold] inside Claude Code\n"
        "or pass the session_graph.json to your LLM with the lesson-done template."
    )


if __name__ == "__main__":
    app()
