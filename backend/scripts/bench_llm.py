"""
Time to first token under the payload the live call actually sends.

The production system prompt and all tools, one caller sentence, streamed
exactly as `cascaded_orchestrator` calls it. Three conditions, so the first
turn of a call can be taken apart instead of guessed at:

  cold    a new client (new TLS connection) and a prompt prefix OpenAI has
          never seen, so its prompt cache misses: the first turn of a call
          with neither warmed
  conn    a new client, but a prefix that was just sent: connection cost alone
  warm    one client reused, prefix cached: every later turn of a call

Usage (from backend/, costs a few cents):
    python -m scripts.bench_llm
    python -m scripts.bench_llm --models gpt-4.1-nano gpt-4o-mini --runs 10
    python -m scripts.bench_llm --models gpt-5.6-luna --extra '{"reasoning_effort": "none"}'
    python -m scripts.bench_llm --models <id> --base-url <provider's OpenAI-compatible URL> --key-env <ENV>
"""
import json
import os
import argparse
import asyncio
import statistics
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from core.config import settings
from services.voice_agent.functions.coalcreek_definitions import get_coalcreek_functions
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt

CALLER = "Hi there, I'm calling about my booking."


def _payload(prefix: str = ""):
    now = datetime.now(ZoneInfo("Australia/Melbourne"))
    prompt = get_coalcreek_prompt(now.strftime("%Y-%m-%d"), now.strftime("%I:%M %p"))
    messages = [
        {"role": "system", "content": prefix + prompt},
        {"role": "user", "content": CALLER},
    ]
    tools = [{"type": "function", "function": fn} for fn in get_coalcreek_functions()]
    return messages, tools


EXTRA = {}          # extra request fields, e.g. reasoning_effort for newer models
ENDPOINT = {}       # base_url / api_key for a non-OpenAI, OpenAI-compatible provider


async def _ttft(client: AsyncOpenAI, model: str, messages, tools):
    """Seconds to the first content or tool-call delta, plus usage."""
    t0 = time.perf_counter()
    stream = await client.chat.completions.create(
        model=model, messages=messages, tools=tools, stream=True,
        stream_options={"include_usage": True}, **EXTRA,
    )
    first, usage = None, None
    async for ev in stream:
        if ev.usage:
            usage = ev.usage
        if first is None and ev.choices:
            d = ev.choices[0].delta
            if d.content or d.tool_calls:
                first = time.perf_counter() - t0
    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
    return first, usage.prompt_tokens if usage else 0, cached


def _new_client():
    return AsyncOpenAI(**ENDPOINT) if ENDPOINT else AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


async def bench(model: str, runs: int):
    rows = {"cold": [], "conn": [], "warm": []}
    base_msgs, tools = _payload()
    shared = _new_client()
    # The first request this process makes pays one-off client costs (lazy
    # imports, model classes) on top of the network; a live call's first turn
    # pays them too if nothing warmed the client.
    first, _p, _c = await _ttft(shared, model, base_msgs, tools)
    print(f"{model:14} first request in process: {first*1000:.0f} ms")

    tokens = cached_warm = 0
    for _ in range(runs):
        # A unique first line changes the prefix, so the cache cannot hit.
        msgs, _t = _payload(prefix=f"[run {uuid.uuid4()}]\n")
        t, tokens, _c = await _ttft(_new_client(), model, msgs, tools)
        rows["cold"].append(t)
        t, _p, _c = await _ttft(_new_client(), model, base_msgs, tools)
        rows["conn"].append(t)
        t, _p, cached_warm = await _ttft(shared, model, base_msgs, tools)
        rows["warm"].append(t)
        # Three ~9k-token requests a run; the org shares a 200k tokens/min
        # limit with live calls, so pace it well under that.
        await asyncio.sleep(10)

    med = {k: statistics.median(v) * 1000 for k, v in rows.items()}
    print(f"{model:14} prompt={tokens} tok, cached on warm={cached_warm}, tools={len(tools)}, n={runs}")
    for k in ("cold", "conn", "warm"):
        print(f"  {k:5} median {med[k]:6.0f} ms   p90 {_pct(rows[k], .9)*1000:6.0f}   "
              f"p99 {_pct(rows[k], .99)*1000:6.0f}   (min {min(rows[k])*1000:.0f}, max {max(rows[k])*1000:.0f})")
    return med


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gpt-4.1-nano", "gpt-4o-mini"])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--extra", default="{}", help="JSON merged into every request")
    ap.add_argument("--base-url", help="an OpenAI-compatible endpoint (verify it in the provider's docs)")
    ap.add_argument("--key-env", help="environment variable holding that provider's key")
    args = ap.parse_args()
    EXTRA.update(json.loads(args.extra))
    if args.base_url:
        ENDPOINT.update(base_url=args.base_url, api_key=os.environ[args.key_env])
    for m in args.models:
        await bench(m, args.runs)


if __name__ == "__main__":
    asyncio.run(main())
