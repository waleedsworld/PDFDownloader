#!/usr/bin/env python3
"""Interactive terminal UI for PDF Downloader.

A small, self-contained `rich`-powered front-end over the same core functions
the command-line tool uses. It walks you through:

    1. Entering (or confirming) a page URL.
    2. Scanning the page and reviewing the PDF links it found.
    3. Picking an output folder.
    4. Watching a live progress bar as each file streams to disk.

Launch it with ``python3 src/PdfDownloader.py --tui`` (or ``python3 src/tui.py``).

``rich`` is an optional dependency — if it isn't installed, :func:`run_tui`
returns a non-zero exit code with a friendly hint instead of crashing.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import requests

try:
    import PdfDownloader as core
except ImportError:  # pragma: no cover - allows `python3 src/tui.py`
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import PdfDownloader as core


def _missing_rich_message() -> str:
    return (
        "The interactive TUI needs the 'rich' package, which isn't installed.\n"
        "Install it with:\n\n"
        "    pip install rich\n\n"
        "…or just use the classic command-line mode instead:\n\n"
        "    python3 src/PdfDownloader.py <url>\n"
    )


def _normalise_url(raw: str) -> str:
    """Add a scheme if the user typed a bare host (mirrors the CLI's behaviour)."""
    raw = raw.strip()
    if raw and not urlparse(raw).scheme:
        raw = "https://" + raw
    return raw


def run_tui(
    url: str | None = None,
    output_dir: str = ".",
    user_agent: str = core.DEFAULT_UA,
) -> int:
    """Run the interactive downloader. Returns a process exit code (0 = success).

    Any pre-filled ``url``/``output_dir`` (e.g. passed on the command line) are
    used as defaults the user can accept or edit.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.prompt import Confirm, Prompt
        from rich.table import Table
    except ImportError:
        print(_missing_rich_message())
        return 3

    console = Console()

    console.print(
        Panel.fit(
            "[bold]PDF Downloader[/bold]\n"
            "[dim]Grab every PDF linked from a web page.[/dim]",
            border_style="cyan",
        )
    )

    # 1. URL --------------------------------------------------------------
    url = _normalise_url(url or Prompt.ask("[bold cyan]Page URL[/bold cyan]"))
    if not url:
        console.print("[yellow]No URL provided. Bye![/yellow]")
        return 2

    session = core.build_session(user_agent)

    # 2. Scan -------------------------------------------------------------
    with console.status(f"Scanning [cyan]{url}[/cyan] …", spinner="dots"):
        try:
            html = core.fetch_page(session, url)
        except requests.RequestException as exc:
            console.print(f"[red]Could not open the page:[/red] {exc}")
            return 1
        links = core.find_pdf_links(url, html)

    if not links:
        console.print("[yellow]No PDF links found on that page. Nothing to do.[/yellow]")
        return 0

    table = Table(title=f"Found {len(links)} PDF link(s)", title_style="bold green")
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("File", style="bold")
    table.add_column("URL", style="cyan", overflow="fold")
    for index, link in enumerate(links, start=1):
        table.add_row(str(index), core.filename_from_url(link), link)
    console.print(table)

    # 3. Confirm & choose destination ------------------------------------
    if not Confirm.ask("Download these now?", default=True):
        console.print("[dim](nothing downloaded)[/dim]")
        return 0

    output_dir = Prompt.ask(
        "[bold cyan]Save to folder[/bold cyan]", default=output_dir or "."
    )
    os.makedirs(output_dir, exist_ok=True)
    console.print(f"Downloading to: [green]{os.path.abspath(output_dir)}[/green]\n")

    # 4. Download with a live progress bar --------------------------------
    failures = 0
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task("Downloading", total=len(links))
        for link in links:
            name = core.filename_from_url(link)
            progress.update(task, description=name)
            try:
                core.download_file(session, link, output_dir)
            except (requests.RequestException, OSError) as exc:
                failures += 1
                console.print(f"[red]FAIL[/red] {link} - {exc}")
            progress.advance(task)

    downloaded = len(links) - failures
    style = "green" if not failures else "yellow"
    console.print(
        f"\n[{style}]Done! {downloaded} downloaded, {failures} failed.[/{style}]"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_tui())
