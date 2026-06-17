"""Extra edge-case coverage for the pure link/filename helpers."""


def test_find_pdf_links_strips_whitespace_hrefs(pdf):
    html = '<a href="  spaced.pdf  ">s</a><a href="">empty</a>'
    links = pdf.find_pdf_links("https://site.test/x/", html)
    assert links == ["https://site.test/x/spaced.pdf"]


def test_find_pdf_links_empty_page(pdf):
    assert pdf.find_pdf_links("https://site.test/", "<html></html>") == []


def test_find_pdf_links_ignores_anchor_without_href(pdf):
    html = "<a>no href</a><a href='ok.pdf'>ok</a>"
    links = pdf.find_pdf_links("https://site.test/", html)
    assert links == ["https://site.test/ok.pdf"]


def test_filename_from_url_appends_pdf_extension(pdf):
    assert pdf.filename_from_url("https://x.com/paper?type=pdf") == "paper.pdf"


def test_filename_from_url_decodes_unicode(pdf):
    assert pdf.filename_from_url("https://x.com/r%C3%A9sum%C3%A9.pdf") == "résumé.pdf"


def test_unique_path_increments_counter(pdf, tmp_path):
    (tmp_path / "f.pdf").write_text("a")
    (tmp_path / "f (1).pdf").write_text("b")
    result = pdf.unique_path(str(tmp_path), "f.pdf")
    assert result.endswith("f (2).pdf")


def test_unique_path_returns_plain_when_free(pdf, tmp_path):
    result = pdf.unique_path(str(tmp_path), "fresh.pdf")
    assert result == str(tmp_path / "fresh.pdf")
