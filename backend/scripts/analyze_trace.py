"""
scripts/analyze_trace.py — Gemini-powered Sentry trace bottleneck analysis.

Pulls the real `user_voice_turn_transaction` spans from Sentry, hands the raw
JSON to Gemini 2.5 Flash (Vertex AI / ADC), and asks it to identify the
latency bottleneck and rank remediations against the sub-800ms TTFA target.

Usage (from backend/):
    python -m scripts.analyze_trace                # last 14d
    python -m scripts.analyze_trace --period 24h
    python -m scripts.analyze_trace --save         # write to benchmarks/

Read the WINDOW line, not the --period label. Sentry pages at 100 rows; this
pages until the period is exhausted or --max-spans is hit, and prints the
timestamps actually covered. A busy hour can fill the cap on its own, and a
period that reports a narrower window than it asked for was truncated.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# SENTRY_AUTH_TOKEN / SENTRY_ORG live in .env but are not part of Settings,
# so pydantic never puts them on os.environ.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SENTRY_API = "https://sentry.io/api/0"
TRANSACTION = "user_voice_turn_transaction"
TARGET_MS = 800
PAGE_SIZE = 100      # Sentry's maximum per page on the events endpoint
MAX_SPANS = 2000     # safety valve; one 70-minute call alone produced 130 turns

# A stage that reports under this is reporting instrumentation, not work:
# Span 3 has come back at 0.8ms, which is not a synthesis time.
IMPLAUSIBLE_MS = 10.0

logger = logging.getLogger(__name__)

# What the last fetch actually covered. Sentry's scan budget makes a long
# period return a SAMPLE and then report no further pages, so the row count
# is not the turn count unless dataScanned == "full".
LAST_FETCH: dict = {}


def window_of(spans: list[dict]) -> tuple[str, str]:
    """Oldest and newest timestamp actually returned, '' when unknown."""
    stamps = sorted(s["timestamp"] for s in spans if s.get("timestamp"))
    return (stamps[0], stamps[-1]) if stamps else ("", "")


def fetch_spans(period: str, max_spans: int = MAX_SPANS) -> list[dict]:
    """
    Fetch voice-turn spans from Sentry's Discover API, following pagination.

    One page is 100 rows sorted newest-first. Returning a single page silently
    turns any --period into "the most recent 100 turns": a `--period 14d` read
    here once covered a 7-minute window and reported it as two weeks, which
    read as a 3x regression that had not happened. Always page.
    """
    token = os.getenv("SENTRY_AUTH_TOKEN", "")
    org = os.getenv("SENTRY_ORG", "")
    project = os.getenv("SENTRY_PROJECT", "")
    if not (token and org):
        # RuntimeError, not sys.exit: this is imported by the post-call
        # watchdog, where a SystemExit would escape its `except Exception`.
        raise RuntimeError("SENTRY_AUTH_TOKEN and SENTRY_ORG must be set")

    params = [
        ("field", "id"),
        ("field", "span.description"),
        ("field", "span.duration"),
        ("field", "timestamp"),
        ("field", "trace"),
        ("query", f"transaction:{TRANSACTION}"),
        ("statsPeriod", period),
        ("dataset", "spans"),
        ("sort", "-timestamp"),
        ("per_page", str(PAGE_SIZE)),
    ]
    if project:
        params.append(("project", project))

    spans: list[dict] = []
    cursor: str | None = None
    scanned = "unknown"
    pages = 0
    with httpx.Client(timeout=30.0, headers={"Authorization": f"Bearer {token}"}) as client:
        while True:
            page_params = params + ([("cursor", cursor)] if cursor else [])
            r = client.get(f"{SENTRY_API}/organizations/{org}/events/", params=page_params)
            r.raise_for_status()
            body = r.json()
            spans.extend(body.get("data", []))
            pages += 1
            # "full" = every matching row was read. "partial" = the query hit
            # Sentry's scan budget and sampled: 90d returned 200 rows and
            # claimed the end, while 30d over the same calls returned 1530.
            if body.get("meta", {}).get("dataScanned") == "partial":
                scanned = "partial"
            elif scanned != "partial":
                scanned = body.get("meta", {}).get("dataScanned", "unknown")

            nxt = r.links.get("next") or {}
            cursor = nxt.get("cursor")
            # Sentry always emits rel="next"; results="false" is the real end.
            if nxt.get("results") != "true" or not cursor or len(spans) >= max_spans:
                break

    oldest, newest = window_of(spans)
    LAST_FETCH.clear()
    LAST_FETCH.update(
        period=period, rows=len(spans), pages=pages, data_scanned=scanned,
        capped=len(spans) >= max_spans, oldest=oldest, newest=newest,
    )
    if scanned == "partial":
        logger.warning(
            "Sentry sampled this query (dataScanned=partial) over %s — %s rows are a "
            "SUBSET, not the turn count. Ask for a shorter period.", period, len(spans)
        )
    return spans


def by_day(spans: list[dict], name: str) -> dict[str, dict]:
    """Per-day stats for one span, because a period median hides the story."""
    days: dict[str, list[float]] = {}
    for s in spans:
        if (s.get("span.description") or "(unnamed)") != name:
            continue
        if s.get("span.duration") is None or not s.get("timestamp"):
            continue
        days.setdefault(s["timestamp"][:10], []).append(float(s["span.duration"]))
    out = {}
    for day, values in sorted(days.items()):
        values.sort()
        out[day] = {
            "samples": len(values),
            "median_ms": round(median(values), 2),
            "max_ms": round(values[-1], 2),
        }
    return out


def summarise(spans: list[dict]) -> dict:
    """Aggregate per-span-name stats so Gemini reasons over numbers, not noise."""
    by_name: dict[str, list[float]] = {}
    for s in spans:
        name = s.get("span.description") or "(unnamed)"
        duration = s.get("span.duration")
        if duration is not None:
            by_name.setdefault(name, []).append(float(duration))

    stats = {}
    for name, values in by_name.items():
        values.sort()
        stats[name] = {
            "samples": len(values),
            "min_ms": round(values[0], 2),
            "median_ms": round(median(values), 2),
            "max_ms": round(values[-1], 2),
            "mean_ms": round(sum(values) / len(values), 2),
        }
    return stats


def by_kind(spans: list[dict]) -> dict[str, dict]:
    """
    Split whole turns into plain and tool turns, per day.

    Pooling the two is the trap that produced a 27% improvement headline out of
    a change in turn mix: a plain turn runs ~600ms, a turn that calls a tool
    runs 1.7-2.2s, and the two samples being compared were 36% and 16% tool
    turns. A trace with one `LLM round` child is a plain turn; two or more is a
    tool turn, because each tool call costs another round.
    """
    traces: dict[str, list[dict]] = {}
    for s in spans:
        traces.setdefault(s.get("trace") or "", []).append(s)

    out: dict[str, dict] = {}
    for rows in traces.values():
        turn = next(
            (r for r in rows if (r.get("span.description") or "") == TRANSACTION), None
        )
        if not turn or turn.get("span.duration") is None:
            continue
        rounds = sum(
            1 for r in rows if (r.get("span.description") or "").startswith("LLM round")
        )
        kind = "plain (no tool)" if rounds <= 1 else "tool  (2+ rounds)"
        key = f"{turn['timestamp'][:10]}  {kind}"
        out.setdefault(key, []).append(float(turn["span.duration"]))

    stats = {}
    for key, values in sorted(out.items()):
        values.sort()
        stats[key] = {
            "samples": len(values),
            "median_ms": round(median(values), 2),
            "max_ms": round(values[-1], 2),
        }
    return stats


PROMPT = """You are a performance engineer analysing a real production voice-AI
pipeline running over Twilio PSTN. The target is sub-{target}ms TTFA (time to
first audio byte after the caller stops speaking).

