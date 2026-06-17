"""Tests for argument parsing and the end-to-end ``run`` / ``main`` flow."""

import requests


# --------------------------------------------------------------------------- #
# parse_args                                                                    #
# --------------------------------------------------------------------------- #
def test_parse_args_defaults(pdf):
    ns = pdf.parse_args([])
    assert ns.url is None
    assert ns.output == "."
    assert ns.dry_run is False
    assert ns.user_agent == pdf.DEFAULT_UA


def test_parse_args_full(pdf):
    ns = pdf.parse_args(
        ["https://e.edu/notes", "-o", "out", "--dry-run", "--user-agent", "Bot/1"]
    )
    assert ns.url == "https://e.edu/notes"
    assert ns.output == "out"
    assert ns.dry_run is True
    assert ns.user_agent == "Bot/1"


# --------------------------------------------------------------------------- #
# run                                                                           #
# --------------------------------------------------------------------------- #
PAGE = '<a href="a.pdf">a</a><a href="b.pdf">b</a><a href="x.html">x</a>'


def test_run_fetch_failure_returns_1(pdf, patch_session, capsys):
    patch_session({"https://e.test/": requests.ConnectionError("boom")})
    rc = pdf.run("https://e.test/", ".", dry_run=True, user_agent="U")
    assert rc == 1
    assert "Could not open the page" in capsys.readouterr().err


def test_run_no_links_returns_0(pdf, patch_session, fake_response, capsys):
    patch_session({"https://e.test/": fake_response(text="<p>nothing here</p>")})
    rc = pdf.run("https://e.test/", ".", dry_run=True, user_agent="U")
    assert rc == 0
    assert "No PDF links found" in capsys.readouterr().out


def test_run_dry_run_lists_without_downloading(pdf, patch_session, fake_response, tmp_path, capsys):
    patch_session({"https://e.test/": fake_response(text=PAGE)})
    rc = pdf.run("https://e.test/", str(tmp_path), dry_run=True, user_agent="U")
    assert rc == 0
    out = capsys.readouterr().out
    assert "Found 2 PDF link(s)" in out
    assert "dry run" in out
    # Dry run must not create the output directory or any files.
    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def test_run_downloads_all_links(pdf, patch_session, fake_response, tmp_path, capsys):
    patch_session(
        {
            "https://e.test/": fake_response(text=PAGE),
            "https://e.test/a.pdf": fake_response(chunks=[b"AAA"]),
            "https://e.test/b.pdf": fake_response(chunks=[b"BBB"]),
        }
    )
    rc = pdf.run("https://e.test/", str(tmp_path), dry_run=False, user_agent="U")
    assert rc == 0
    assert (tmp_path / "a.pdf").read_bytes() == b"AAA"
    assert (tmp_path / "b.pdf").read_bytes() == b"BBB"
    assert "2 downloaded, 0 failed" in capsys.readouterr().out


def test_run_reports_partial_failures_with_nonzero_exit(pdf, patch_session, fake_response, tmp_path, capsys):
    patch_session(
        {
            "https://e.test/": fake_response(text=PAGE),
            "https://e.test/a.pdf": fake_response(chunks=[b"AAA"]),
            "https://e.test/b.pdf": requests.ConnectionError("dropped"),
        }
    )
    rc = pdf.run("https://e.test/", str(tmp_path), dry_run=False, user_agent="U")
    assert rc == 1
    assert (tmp_path / "a.pdf").read_bytes() == b"AAA"
    assert not (tmp_path / "b.pdf").exists()
    captured = capsys.readouterr()
    assert "1 downloaded, 1 failed" in captured.out
    assert "FAIL" in captured.err


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def test_main_empty_url_returns_2(pdf, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *_: "   ")
    rc = pdf.main([])
    assert rc == 2
    assert "No URL provided" in capsys.readouterr().err


def test_main_prompts_when_no_url_given(pdf, monkeypatch):
    captured = {}

    def fake_run(url, output_dir, dry_run, user_agent, *a, **k):
        captured["url"] = url
        return 0

    monkeypatch.setattr("builtins.input", lambda *_: "example.edu/notes")
    monkeypatch.setattr(pdf, "run", fake_run)
    rc = pdf.main([])
    assert rc == 0
    # A bare host gets a default https:// scheme prepended.
    assert captured["url"] == "https://example.edu/notes"


def test_main_keeps_explicit_scheme(pdf, monkeypatch):
    captured = {}

    def fake_run(url, *a, **k):
        captured["url"] = url
        return 0

    monkeypatch.setattr(pdf, "run", fake_run)
    rc = pdf.main(["http://plain.test/page"])
    assert rc == 0
    assert captured["url"] == "http://plain.test/page"
