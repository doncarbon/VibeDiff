import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vibediff import __version__
from vibediff.analyze import AnalysisReport, analyze_ai
from vibediff.diff import diff_from_ref

console = Console()

SCORE_COLORS = {"high": "red", "medium": "yellow", "low": "green"}


def _render_report(report: AnalysisReport, file_count: int, added: int, removed: int):
    color = SCORE_COLORS[report.label]

    header = Table.grid(padding=(0, 2))
    header.add_row(
        f"[bold]{file_count} file(s)[/bold]",
        f"[green]+{added}[/green] [red]-{removed}[/red]",
        f"AI score: [{color} bold]{report.ai_score:.0f}/100[/{color} bold] ({report.label})",
    )
    console.print(Panel(header, title="[bold]VibeDiff[/bold]", border_style="dim"))

    if not report.findings:
        console.print("\n[green]No AI patterns detected.[/green]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Signal", style="cyan", min_width=20)
    table.add_column("Detail")
    table.add_column("Severity", justify="right", min_width=8)

    for f in sorted(report.findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        sev_bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        detail = f.detail
        if f.locations:
            detail += f" ({', '.join(f.locations[:3])})"
        table.add_row(f.signal, detail, f"[{sev_color}]{sev_bar}[/{sev_color}]")

    console.print(table)


@click.group()
@click.version_option(version=__version__, prog_name="vibediff")
def main():
    """VibeDiff — knows when a PR doesn't belong."""


@main.command()
@click.argument("target", default="HEAD~1")
@click.option("-v", "--verbose", is_flag=True)
def review(target: str, verbose: bool):
    """Review a diff for AI patterns and style drift."""
    d = diff_from_ref(target)
    if not d.files:
        console.print("[yellow]No changes.[/yellow]")
        return

    report = analyze_ai(d)
    added = sum(len(f.added) for f in d.files)
    removed = sum(len(f.removed) for f in d.files)
    _render_report(report, len(d.files), added, removed)
