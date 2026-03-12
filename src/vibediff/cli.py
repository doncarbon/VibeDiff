import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vibediff import __version__
from vibediff.analyze import AnalysisReport, analyze_ai
from vibediff.collaboration import CollabReport, analyze_collaboration
from vibediff.diff import diff_from_pr, diff_from_ref
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


# --- Rich terminal rendering ---

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


# --- JSON output ---

def _severity_bar(severity: float) -> str:
    return "█" * int(severity * 5) + "░" * (5 - int(severity * 5))


def _to_json(ai_report, drift_report, collab_report, idiom_report, file_count, added, removed):
    result = {
        "files": file_count,
        "lines_added": added,
        "lines_removed": removed,
        "ai_detection": {
            "score": round(ai_report.ai_score, 1),
            "label": ai_report.label,
            "findings": [
                {"signal": f.signal, "detail": f.detail, "severity": round(f.severity, 2), "locations": f.locations}
                for f in ai_report.findings
            ],
        },
        "collaboration": {
            "score": round(collab_report.collab_score, 1),
            "label": collab_report.label,
            "findings": [
                {"signal": f.signal, "detail": f.detail, "severity": round(f.severity, 2)}
                for f in collab_report.findings
            ],
        },
        "idiom_contamination": {
            "score": round(idiom_report.idiom_score, 1),
            "label": idiom_report.label,
            "findings": [
                {"signal": f.signal, "source_lang": f.source_lang, "detail": f.detail, "severity": round(f.severity, 2), "locations": f.locations}
                for f in idiom_report.findings
            ],
        },
    }
    if drift_report:
        result["style_drift"] = {
            "score": round(drift_report.drift_score, 1),
            "label": drift_report.label,
            "findings": [
                {"signal": f.signal, "expected": f.expected, "found": f.found, "severity": round(f.severity, 2)}
                for f in drift_report.findings
            ],
        }
    return result


# --- Markdown output ---

def _to_markdown(ai_report, drift_report, collab_report, idiom_report, file_count, added, removed):
    lines = [f"## VibeDiff Report", "", f"**{file_count} file(s)** | +{added} -{removed}", ""]

    if ai_report.findings:
        lines.append(f"### AI Detection — {ai_report.ai_score:.0f}/100 ({ai_report.label})")
        lines.append("")
        lines.append("| Signal | Detail | Severity |")
        lines.append("|--------|--------|----------|")
        for f in sorted(ai_report.findings, key=lambda x: x.severity, reverse=True):
            detail = f.detail
            if f.locations:
                detail += f" ({', '.join(f.locations[:3])})"
            lines.append(f"| `{f.signal}` | {detail} | {_severity_bar(f.severity)} |")
        lines.append("")

    if drift_report and drift_report.findings:
        lines.append(f"### Style Drift — {drift_report.drift_score:.0f}/100 ({drift_report.label})")
        lines.append("")
        lines.append("| Signal | Expected | Found | Severity |")
        lines.append("|--------|----------|-------|----------|")
        for f in sorted(drift_report.findings, key=lambda x: x.severity, reverse=True):
            lines.append(f"| `{f.signal}` | {f.expected} | {f.found} | {_severity_bar(f.severity)} |")
        lines.append("")

    if collab_report.findings:
        lines.append(f"### Collaboration — {collab_report.collab_score:.0f}/100 ({collab_report.label})")
        lines.append("")
        lines.append("| Signal | Detail | Severity |")
        lines.append("|--------|--------|----------|")
        for f in sorted(collab_report.findings, key=lambda x: x.severity, reverse=True):
            lines.append(f"| `{f.signal}` | {f.detail} | {_severity_bar(f.severity)} |")
        lines.append("")

    if idiom_report.findings:
        lines.append(f"### Idiom Contamination — {idiom_report.idiom_score:.0f}/100 ({idiom_report.label})")
        lines.append("")
        lines.append("| Signal | Detail | Source | Severity |")
        lines.append("|--------|--------|--------|----------|")
        for f in sorted(idiom_report.findings, key=lambda x: x.severity, reverse=True):
            detail = f.detail
            if f.locations:
                detail += f" ({', '.join(f.locations[:3])})"
            lines.append(f"| `{f.signal}` | {detail} | {f.source_lang} | {_severity_bar(f.severity)} |")
        lines.append("")

    if not any([ai_report.findings, drift_report and drift_report.findings, collab_report.findings, idiom_report.findings]):
        lines.append("**Clean.** No issues found.")
        lines.append("")

    return "\n".join(lines)


# --- CLI ---

@click.group()
@click.version_option(version=__version__, prog_name="vibediff")
def main():
    """VibeDiff — what changed, who wrote it, and does it belong."""


@main.command()
@click.argument("target", default="HEAD~1")
@click.option("-v", "--verbose", is_flag=True)
@click.option("--no-fingerprint", is_flag=True, help="Skip style drift analysis.")
@click.option("--format", "fmt", type=click.Choice(["rich", "json", "md"]), default="rich", help="Output format.")
@click.option("--pr", is_flag=True, help="Treat TARGET as a GitHub PR number (requires gh CLI).")
def review(target: str, verbose: bool, no_fingerprint: bool, fmt: str, pr: bool):
    """Review a diff for AI patterns and style drift."""
    d = diff_from_pr(target) if pr else diff_from_ref(target)
    if not d.files:
        if fmt == "json":
            click.echo("{}")
        elif fmt == "md":
            click.echo("No changes.")
        else:
            console.print("[yellow]No changes.[/yellow]")
        return

    added = sum(len(f.added) for f in d.files)
    removed = sum(len(f.removed) for f in d.files)

    ai_report = analyze_ai(d)

    drift_report = None
    fp = None
    if not no_fingerprint:
        fp = _load_fingerprint()
        if fp:
            drift_report = analyze_drift(d, fp)

    collab_report = analyze_collaboration(d)
    idiom_report = analyze_idioms(d)

    if fmt == "json":
        click.echo(json.dumps(_to_json(ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed), indent=2))
        return

    if fmt == "md":
        click.echo(_to_markdown(ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed))
        return

    # Rich terminal output
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
