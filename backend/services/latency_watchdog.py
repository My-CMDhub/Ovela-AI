"""
services/latency_watchdog.py
============================
Post-call latency watchdog.

Sentry records where each voice turn spends its time; this runs after a call
completes, asks Gemini to read those spans, and compares the result against the
previous run. A regression is then reported by the system instead of being
noticed by whoever happens to be on the phone next.

Deliberately advisory: it logs and raises a Sentry message. It never changes
configuration or code.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import sentry_sdk

logger = logging.getLogger(__name__)

# The model's own time-to-first-token was measured swinging 574-1861ms on a
# byte-identical prompt, so a tighter threshold would report provider noise
# as a regression every other call.
REGRESSION_PCT = 40.0

# Spans need to reach Sentry's query API before they can be read back.
ANALYSIS_DELAY_S = 120

_last_run: Optional[Dict[str, Any]] = None
_in_flight = False


def compare_runs(prev: Optional[Dict[str, Any]], curr: Dict[str, Any]) -> Dict[str, Any]:
    """Diff two analysis runs by per-span median. Pure — no I/O."""
    result: Dict[str, Any] = {
        "baseline": prev is None,
        "regressions": [],
        "improvements": [],
        "new_spans": [],
    }
    curr_stats = curr.get("stats", {})
    if prev is None:
        result["new_spans"] = sorted(curr_stats)
        return result

    prev_stats = prev.get("stats", {})
    for span, stat in curr_stats.items():
        before = prev_stats.get(span, {}).get("median_ms")
        if before is None:
            result["new_spans"].append(span)
            continue
        after = stat.get("median_ms")
        if not before or after is None:
            continue
        change = round((after - before) / before * 100, 1)
        entry = {"span": span, "prev_ms": before, "curr_ms": after, "change_pct": change}
        if change >= REGRESSION_PCT:
            result["regressions"].append(entry)
        elif change <= -REGRESSION_PCT:
            result["improvements"].append(entry)

    result["regressions"].sort(key=lambda e: -e["change_pct"])
    result["improvements"].sort(key=lambda e: e["change_pct"])
    return result


def _run_analysis_blocking(period: str) -> Dict[str, Any]:
    """Sentry HTTP + Vertex call — both blocking, so this runs off the loop."""
    from scripts.analyze_trace import analyze
    return analyze(period=period)


async def _analyse_after_delay(call_sid: str, delay_s: int) -> None:
    global _last_run, _in_flight
    try:
        await asyncio.sleep(delay_s)
        current = await asyncio.to_thread(_run_analysis_blocking, "1h")
        if not current.get("span_count"):
            logger.info("🔭 [LatencyWatchdog] No voice spans yet for %s — skipping", call_sid)
            return

        diff = compare_runs(_last_run, current)
        _last_run = current

        if diff["baseline"]:
            logger.info(
                "🔭 [LatencyWatchdog] Baseline recorded from %s spans (%s)",
                current["span_count"], call_sid,
            )
        elif diff["regressions"]:
            top = diff["regressions"][0]
            message = (
                f"Voice latency regression: {top['span']} "
                f"{top['prev_ms']:.0f}ms -> {top['curr_ms']:.0f}ms (+{top['change_pct']}%)"
            )
            logger.warning("🔺 [LatencyWatchdog] %s", message)
            sentry_sdk.capture_message(message, level="warning")
        else:
            logger.info(
                "🔭 [LatencyWatchdog] No latency drift over %s spans", current["span_count"]
            )

        verdict = current.get("gemini_analysis") or ""
        if verdict:
            logger.info("🤖 [LatencyWatchdog] Gemini: %s", verdict.replace("\n", " ")[:600])
    except Exception as e:
        # Never let post-call analysis affect call handling.
        logger.warning("🟡 [LatencyWatchdog] Analysis skipped: %s", e)
    finally:
        _in_flight = False


def schedule_post_call_analysis(call_sid: str, delay_s: int = ANALYSIS_DELAY_S) -> bool:
    """
    Fire-and-forget. Returns whether a run was scheduled — a second call while
    one is pending is ignored rather than queued, so a busy hour cannot stack
    Gemini requests behind each other.
    """
    global _in_flight
    if _in_flight:
        logger.debug("🔭 [LatencyWatchdog] Analysis already pending; skipping %s", call_sid)
        return False
    _in_flight = True
    asyncio.create_task(_analyse_after_delay(call_sid, delay_s))
    return True
