"""
Time to first token for Claude under the payload the live call sends.

The Anthropic twin of scripts/bench_llm.py: the production system prompt, all
12 tools, one caller sentence, streamed. A separate file because Claude's
OpenAI-compatibility layer does not support prompt caching (Anthropic's own
docs), so timing Claude through it would resend ~9k uncached tokens every turn
and measure the shim, not the model. Here the prompt is cached the way a real
integration would cache it: tools -> system, with a breakpoint on the system.

Same three conditions as bench_llm: cold (a prefix never seen, new client),
conn (new client, cached prefix) and warm (reused client, cached prefix).

Usage (from backend/, costs a few cents):
    python -m scripts.bench_claude --runs 30
"""
import argparse
import asyncio
import os
import statistics
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from services.voice_agent.functions.coalcreek_definitions import get_coalcreek_functions
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt

CALLER = "Hi there, I'm calling about my booking."   # same line as bench_llm


def _payload(prefix: str = ""):
    now = datetime.now(ZoneInfo("Australia/Melbourne"))
    prompt = get_coalcreek_prompt(now.strftime("%Y-%m-%d"), now.strftime("%I:%M %p"))
    system = [{"type": "text", "text": prefix + prompt, "cache_control": {"type": "ephemeral"}}]
    tools = [{"name": fn["name"], "description": fn.get("description", ""),
              "input_schema": fn["parameters"]} for fn in get_coalcreek_functions()]
    return system, tools


async def _ttft(client, model, system, tools):
    """Seconds to the first text delta or tool_use block, plus cache usage."""
    t0 = time.perf_counter()
    first, cached, uncached = None, 0, 0
    stream = await client.messages.create(
        model=model, max_tokens=1024, system=system, tools=tools, stream=True,
        messages=[{"role": "user", "content": CALLER}],
    )
    async for event in stream:
        if event.type == "message_start":
            usage = event.message.usage
            cached = usage.cache_read_input_tokens or 0
            uncached = (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
        elif first is None and (
            (event.type == "content_block_start" and event.content_block.type == "tool_use")
            or (event.type == "content_block_delta" and event.delta.type == "text_delta")
        ):
            first = time.perf_counter() - t0
    return first, cached, cached + uncached


def _new_client():
    return anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


async def bench(model, runs):
    rows = {"cold": [], "conn": [], "warm": []}
    system, tools = _payload()
    shared = _new_client()
    first, _c, _t = await _ttft(shared, model, system, tools)
    print(f"{model:18} first request in process: {first*1000:.0f} ms")
    cached_warm = total = 0
    for _ in range(runs):
        cold_system, _t = _payload(prefix=f"[run {uuid.uuid4()}]\n")
        t, _c, _p = await _ttft(_new_client(), model, cold_system, tools)
        rows["cold"].append(t)
        t, _c, _p = await _ttft(_new_client(), model, system, tools)
        rows["conn"].append(t)
        t, cached_warm, total = await _ttft(shared, model, system, tools)
        rows["warm"].append(t)
        await asyncio.sleep(10)
    print(f"{model:18} prompt={total} tok, cached on warm={cached_warm}, tools={len(tools)}, n={runs}")
    for k in ("cold", "conn", "warm"):
        v = rows[k]
        print(f"  {k:5} median {statistics.median(v)*1000:6.0f} ms   p90 {_pct(v, .9)*1000:6.0f}   "
              f"p99 {_pct(v, .99)*1000:6.0f}   (min {min(v)*1000:.0f}, max {max(v)*1000:.0f})")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["claude-haiku-4-5"])
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()
    for m in args.models:
        await bench(m, args.runs)


if __name__ == "__main__":
    asyncio.run(main())
