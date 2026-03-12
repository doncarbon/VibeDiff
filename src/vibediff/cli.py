import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vibediff import __version__
from vibediff.analyze import AnalysisReport, analyze_ai
from vibediff.collaboration import CollabReport, analyze_collaboration
from vibediff.diff import diff_from_ref
from vibediff.drift import DriftReport, analyze_drift
from vibediff.fingerprint import Fingerprint, scan
from vibediff.idiom import IdiomReport, analyze_idioms

console = Console()

CACHE_DIR = ".vibediff-cache"
FINGERPRINT_FILE = "fingerprint.json"

SCORE_COLORS = {"high": "red", "medium": "yellow", "low": "green", "good": "green", "mixed": "yellow", "poor": "red"}


def _load_fingerprint() -> Fingerprint | None:
    path = Path(CACHE_DIR) / FINGERPRINT_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fp = Fingerprint()
        for k, v in data.items():
            if hasattr(fp, k):
                setattr(fp, k, v)
        return fp
    except (json.JSONDecodeError, OSError):
        return None


def _save_fingerprint(fp: Fingerprint):
    Path(CACHE_DIR).mkdir(exist_ok=True)
    data = {
        "files_scanned": fp.files_scanned,
        "total_lines": fp.total_lines,
        "snake_case_ratio": fp.snake_case_ratio,
        "camel_case_ratio": fp.camel_case_ratio,
        "avg_func_name_words": fp.avg_func_name_words,
        "comment_ratio": fp.comment_ratio,
        "avg_func_length": fp.avg_func_length,
        "from_import_ratio": fp.from_import_ratio,
        "docstring_ratio": fp.docstring_ratio,
    }
    (Path(CACHE_DIR) / FINGERPRINT_FILE).write_text(json.dumps(data, indent=2))


def _render_ai_report(report: AnalysisReport):
    if not report.findings:
        return

    color = SCORE_COLORS[report.label]
    console.print(f"\n[bold]AI Detection[/bold]  [{color}]{report.ai_score:.0f}/100 ({report.label})[/{color}]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(min_width=22)
    table.add_column()
    table.add_column(justify="right", min_width=8)

    for f in sorted(report.findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        detail = f.detail
        if f.locations:
            detail += f" ({', '.join(f.locations[:3])})"
        table.add_row(f"[cyan]{f.signal}[/cyan]", detail, f"[{sev_color}]{bar}[/{sev_color}]")

    console.print(table)


def _render_drift_report(report: DriftReport):
    if not report.findings:
        return

    color = SCORE_COLORS[report.label]
    console.print(f"\n[bold]Style Drift[/bold]  [{color}]{report.drift_score:.0f}/100 ({report.label})[/{color}]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(min_width=22)
    table.add_column()
    table.add_column(justify="right", min_width=8)

    for f in sorted(report.findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        table.add_row(
            f"[cyan]{f.signal}[/cyan]",
            f"expected {f.expected}, got {f.found}",
            f"[{sev_color}]{bar}[/{sev_color}]",
        )

    console.print(table)


def _render_collab_report(report: CollabReport):
    if not report.findings:
        return

    color = SCORE_COLORS[report.label]
    console.print(f"\n[bold]Collaboration[/bold]  [{color}]{report.collab_score:.0f}/100 ({report.label})[/{color}]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(min_width=22)
    table.add_column()
    table.add_column(justify="right", min_width=8)

    for f in sorted(report.findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        table.add_row(f"[cyan]{f.signal}[/cyan]", f.detail, f"[{sev_color}]{bar}[/{sev_color}]")

    console.print(table)


def _render_idiom_report(report: IdiomReport):
    if not report.findings:
        return

    color = SCORE_COLORS[report.label]
    console.print(f"\n[bold]Idiom Contamination[/bold]  [{color}]{report.idiom_score:.0f}/100 ({report.label})[/{color}]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(min_width=22)
    table.add_column()
    table.add_column(justify="right", min_width=8)

    for f in sorted(report.findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        detail = f"{f.detail} [{f.source_lang}]"
        if f.locations:
            detail += f" ({', '.join(f.locations[:3])})"
        table.add_row(f"[cyan]{f.signal}[/cyan]", detail, f"[{sev_color}]{bar}[/{sev_color}]")

    console.print(table)


@click.group()
@click.version_option(version=__version__, prog_name="vibediff")
def main():
    """VibeDiff — what changed, who wrote it, and does it belong."""


@main.command()
@click.argument("target", default="HEAD~1")
@click.option("-v", "--verbose", is_flag=True)
@click.option("--no-fingerprint", is_flag=True, help="Skip style drift analysis.")
def review(target: str, verbose: bool, no_fingerprint: bool):
    """Review a diff for AI patterns and style drift."""
    d = diff_from_ref(target)
    if not d.files:
        console.print("[yellow]No changes.[/yellow]")
        return

    added = sum(len(f.added) for f in d.files)
    removed = sum(len(f.removed) for f in d.files)

    # AI detection
    ai_report = analyze_ai(d)

    # Style drift (if fingerprint exists)
    drift_report = None
    fp = None
    if not no_fingerprint:
        fp = _load_fingerprint()
        if fp:
            drift_report = analyze_drift(d, fp)

    # Collaboration
    collab_report = analyze_collaboration(d)

    # Idiom contamination
    idiom_report = analyze_idioms(d)

    # Header
    parts = [f"[bold]{len(d.files)} file(s)[/bold]", f"[green]+{added}[/green] [red]-{removed}[/red]"]
    if ai_report.findings:
        c = SCORE_COLORS[ai_report.label]
        parts.append(f"AI: [{c}]{ai_report.ai_score:.0f}[/{c}]")
    if drift_report and drift_report.findings:
        c = SCORE_COLORS[drift_report.label]
        parts.append(f"Drift: [{c}]{drift_report.drift_score:.0f}[/{c}]")

    header = Table.grid(padding=(0, 2))
    header.add_row(*parts)
    console.print(Panel(header, title="[bold]VibeDiff[/bold]", border_style="dim"))

    has_findings = (
        ai_report.findings
        or (drift_report and drift_report.findings)
        or collab_report.findings
        or idiom_report.findings
    )

    if not has_findings:
        if not fp and not no_fingerprint:
            console.print("[dim]Run 'vibediff learn' to enable style drift detection.[/dim]")
        else:
            console.print("[green]Clean.[/green]")
        return

    _render_ai_report(ai_report)
    if drift_report:
        _render_drift_report(drift_report)
    _render_collab_report(collab_report)
    _render_idiom_report(idiom_report)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing fingerprint.")
def learn(path: str, force: bool):
    """Learn codebase conventions for style drift detection."""
    existing = _load_fingerprint()
    if existing and not force:
        console.print(f"[yellow]Fingerprint exists ({existing.files_scanned} files). Use --force to rebuild.[/yellow]")
        return

    fp = scan(path)
    _save_fingerprint(fp)

    console.print(f"[green]Learned from {fp.files_scanned} files ({fp.total_lines} lines)[/green]")
    console.print(f"  Naming: {fp.snake_case_ratio:.0%} snake_case, {fp.camel_case_ratio:.0%} camelCase")
    console.print(f"  Comment density: {fp.comment_ratio:.0%}")
    console.print(f"  Avg function length: {fp.avg_func_length:.0f} lines")
    console.print(f"  Import style: {fp.from_import_ratio:.0%} from-imports")
    console.print(f"  Docstring usage: {fp.docstring_ratio:.0%}")
