"""Shared pytest fixtures and import wiring for the test suite.

Puts ``src/`` on ``sys.path`` once, so every test module can simply
``import PdfDownloader`` without repeating the path dance.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import PdfDownloader as pd  # noqa: E402


class FakeResponse:
    """A minimal stand-in for ``requests.Response``.

    Supports both the streaming path (context manager + ``iter_content``)
    used by :func:`download_file` and the plain ``.text`` path used by
    :func:`fetch_page`.
    """

    def __init__(self, *, text="", chunks=None, status_ok=True, exc=None):
        self.text = text
        self._chunks = chunks if chunks is not None else []
        self._status_ok = status_ok
        self._exc = exc

    def raise_for_status(self):
        if self._exc is not None:
            raise self._exc
        if not self._status_ok:
            import requests

            raise requests.HTTPError("simulated non-2xx response")

    def iter_content(self, chunk_size=1):  # noqa: ARG002 - signature parity
        for chunk in self._chunks:
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeSession:
    """Records requests and returns queued :class:`FakeResponse` objects."""

    def __init__(self, responses):
        # ``responses`` maps a URL -> FakeResponse (or an Exception to raise).
        self._responses = responses
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self._responses.get(url)
        if result is None:
            raise AssertionError(f"unexpected URL requested: {url}")
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def pdf():
    """The module under test."""
    return pd


@pytest.fixture
def fake_response():
    return FakeResponse


@pytest.fixture
def fake_session():
    return FakeSession


@pytest.fixture
def patch_session(monkeypatch):
    """Replace ``build_session`` so ``run`` uses our fake session.

    Returns a helper that installs a :class:`FakeSession` built from a
    ``{url: FakeResponse|Exception}`` mapping.
    """

    def _install(responses):
        session = FakeSession(responses)
        monkeypatch.setattr(pd, "build_session", lambda *a, **k: session)
        return session

    return _install
