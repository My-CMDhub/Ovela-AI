"""
scripts/analyze_trace.py — Gemini-powered Sentry trace bottleneck analysis.

Pulls the real `user_voice_turn_transaction` spans from Sentry, hands the raw
JSON to Gemini 2.5 Flash (Vertex AI / ADC), and asks it to identify the
latency bottleneck and rank remediations against the sub-800ms TTFA target.

Usage (from backend/):
    python -m scripts.analyze_trace                # last 14d
    python -m scripts.analyze_trace --period 24h
    python -m scripts.analyze_trace --save         # write to benchmarks/
"""

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# SENTRY_AUTH_TOKEN / SENTRY_ORG live in .env but are not part of Settings,
# so pydantic never puts them on os.environ.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SENTRY_API = "https://sentry.io/api/0"
TRANSACTION = "user_voice_turn_transaction"
TARGET_MS = 800


def fetch_spans(period: str) -> list[dict]:
    """Fetch voice-turn spans from Sentry's Discover API."""
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
        ("per_page", "100"),
    ]
    if project:
        params.append(("project", project))

    r = httpx.get(
        f"{SENTRY_API}/organizations/{org}/events/",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json().get("data", [])


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
            "median_ms": round(values[len(values) // 2], 2),
            "max_ms": round(values[-1], 2),
            "mean_ms": round(sum(values) / len(values), 2),
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
    return {
        "period": period,
        "span_count": len(spans),
        "stats": stats,
        "gemini_analysis": ask_gemini(stats, spans) if spans else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="14d", help="Sentry statsPeriod, e.g. 24h / 7d / 14d")
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
        spans = fetch_spans(args.period)
    if not spans:
        sys.exit(f"No '{TRANSACTION}' spans found in the last {args.period}. Place a call first.")

    stats = summarise(spans)
    print(f"\n📊 {len(spans)} spans over {args.period}\n")
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1]["mean_ms"]):
        print(f"  {name[:58]:60s} n={s['samples']:<3} median={s['median_ms']:>9.2f}ms  max={s['max_ms']:>9.2f}ms")

    print("\n🤖 Asking Gemini 2.5 Flash to diagnose...\n")
    verdict = ask_gemini(stats, spans)
    print(verdict)

    if args.save:
        out = {
            "generated_at": datetime.now(ZoneInfo("Australia/Melbourne")).isoformat(),
            "period": args.period,
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
