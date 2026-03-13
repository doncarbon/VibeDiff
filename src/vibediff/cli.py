import json
from pathlib import Path

import click
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from vibediff import __version__
from vibediff.analyze import analyze_ai
from vibediff.collaboration import analyze_collaboration
from vibediff.config import Config, load_config
from vibediff.diff import diff_from_pr, diff_from_ref
from vibediff.drift import analyze_drift
from vibediff.fingerprint import Fingerprint, scan
from vibediff.idiom import analyze_idioms

console = Console()

CACHE_DIR = ".vibediff-cache"
FINGERPRINT_FILE = "fingerprint.json"

SCORE_COLORS = {"high": "red", "medium": "yellow", "low": "green", "good": "green", "mixed": "yellow", "poor": "red"}

GRADE_ART = {
    "A": [
        "  ██  ",
        " ████ ",
        "██  ██",
        "██████",
        "██  ██",
    ],
    "B": [
        "█████ ",
        "██  ██",
        "█████ ",
        "██  ██",
        "█████ ",
    ],
    "C": [
        " ████ ",
        "██    ",
        "██    ",
        "██    ",
        " ████ ",
    ],
    "D": [
        "████  ",
        "██ ██ ",
        "██  ██",
        "██ ██ ",
        "████  ",
    ],
    "F": [
        "██████",
        "██    ",
        "█████ ",
        "██    ",
        "██    ",
    ],
}

GRADE_COLORS = {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}


def _compute_grade(ai_score, drift_score, collab_score, idiom_score):
    if drift_score is not None:
        health = (
            (100 - ai_score) * 0.30
            + (100 - drift_score) * 0.20
            + collab_score * 0.25
            + (100 - idiom_score) * 0.25
        )
    else:
        health = (
            (100 - ai_score) * 0.35
            + collab_score * 0.35
            + (100 - idiom_score) * 0.30
        )
    if health >= 90:
        return "A"
    if health >= 75:
        return "B"
    if health >= 60:
        return "C"
    if health >= 40:
        return "D"
    return "F"


def _score_bar(score: float, higher_is_better: bool = False) -> str:
    width = 15
    filled = round(score * width / 100)
    empty = width - filled
    quality = score if higher_is_better else 100 - score
    if quality >= 70:
        color = "green"
    elif quality >= 40:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def _severity_bar(severity: float) -> str:
    return "█" * int(severity * 5) + "░" * (5 - int(severity * 5))


# --- Fingerprint persistence ---

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


SKIP_FIELDS = {"func_names", "func_lengths"}


def _save_fingerprint(fp: Fingerprint):
    Path(CACHE_DIR).mkdir(exist_ok=True)
    data = {k: v for k, v in fp.__dict__.items() if k not in SKIP_FIELDS and not k.startswith("_")}
    (Path(CACHE_DIR) / FINGERPRINT_FILE).write_text(json.dumps(data, indent=2))


# --- Rich terminal rendering ---

def _render_header(grade, file_count, added, removed, scores):
    grade_color = GRADE_COLORS[grade]
    art = Text("\n".join(GRADE_ART[grade]), style=grade_color)

    summary = Text()
    summary.append(f"{file_count} file(s)", style="bold")
    summary.append("  ")
    summary.append(f"+{added}", style="green")
    summary.append("  ")
    summary.append(f"-{removed}", style="red")

    bars = Table(show_header=False, box=None, padding=(0, 2))
    bars.add_column(min_width=22)
    bars.add_column()
    bars.add_column(justify="right", min_width=4)
    bars.add_column(min_width=8)

    for name, score, label, higher_better in scores:
        bar = _score_bar(score, higher_better)
        lbl_color = SCORE_COLORS[label]
        bars.add_row(name, bar, f"{score:.0f}", f"[{lbl_color}]{label}[/{lbl_color}]")

    layout = Table.grid(padding=(0, 4))
    layout.add_column()
    layout.add_column()
    layout.add_row(Align.center(art, vertical="middle"), Group(summary, Text(""), bars))

    console.print(Panel(layout, title="[bold]VibeDiff[/bold]", border_style="dim", padding=(1, 2)))


