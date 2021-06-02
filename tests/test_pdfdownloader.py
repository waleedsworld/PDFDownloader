"""Unit tests for the pure, network-free parts of PdfDownloader."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import PdfDownloader as pd  # noqa: E402


def test_is_pdf_link_variants():
    assert pd.is_pdf_link("notes.pdf")
    assert pd.is_pdf_link("/a/b/paper.PDF")
    assert pd.is_pdf_link("https://x.com/f.pdf?v=2#page=3")
    assert not pd.is_pdf_link("index.html")
    assert not pd.is_pdf_link("notpdf")
    assert not pd.is_pdf_link("")


def test_find_pdf_links_resolves_and_dedupes():
    html = """
    <a href="alpha.pdf">a</a>
    <a href="sub/gamma.pdf">g</a>
    <a href="alpha.pdf">dup</a>
    <a href="beta.pdf?v=2">q</a>
    <a href="page.html">no</a>
    <a href="https://cdn.example.com/ext.pdf">abs</a>
    """
    links = pd.find_pdf_links("https://site.test/course/", html)
    assert links == [
        "https://site.test/course/alpha.pdf",
        "https://site.test/course/sub/gamma.pdf",
        "https://site.test/course/beta.pdf?v=2",
        "https://cdn.example.com/ext.pdf",
    ]


def test_find_pdf_links_honours_base_tag():
    html = '<base href="https://cdn.test/files/"><a href="doc.pdf">d</a>'
    links = pd.find_pdf_links("https://site.test/page", html)
    assert links == ["https://cdn.test/files/doc.pdf"]


def test_filename_from_url():
    assert pd.filename_from_url("https://x.com/a/b/report.pdf") == "report.pdf"
    assert pd.filename_from_url("https://x.com/f.pdf?v=2") == "f.pdf"
    assert pd.filename_from_url("https://x.com/my%20notes.pdf") == "my notes.pdf"
    assert pd.filename_from_url("https://x.com/download") == "download.pdf"


def test_unique_path_avoids_clobber(tmp_path):
    (tmp_path / "f.pdf").write_text("x")
    result = pd.unique_path(str(tmp_path), "f.pdf")
    assert result.endswith("f (1).pdf")