Pipeline architecture (cascaded, self-hosted stages):
  1. Local webrtcvad  — acoustic barge-in detection (20ms frames)
  2. Deepgram Flux v2 — STT + semantic end-of-turn
  3. OpenAI GPT       — conversational driver with 12 tool definitions
  4. Cartesia sonic-3 — streaming mu-law TTS straight to Twilio

Sentry span semantics:
  "user_voice_turn_transaction"                  = the whole turn (TTFA)
  "Span 1: User Speech Ended -> First Token"     = everything before the model speaks
  "Span 3: First Token -> Cartesia First Audio"  = TTS synthesis
Span 1 is decomposed by these children, so attribute its cost between them:
  "LLM round N: request -> first token"          = op llm.stream, model wait only
  "Tool: <name>"                                 = op tool.execute, one per tool call
Transaction data:
  llm.cached_tokens / llm.prompt_tokens          = prompt-cache hit for that turn.
  A cached_tokens of 0 with a large prompt_tokens means the cache was COLD.

Aggregated span statistics (milliseconds):
{stats}

Raw span sample (most recent, truncated):
{raw}

Answer strictly as JSON with these keys:
  "bottleneck_span"      : the span name dominating latency
  "bottleneck_share_pct" : its share of total turn time, integer
  "evidence"             : one sentence citing specific numbers above
  "root_causes"          : list of 2-4 likely technical causes, most probable first
  "remediations"         : list of objects {{"action": str, "expected_saving_ms": int, "risk": "low"|"medium"|"high"}}
  "verdict"              : does the pipeline currently meet the {target}ms target? one sentence
