#!/usr/bin/env python3
"""PDF Downloader — grab every PDF linked from a web page in one go.

A tiny, dependency-light web-scraping helper. Point it at a page (a course
index, a lecture-notes hub, a documentation dump) and it finds every link that
resolves to a ``.pdf`` and downloads them for you.

Usage examples
--------------
    # Interactive — it will ask for the link
    python3 PdfDownloader.py

    # One-liner
    python3 PdfDownloader.py https://example.edu/course/notes

    # Choose an output folder and just list what it *would* grab
    python3 PdfDownloader.py https://example.edu/notes -o ./downloads --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; PDFDownloader/2.0; "
    "+https://github.com/waleedsworld/PDFDownloader)"
)
CHUNK_SIZE = 64 * 1024  # 64 KiB streaming chunks


def build_session(user_agent: str = DEFAULT_UA) -> requests.Session:
    """Return a configured requests session with a friendly User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def is_pdf_link(href: str) -> bool:
    """True if a href points at a PDF (ignores query strings & fragments)."""
    if not href:
        return False
    path = urlparse(href).path.lower()
    return path.endswith(".pdf")


def find_pdf_links(page_url: str, html: str) -> list[str]:
    """Extract absolute, de-duplicated PDF URLs from a page's HTML.

    Links are resolved against the page's own ``<base>`` tag when present,
    otherwise against ``page_url`` — so relative links Just Work.
    """
    soup = BeautifulSoup(html, "lxml")

    base_tag = soup.find("base", href=True)
    base_url = urljoin(page_url, base_tag["href"]) if base_tag else page_url

    seen: set[str] = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not is_pdf_link(href):
            continue
        absolute = urljoin(base_url, href)
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links


def filename_from_url(url: str) -> str:
    """Derive a safe local filename from a URL, defaulting to ``download.pdf``."""
    name = os.path.basename(urlparse(url).path)
    name = unquote(name) or "download.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def unique_path(directory: str, filename: str) -> str:
    """Avoid clobbering: file.pdf -> file (1).pdf -> file (2).pdf ..."""
    candidate = os.path.join(directory, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(directory, f"{stem} ({counter}){ext}")):
        counter += 1
    return os.path.join(directory, f"{stem} ({counter}){ext}")


def download_file(session: requests.Session, url: str, directory: str) -> str:
    """Stream a single PDF to ``directory`` and return the written path."""
    filename = filename_from_url(url)
    dest = unique_path(directory, filename)
    with session.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    handle.write(chunk)
    return dest


def fetch_page(session: requests.Session, url: str) -> str:
    """Fetch a page's HTML, raising for non-2xx responses."""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def run(url: str, output_dir: str, dry_run: bool, user_agent: str) -> int:
    """Core workflow. Returns a process exit code (0 = success)."""
    session = build_session(user_agent)

    try:
        html = fetch_page(session, url)
    except requests.RequestException as exc:
        print(f"x Could not open the page: {exc}", file=sys.stderr)
        return 1

    links = find_pdf_links(url, html)
    if not links:
        print("No PDF links found on that page. Nothing to do.")
        return 0

    print(f"Found {len(links)} PDF link(s):")
    for link in links:
        print(f"  - {link}")

    if dry_run:
        print("\n(dry run - nothing downloaded)")
        return 0

    os.makedirs(output_dir, exist_ok=True)
    print(f"\nDownloading to: {os.path.abspath(output_dir)}\n")

    failures = 0
    for index, link in enumerate(links, start=1):
        try:
            dest = download_file(session, link, output_dir)
            print(f"  [{index}/{len(links)}] ok  {os.path.basename(dest)}")
        except (requests.RequestException, OSError) as exc:
            failures += 1
            print(f"  [{index}/{len(links)}] FAIL {link} - {exc}", file=sys.stderr)

    downloaded = len(links) - failures
    print(f"\nDone! {downloaded} downloaded, {failures} failed.")
    return 1 if failures else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="PdfDownloader",
        description="Download every PDF linked from a web page.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Page to scrape. If omitted, you'll be prompted for it.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        metavar="DIR",
        help="Folder to save PDFs into (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the PDFs that would be downloaded, but don't download them.",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_UA,
        help="Custom User-Agent header to send.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = args.url or input("Enter link: ").strip()
    if not url:
        print("No URL provided. Bye!", file=sys.stderr)
        return 2
    if not urlparse(url).scheme:
        url = "https://" + url
    return run(url, args.output, args.dry_run, args.user_agent)


if __name__ == "__main__":
    raise SystemExit(main())
