"""CLI entry point for VibeDiff."""

import click
from rich.console import Console

from vibediff import __version__
from vibediff.input.git_diff import parse_git_diff
from vibediff.input.models import PatchContext

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="vibediff")
def main():
    """VibeDiff — AI-era code review.

    Detects AI-generated patterns, style drift, and collaboration quality in your PRs.
    """


@main.command()
@click.argument("target", default="HEAD~1")
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["terminal", "json", "markdown"]),
    default="terminal",
    help="Output format.",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed analysis.")
@click.option("--no-context", is_flag=True, help="Skip codebase learning.")
def review(target: str, fmt: str, verbose: bool, no_context: bool):
    """Review a diff for AI patterns and style drift.

    TARGET can be a git ref (HEAD~3), branch comparison (main..feature),
    or a GitHub PR URL.
    """
    console.print(f"\n[bold]VibeDiff v{__version__}[/bold]")
    console.print(f"[dim]Analyzing: {target}[/dim]\n")

    patch = parse_git_diff(target)
    if not patch.files:
        console.print("[yellow]No files changed.[/yellow]")
        return

    console.print(f"[green]Parsed {len(patch.files)} changed file(s):[/green]")
    for f in patch.files:
        added = len(f.added_lines)
        removed = len(f.removed_lines)
        console.print(f"  {f.path} [green]+{added}[/green] [red]-{removed}[/red] [{f.language}]")

    console.print("\n[dim]Analyzers not yet implemented — coming in Phase 2.[/dim]")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing fingerprint cache.")
def learn(path: str, force: bool):
    """Learn codebase conventions to detect style drift.

    Scans the codebase and builds a style fingerprint.
    """
    console.print(f"\n[bold]VibeDiff v{__version__}[/bold]")
    console.print(f"[dim]Learning conventions from: {path}[/dim]\n")
    console.print("[dim]Codebase fingerprinting not yet implemented — coming in Phase 3.[/dim]")
