import click
from rich.console import Console

from vibediff import __version__
from vibediff.diff import diff_from_ref

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="vibediff")
def main():
    """vibediff — knows when a PR doesn't belong."""


@main.command()
@click.argument("target", default="HEAD~1")
@click.option("-v", "--verbose", is_flag=True)
def review(target: str, verbose: bool):
    """Review a diff for style drift and AI patterns."""
    d = diff_from_ref(target)
    if not d.files:
        console.print("[yellow]No changes.[/yellow]")
        return

    console.print(f"[bold]{len(d.files)} file(s) changed[/bold]")
    for f in d.files:
        console.print(f"  {f.path} [green]+{len(f.added)}[/green] [red]-{len(f.removed)}[/red]")
