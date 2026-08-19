"""
tests/test_latency_watchdog.py
=============================
The watchdog runs after every completed call and compares this run's span
medians against the previous run's, so a latency regression is reported by
the system rather than noticed by whoever happens to be on the phone.
"""

import pytest

from services.latency_watchdog import compare_runs, REGRESSION_PCT


def _stats(**names):
    return {name: {"median_ms": ms, "samples": 5} for name, ms in names.items()}


class TestCompareRuns:
    def test_reports_a_regression_beyond_the_threshold(self):
        prev = {"stats": _stats(user_voice_turn_transaction=800.0)}
        curr = {"stats": _stats(user_voice_turn_transaction=1200.0)}

        result = compare_runs(prev, curr)

        assert result["regressions"], "a 50% slowdown must be reported"
        top = result["regressions"][0]
        assert top["span"] == "user_voice_turn_transaction"
        assert top["prev_ms"] == 800.0 and top["curr_ms"] == 1200.0
        assert top["change_pct"] == 50.0

    def test_stays_quiet_inside_normal_variance(self):
        """
        Measured: the model's own time-to-first-token swings 574-1861ms on a
        byte-identical prompt. A watchdog that fires on that is noise.
        """
        prev = {"stats": _stats(user_voice_turn_transaction=800.0)}
        curr = {"stats": _stats(user_voice_turn_transaction=800.0 * (1 + (REGRESSION_PCT - 1) / 100))}

        assert compare_runs(prev, curr)["regressions"] == []

    def test_improvements_are_reported_but_never_as_regressions(self):
        prev = {"stats": _stats(user_voice_turn_transaction=2000.0)}
        curr = {"stats": _stats(user_voice_turn_transaction=900.0)}

        result = compare_runs(prev, curr)

        assert result["regressions"] == []
        assert result["improvements"][0]["change_pct"] == -55.0

    def test_new_and_missing_spans_do_not_crash_the_comparison(self):
        prev = {"stats": _stats(old_span=100.0)}
        curr = {"stats": _stats(brand_new_span=100.0)}

        result = compare_runs(prev, curr)

        assert result["regressions"] == [] and result["improvements"] == []
        assert "brand_new_span" in result["new_spans"]

    def test_first_ever_run_has_nothing_to_compare_against(self):
        result = compare_runs(None, {"stats": _stats(user_voice_turn_transaction=900.0)})
        assert result["baseline"] is True
        assert result["regressions"] == []
