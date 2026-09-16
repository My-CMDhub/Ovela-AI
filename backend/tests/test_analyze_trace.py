"""
tests/test_analyze_trace.py
===========================
The trace reader has to be honest about what it read.

Two real incidents are pinned here. `--period 14d` once returned Sentry's
newest 100 rows — a 7-minute window — and reported it as two weeks, which
read as a 3x regression that had never happened. And `--period 90d` returns
200 sampled rows with `meta.dataScanned == "partial"` while the same calls
over 30d return 1530: the row count is only a turn count when the scan was
full.

No network: the Sentry client is replaced with pages built here.
"""

import os

import pytest

os.environ.setdefault("SENTRY_AUTH_TOKEN", "test-token")
os.environ.setdefault("SENTRY_ORG", "test-org")

from scripts import analyze_trace as at  # noqa: E402


class _FakeResponse:
    def __init__(self, rows, scanned, next_results):
        self._rows = rows
        self._scanned = scanned
        self.links = {
            "next": {"rel": "next", "results": next_results, "cursor": "0:100:0"},
        }

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": self._rows, "meta": {"dataScanned": self._scanned}}


class _FakeClient:
    """Serves prepared pages in order and records how many were asked for."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        self.calls += 1
        return self.pages[min(self.calls - 1, len(self.pages) - 1)]


def _row(day, name, ms):
    return {
        "span.description": name,
        "span.duration": ms,
        "timestamp": f"2026-09-{day:02d}T04:00:00+00:00",
        "trace": f"t{day}{int(ms)}",
    }


def _install(monkeypatch, pages):
    client = _FakeClient(pages)
    monkeypatch.setattr(at.httpx, "Client", lambda **kw: client)
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SENTRY_ORG", "test-org")
    return client


def test_pagination_reads_every_page(monkeypatch):
    """Stopping at page one is what mislabelled a 7-minute window as 14 days."""
    page1 = _FakeResponse([_row(3, "user_voice_turn_transaction", 600.0)] * 100, "full", "true")
    page2 = _FakeResponse([_row(4, "user_voice_turn_transaction", 700.0)] * 40, "full", "false")
    client = _install(monkeypatch, [page1, page2])

    spans = at.fetch_spans("14d")

    assert client.calls == 2
    assert len(spans) == 140
    assert at.LAST_FETCH["data_scanned"] == "full"
    assert at.LAST_FETCH["capped"] is False


def test_max_spans_caps_and_says_so(monkeypatch):
    page = _FakeResponse([_row(3, "user_voice_turn_transaction", 600.0)] * 100, "full", "true")
    _install(monkeypatch, [page])

    spans = at.fetch_spans("14d", max_spans=150)

    assert len(spans) == 200          # paging is per-page, so the cap is a ceiling
    assert at.LAST_FETCH["capped"] is True


def test_sampled_query_is_reported_as_partial(monkeypatch):
    """90d comes back sampled; the row count must not pass as a turn count."""
    page1 = _FakeResponse([_row(3, "user_voice_turn_transaction", 600.0)] * 100, "full", "true")
    page2 = _FakeResponse([_row(4, "user_voice_turn_transaction", 700.0)] * 100, "partial", "false")
    _install(monkeypatch, [page1, page2])

    at.fetch_spans("90d")

    assert at.LAST_FETCH["data_scanned"] == "partial"


def test_window_is_what_was_read_not_what_was_asked_for():
    spans = [_row(3, "x", 1.0), _row(16, "x", 2.0), _row(5, "x", 3.0)]
    oldest, newest = at.window_of(spans)
    assert oldest.startswith("2026-09-03")
    assert newest.startswith("2026-09-16")
    assert at.window_of([]) == ("", "")


def test_by_day_separates_a_bad_day_from_a_period_median():
    """The 14d median read 1498ms only because one slow provider day had n=130."""
    name = "user_voice_turn_transaction"
    spans = (
        [_row(3, name, 672.0)] * 3
        + [_row(5, name, 1597.0)] * 9
        + [_row(16, name, 420.0)]
    )
    days = at.by_day(spans, name)

    assert list(days) == ["2026-09-03", "2026-09-05", "2026-09-16"]
    assert days["2026-09-05"]["samples"] == 9
    assert days["2026-09-03"]["median_ms"] == 672.0
    # Pooled, the bad day owns the median. Per day, it is visibly one day.
    pooled = at.summarise(spans)[name]["median_ms"]
    assert pooled == 1597.0


def test_missing_credentials_raise_not_exit(monkeypatch):
    """The watchdog catches Exception; SystemExit would escape it."""
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.setattr(at.os, "getenv", lambda k, d="": d)
    with pytest.raises(RuntimeError):
        at.fetch_spans("1h")