def _render_findings(title, score, label, findings, detail_fn):
    if not findings:
        return
    color = SCORE_COLORS[label]
    console.print()
    console.print(Rule(f"[bold]{title}[/bold]  [{color}]{score:.0f}/100 ({label})[/{color}]", style="dim"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan", min_width=22)
    table.add_column()
    table.add_column(justify="right", min_width=7)

    for f in sorted(findings, key=lambda x: x.severity, reverse=True):
        sev_color = "red" if f.severity >= 0.7 else "yellow" if f.severity >= 0.4 else "dim"
        bar = "█" * int(f.severity * 5) + "░" * (5 - int(f.severity * 5))
        table.add_row(f.signal, detail_fn(f), f"[{sev_color}]{bar}[/{sev_color}]")

    console.print(table)


# --- JSON output ---

def _to_json(grade, ai_report, drift_report, collab_report, idiom_report, file_count, added, removed):
    result = {
        "grade": grade,
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
                {"signal": f.signal, "detail": f.detail, "severity": round(f.severity, 2), "locations": f.locations}
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

def _to_markdown(grade, ai_report, drift_report, collab_report, idiom_report, file_count, added, removed):
    lines = [f"## VibeDiff Report — Grade: {grade}", "", f"**{file_count} file(s)** | +{added} -{removed}", ""]

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
            detail = f.detail
            if f.locations:
                detail += f" ({', '.join(f.locations[:3])})"
            lines.append(f"| `{f.signal}` | {detail} | {_severity_bar(f.severity)} |")
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


# --- PR comment posting ---

def _post_pr_comment(pr_number: str, body: str) -> bool:
    """Post a comment on a PR via gh CLI. Returns True on success."""
    import subprocess
    try:
        subprocess.run(
            ["gh", "pr", "comment", pr_number, "--body", body],
            check=True, capture_output=True, text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        click.echo(f"Failed to post PR comment: {e.stderr.strip()}", err=True)
        return False
    except FileNotFoundError:
        click.echo("gh CLI not found — install it from https://cli.github.com", err=True)
        return False


# --- Filtering and baseline ---

BASELINE_FILE = "baseline.json"


def _filter_findings(findings, ignore: list[str]):
    """Remove findings whose signal is in the ignore list."""
    if not ignore:
        return findings
    return [f for f in findings if f.signal not in ignore]


def _load_baseline() -> set[str] | None:
    """Load baseline signal set. Returns set of signal names or None."""
    path = Path(CACHE_DIR) / BASELINE_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return set(data.get("signals", []))
    except (json.JSONDecodeError, OSError):
        return None


def _save_baseline(signals: set[str]):
    Path(CACHE_DIR).mkdir(exist_ok=True)
    data = {"signals": sorted(signals)}
    (Path(CACHE_DIR) / BASELINE_FILE).write_text(
        json.dumps(data, indent=2)
    )


def _apply_baseline(findings, baseline: set[str] | None):
    """Remove findings that are in the baseline."""
    if baseline is None:
        return findings
    return [f for f in findings if f.signal not in baseline]


def _filter_files(diff, exclude: list[str]):
    """Remove files matching exclude glob patterns from a diff."""
    if not exclude:
        return diff
    from fnmatch import fnmatch
    diff.files = [
        f for f in diff.files
        if not any(fnmatch(f.path, pat) for pat in exclude)
    ]
    return diff


# --- Core logic (used by CLI and MCP server) ---

def run_review(target: str, pr: bool = False, no_fingerprint: bool = False,
               do_synth: bool = False, no_baseline: bool = False) -> dict | None:
    """Run all analyzers and return structured results."""
    cfg = load_config()
    d = diff_from_pr(target) if pr else diff_from_ref(target)
    _filter_files(d, cfg.exclude)
    if not d.files:
        return None

    added = sum(len(f.added) for f in d.files)
    removed = sum(len(f.removed) for f in d.files)

    ai_report = analyze_ai(d)

    drift_report = None
    if not no_fingerprint:
        fp = _load_fingerprint()
        if fp:
            drift_report = analyze_drift(d, fp)

    collab_report = analyze_collaboration(d)
    idiom_report = analyze_idioms(d)

    # Apply ignore filter
    ai_report.findings = _filter_findings(ai_report.findings, cfg.ignore)
    if drift_report:
        drift_report.findings = _filter_findings(drift_report.findings, cfg.ignore)
    collab_report.findings = _filter_findings(collab_report.findings, cfg.ignore)
    idiom_report.findings = _filter_findings(idiom_report.findings, cfg.ignore)

    # Apply baseline
    if not no_baseline:
        baseline = _load_baseline()
        ai_report.findings = _apply_baseline(ai_report.findings, baseline)
        if drift_report:
            drift_report.findings = _apply_baseline(drift_report.findings, baseline)
        collab_report.findings = _apply_baseline(collab_report.findings, baseline)
        idiom_report.findings = _apply_baseline(idiom_report.findings, baseline)

    drift_score = drift_report.drift_score if drift_report else None
    grade = _compute_grade(ai_report.ai_score, drift_score, collab_report.collab_score, idiom_report.idiom_score)

    result = _to_json(grade, ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed)

    if do_synth:
        from vibediff.synthesize import synthesize as _synth
        raw_diff = d.raw if hasattr(d, "raw") else ""
        synthesis = _synth(raw_diff, result, grade)
        if synthesis:
            result["synthesis"] = synthesis

    return result


def run_learn(path: str = ".", force: bool = False) -> dict | None:
    """Scan codebase and save fingerprint. Returns fingerprint data or None if exists and not forced."""
    existing = _load_fingerprint()
    if existing and not force:
        return None

    fp = scan(path)
    _save_fingerprint(fp)
    return {k: v for k, v in fp.__dict__.items() if k not in SKIP_FIELDS and not k.startswith("_")}


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
@click.option("--synthesize", "do_synth", is_flag=True, help="Use Claude API for natural-language synthesis.")
@click.option("--no-baseline", is_flag=True, help="Ignore baseline, show all findings.")
@click.option("--comment", is_flag=True, help="Post review as a PR comment (requires --pr and gh CLI).")
def review(target: str, verbose: bool, no_fingerprint: bool, fmt: str, pr: bool, do_synth: bool, no_baseline: bool, comment: bool):
    """Review a diff for AI patterns and style drift."""
    if comment and not pr:
        click.echo("--comment requires --pr", err=True)
        raise SystemExit(1)

    cfg = load_config()
    d = diff_from_pr(target) if pr else diff_from_ref(target)
    _filter_files(d, cfg.exclude)
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

    # Apply ignore filter
    ai_report.findings = _filter_findings(ai_report.findings, cfg.ignore)
    if drift_report:
        drift_report.findings = _filter_findings(drift_report.findings, cfg.ignore)
    collab_report.findings = _filter_findings(collab_report.findings, cfg.ignore)
    idiom_report.findings = _filter_findings(idiom_report.findings, cfg.ignore)

    # Apply baseline
    if not no_baseline:
        baseline = _load_baseline()
        ai_report.findings = _apply_baseline(ai_report.findings, baseline)
        if drift_report:
            drift_report.findings = _apply_baseline(drift_report.findings, baseline)
        collab_report.findings = _apply_baseline(collab_report.findings, baseline)
        idiom_report.findings = _apply_baseline(idiom_report.findings, baseline)

    drift_score = drift_report.drift_score if drift_report else None
    grade = _compute_grade(ai_report.ai_score, drift_score, collab_report.collab_score, idiom_report.idiom_score)

    # Optional LLM synthesis
    synthesis = None
    if do_synth:
        from vibediff.synthesize import synthesize
        raw_diff = d.raw if hasattr(d, "raw") else ""
        analysis_json = _to_json(grade, ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed)
        synthesis = synthesize(raw_diff, analysis_json, grade)
        if synthesis is None and fmt == "rich":
            console.print("[dim]Set ANTHROPIC_API_KEY to enable synthesis (pip install vibediff\\[llm]).[/dim]")

    # Generate markdown for --comment (regardless of output format)
    if comment:
        md_body = _to_markdown(grade, ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed)
        if synthesis:
            md_body += f"\n### Synthesis\n\n{synthesis}\n"
        if _post_pr_comment(target, md_body):
            console.print(f"[green]Posted review comment on PR #{target}[/green]")
        else:
            raise SystemExit(1)

    if fmt == "json":
        result = _to_json(grade, ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed)
        if synthesis:
            result["synthesis"] = synthesis
        click.echo(json.dumps(result, indent=2))
        return

    if fmt == "md":
        md = _to_markdown(grade, ai_report, drift_report, collab_report, idiom_report, len(d.files), added, removed)
        if synthesis:
            md += f"\n### Synthesis\n\n{synthesis}\n"
        click.echo(md)
        return

    # Rich terminal output — header panel with grade + score bars
    scores = [("AI Detection", ai_report.ai_score, ai_report.label, False)]
    if drift_report:
        scores.append(("Style Drift", drift_report.drift_score, drift_report.label, False))
    scores.append(("Collaboration", collab_report.collab_score, collab_report.label, True))
    scores.append(("Idiom Contamination", idiom_report.idiom_score, idiom_report.label, False))

    _render_header(grade, len(d.files), added, removed, scores)

    has_findings = (
        ai_report.findings
        or (drift_report and drift_report.findings)
        or collab_report.findings
        or idiom_report.findings
    )

    if not has_findings:
        if not fp and not no_fingerprint:
            console.print("[dim]Run 'vibediff learn' to enable style drift detection.[/dim]")
        if not synthesis:
            return

    # Detailed findings with Rule headers
    _render_findings("AI Detection", ai_report.ai_score, ai_report.label, ai_report.findings,
                     lambda f: f.detail + (f" ({', '.join(f.locations[:3])})" if f.locations else ""))

    if drift_report:
        _render_findings("Style Drift", drift_report.drift_score, drift_report.label, drift_report.findings,
                         lambda f: f"expected {f.expected}, got {f.found}")

    _render_findings("Collaboration", collab_report.collab_score, collab_report.label, collab_report.findings,
                     lambda f: f.detail + (f" ({', '.join(f.locations[:3])})" if f.locations else ""))

    _render_findings("Idiom Contamination", idiom_report.idiom_score, idiom_report.label, idiom_report.findings,
                     lambda f: f"{f.detail} \\[{f.source_lang}]" + (f" ({', '.join(f.locations[:3])})" if f.locations else ""))

    if synthesis:
        console.print()
        console.print(Panel(synthesis, title="[bold]Synthesis[/bold]", border_style="cyan", padding=(1, 2)))

    console.print()


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
    console.print(f"  Type annotations: {fp.type_annotation_ratio:.0%} params, {fp.return_annotation_ratio:.0%} returns")
    console.print(f"  Error handling: {fp.try_except_ratio:.0%} funcs use try/except, {fp.specific_except_ratio:.0%} specific")
    console.print(f"  Decorators: {fp.decorator_density:.1f} per function")


@main.command()
@click.argument("target", default="HEAD~1")
@click.option("--pr", is_flag=True, help="Treat TARGET as a GitHub PR number.")
@click.option("--clear", is_flag=True, help="Remove the current baseline.")
def baseline(target: str, pr: bool, clear: bool):
    """Save current findings as baseline so future reviews only flag new issues."""
    if clear:
        path = Path(CACHE_DIR) / BASELINE_FILE
        if path.exists():
            path.unlink()
            console.print("[green]Baseline cleared.[/green]")
        else:
            console.print("[yellow]No baseline to clear.[/yellow]")
        return

    cfg = load_config()
    d = diff_from_pr(target) if pr else diff_from_ref(target)
    _filter_files(d, cfg.exclude)
    if not d.files:
        console.print("[yellow]No changes to baseline.[/yellow]")
        return

    ai_report = analyze_ai(d)
    collab_report = analyze_collaboration(d)
    idiom_report = analyze_idioms(d)

    signals: set[str] = set()
    for f in ai_report.findings:
        signals.add(f.signal)
    for f in collab_report.findings:
        signals.add(f.signal)
    for f in idiom_report.findings:
        signals.add(f.signal)

    fp = _load_fingerprint()
    if fp:
        drift_report = analyze_drift(d, fp)
        for f in drift_report.findings:
            signals.add(f.signal)

    _save_baseline(signals)
    console.print(f"[green]Baseline saved: {len(signals)} signal(s) suppressed in future reviews.[/green]")
    if signals:
        for s in sorted(signals):
            console.print(f"  [dim]• {s}[/dim]")


@main.command()
def serve():
    """Start VibeDiff as an MCP tool server (stdio)."""
    from vibediff.mcp_server import run_server
    run_server()
