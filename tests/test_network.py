"""Tests for the network-touching helpers, using fake sessions (no real IO)."""

import requests


def test_build_session_sets_user_agent(pdf):
    session = pdf.build_session()
    assert session.headers["User-Agent"] == pdf.DEFAULT_UA
    assert isinstance(session, requests.Session)


def test_build_session_honours_custom_user_agent(pdf):
    session = pdf.build_session("MyBot/9.9")
    assert session.headers["User-Agent"] == "MyBot/9.9"


def test_fetch_page_returns_text(pdf, fake_session, fake_response):
    session = fake_session({"https://x.test/": fake_response(text="<html>ok</html>")})
    assert pdf.fetch_page(session, "https://x.test/") == "<html>ok</html>"
    # timeout is always passed so a hung server can't wedge the run.
    assert session.calls[0][1].get("timeout") == 30


def test_fetch_page_raises_on_error_status(pdf, fake_session, fake_response):
    session = fake_session({"https://x.test/": fake_response(status_ok=False)})
    try:
        pdf.fetch_page(session, "https://x.test/")
    except requests.HTTPError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected HTTPError to propagate")


def test_download_file_streams_chunks_to_disk(pdf, tmp_path, fake_session, fake_response):
    url = "https://x.test/report.pdf"
    session = fake_session(
        {url: fake_response(chunks=[b"abc", b"", b"def"])}
    )
    dest = pdf.download_file(session, url, str(tmp_path))
    assert dest == str(tmp_path / "report.pdf")
    # Empty chunks are skipped, real ones concatenated in order.
    assert (tmp_path / "report.pdf").read_bytes() == b"abcdef"
    # Streaming must be requested so large PDFs don't load fully into memory.
    assert session.calls[0][1].get("stream") is True


def test_download_file_uses_unique_path_when_clobbering(pdf, tmp_path, fake_session, fake_response):
    (tmp_path / "report.pdf").write_bytes(b"old")
    url = "https://x.test/report.pdf"
    session = fake_session({url: fake_response(chunks=[b"new"])})
    dest = pdf.download_file(session, url, str(tmp_path))
    assert dest.endswith("report (1).pdf")
    assert (tmp_path / "report.pdf").read_bytes() == b"old"
    assert (tmp_path / "report (1).pdf").read_bytes() == b"new"


def test_download_file_propagates_http_error(pdf, tmp_path, fake_session, fake_response):
    url = "https://x.test/broken.pdf"
    session = fake_session({url: fake_response(status_ok=False)})
    try:
        pdf.download_file(session, url, str(tmp_path))
    except requests.HTTPError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected HTTPError to propagate")
    # Nothing should be left behind on a failed download's directory scan.
    assert list(tmp_path.iterdir()) == [] or all(
        p.name == "broken.pdf" for p in tmp_path.iterdir()
    )