Return ONLY the JSON object, no markdown fences.
"""


def ask_gemini(stats: dict, raw: list[dict]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    prompt = PROMPT.format(
        target=TARGET_MS,
        stats=json.dumps(stats, indent=2),
        raw=json.dumps(raw[:12], indent=2),
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1),
    )
    return (response.text or "").strip()


def analyze(period: str = "1h", spans: list[dict] | None = None) -> dict:
    """
    Run one full analysis pass and return it. Shared by the CLI and by the
    post-call watchdog so both read the pipeline the same way.
    """
    spans = fetch_spans(period) if spans is None else spans
    stats = summarise(spans)
    oldest, newest = window_of(spans)
    return {
        "period": period,
        "window": {"oldest": oldest, "newest": newest},
        "coverage": dict(LAST_FETCH),
        "span_count": len(spans),
        "stats": stats,
        "gemini_analysis": ask_gemini(stats, spans) if spans else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="14d", help="Sentry statsPeriod, e.g. 24h / 7d / 14d")
    ap.add_argument("--max-spans", type=int, default=MAX_SPANS,
                    help=f"stop paging after this many spans (default {MAX_SPANS})")
    ap.add_argument("--by-day", action="store_true",
                    help="break the whole-turn span down per day instead of one median")
    ap.add_argument("--by-kind", action="store_true",
                    help="split each day's turns into plain and tool turns — never pool them")
    ap.add_argument("--no-gemini", action="store_true",
                    help="numbers only — skip the Vertex call")
    ap.add_argument("--save", action="store_true", help="write result under benchmarks/")
    ap.add_argument(
        "--input",
        help="Read spans from a JSON file instead of the Sentry API "
             "(use when SENTRY_AUTH_TOKEN lacks the event:read scope)",
    )
    args = ap.parse_args()

    if args.input:
        with open(args.input) as f:
            spans = json.load(f)
        print(f"📥 Loaded {len(spans)} spans from {args.input}")
    else:
        spans = fetch_spans(args.period, max_spans=args.max_spans)
    if not spans:
        sys.exit(f"No '{TRANSACTION}' spans found in the last {args.period}. Place a call first.")

    stats = summarise(spans)
    oldest, newest = window_of(spans)
    print(f"\n📊 {len(spans)} spans, --period {args.period}")
    print(f"   WINDOW {oldest or '?'} → {newest or '?'}  (this, not the period, is what you measured)")
    if LAST_FETCH.get("data_scanned") == "partial":
        print(f"   ⚠️  SAMPLED: Sentry reported dataScanned=partial for {args.period}. "
              f"These {len(spans)} rows are a subset — re-run with a shorter --period "
              f"before quoting any of it.")
    if len(spans) >= args.max_spans:
        print(f"   ⚠️  CAPPED at --max-spans {args.max_spans}: the window above is "
              f"newest-first and does NOT cover the full {args.period}.")
    print()
    for name, st in sorted(stats.items(), key=lambda kv: -kv[1]["mean_ms"]):
        flag = "  ⚠️ implausible — instrumentation, do not quote" if st["median_ms"] < IMPLAUSIBLE_MS else ""
        print(f"  {name[:58]:60s} n={st['samples']:<4} median={st['median_ms']:>9.2f}ms  max={st['max_ms']:>9.2f}ms{flag}")

    if args.by_day:
        print(f"\n📅 {TRANSACTION} per day (a period median mixes releases):")
        for day, st in by_day(spans, TRANSACTION).items():
            print(f"  {day}  n={st['samples']:<4} median={st['median_ms']:>9.2f}ms  max={st['max_ms']:>9.2f}ms")

    if args.by_kind:
        print("\n🔧 whole turns split by kind (a plain turn and a tool turn are not comparable):")
        for key, st in by_kind(spans).items():
            print(f"  {key:34s} n={st['samples']:<4} median={st['median_ms']:>9.2f}ms  max={st['max_ms']:>9.2f}ms")

    verdict = ""
    if not args.no_gemini:
        print("\n🤖 Asking Gemini 2.5 Flash to diagnose...\n")
        verdict = ask_gemini(stats, spans)
        print(verdict)

    if args.save:
        out = {
            "generated_at": datetime.now(ZoneInfo("Australia/Melbourne")).isoformat(),
            "period": args.period,
            "window": {"oldest": oldest, "newest": newest},
            "coverage": dict(LAST_FETCH),
            "span_count": len(spans),
            "stats": stats,
            "gemini_analysis": verdict,
        }
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "benchmarks", "trace_analysis.json",
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n💾 Saved → {path}")


if __name__ == "__main__":
    main()
