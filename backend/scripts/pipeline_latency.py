"""
How fast does each candidate model answer through OUR pipeline, in whole
conversations, with tools running and callers who interrupt?

scripts/bench_llm.py times one request in isolation. This times every model
request and every turn inside `CascadedPipelineOrchestrator._default_llm_callback`
— the code a live call runs — across the replay scenarios. No pass/fail on
wording: each turn records its timings, the tools the model chose and what it
said, so the decisions can be read rather than scored against a string.

  * Read tools (lookup_booking, check_availability, ...) run for real against
    Appwrite. hang_up_call / transfer_to_staff run for real too: the dispatcher
    only returns an `action`, and with no phone line nothing is dialled.
  * Write tools are SIMULATED with the real success shape — a harness must not
    raise real bookings, Stripe sessions or emails in the production database.
  * Interruptions: before ~30% of caller turns (same turns for every model), the
    agent's previous reply is cut after 3-12 words with the pipeline's own
    `prune_conversation_history`, which is what `trigger_barge_in` records.
  * Each scenario starts with a warm-up request, as the live greeting does.
  * Claude runs on Anthropic's native API through a small adapter, because the
    OpenAI-compatibility layer does not cache — it would time the shim.
  * Privacy is still reported (another guest's details spoken), never gated.

Usage (from backend/):
    python -m scripts.pipeline_latency --model gpt-4.1-nano --runs 5
    python -m scripts.pipeline_latency --model gpt-5.6-luna --extra '{"reasoning_effort":"none"}'
    python -m scripts.pipeline_latency --model claude-haiku-4-5 --anthropic
"""
import argparse
import asyncio
import json
import os
import random
import time
from types import SimpleNamespace as NS

from scripts import replay_conversation as rc
from services.voice_agent.interruption import prune_conversation_history

SIMULATED = {"create_booking_request", "update_guest_info", "resend_payment_link",
             "resend_payment_confirmation", "request_human_callback"}


def _simulated(name, args):
    if name == "create_booking_request":
        return {"success": True, "booking_reference": "CC-SIM001",
                "guest_name": args.get("guest_name", ""), "guest_email": args.get("guest_email", ""),
                "check_in_date": args.get("check_in_date", ""),
                "check_out_date": args.get("check_out_date", ""),
                "room_type": args.get("room_type", ""),
                "message": "I've placed a hold. Your reference is C C, S I M 0 0 1. "
                           "A payment link has been sent to your email."}
    return {"success": True, "message": "Done."}


class AnthropicChat:
    """Just enough of `openai.AsyncOpenAI().chat.completions` for the orchestrator.

    Converts the OpenAI-shaped request to the Messages API with the prompt and
    tools cached (tools -> system render order, breakpoint on the prompt), and
    streams back chunks in the shape `_default_llm_callback` reads. Every
    system message after the first is hoisted into a second, uncached system
    block — Haiku 4.5 has no mid-conversation system role — which moves the
    call-state note out of its position before the caller's last line.
    """

    def __init__(self, api_key):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.chat = NS(completions=NS(create=self.create))

    @staticmethod
    def _convert(messages):
        systems = [m["content"] for m in messages if m["role"] == "system"]
        system = [{"type": "text", "text": systems[0], "cache_control": {"type": "ephemeral"}}]
        if systems[1:]:
            system.append({"type": "text", "text": "\n\n".join(systems[1:])})
        out = []
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "user":
                role, blocks = "user", [{"type": "text", "text": m["content"] or "…"}]
            elif m["role"] == "assistant":
                role, blocks = "assistant", []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"],
                                   "input": json.loads(tc["function"]["arguments"] or "{}")})
                if not blocks:
                    continue
            else:                                   # tool result
                role, blocks = "user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"],
                                         "content": m["content"]}]
            if out and out[-1]["role"] == role:
                out[-1]["content"].extend(blocks)
            else:
                out.append({"role": role, "content": blocks})
        return system, out

    async def create(self, model, messages, tools=None, max_completion_tokens=None, **_):
        system, msgs = self._convert(messages)
        tools = [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
                  "input_schema": t["function"]["parameters"]} for t in (tools or [])]
        stream = await self._client.messages.create(
            model=model, max_tokens=max_completion_tokens or 1024, system=system,
            tools=tools, messages=msgs, stream=True)
        return self._chunks(stream)

    @staticmethod
    async def _chunks(stream):
        def chunk(content=None, tool_calls=None):
            return NS(usage=None, choices=[NS(delta=NS(content=content, tool_calls=tool_calls))])
        tool_index, cached, total = {}, 0, 0
        async for ev in stream:
            if ev.type == "message_start":
                u = ev.message.usage
                cached = u.cache_read_input_tokens or 0
                total = cached + (u.input_tokens or 0) + (u.cache_creation_input_tokens or 0)
            elif ev.type == "content_block_start" and ev.content_block.type == "tool_use":
                tool_index[ev.index] = len(tool_index)
                yield chunk(tool_calls=[NS(index=tool_index[ev.index], id=ev.content_block.id,
                                           function=NS(name=ev.content_block.name, arguments=""))])
            elif ev.type == "content_block_delta" and ev.delta.type == "text_delta":
                yield chunk(content=ev.delta.text)
            elif ev.type == "content_block_delta" and ev.delta.type == "input_json_delta":
                yield chunk(tool_calls=[NS(index=tool_index[ev.index], id=None,
                                           function=NS(name=None, arguments=ev.delta.partial_json))])
        yield NS(choices=[], usage=NS(prompt_tokens=total,
                                      prompt_tokens_details=NS(cached_tokens=cached)))


def _timed(create, requests):
    """Wrap chat.completions.create so every request's time to first event is kept."""
    async def timed_create(*a, **kw):
        t0 = time.perf_counter()
        stream = await create(*a, **kw)
        record = {"ttft_ms": None}
        requests.append(record)

        async def events():
            async for ev in stream:
                if record["ttft_ms"] is None and ev.choices:
                    d = ev.choices[0].delta
                    if d.content or d.tool_calls:
                        record["ttft_ms"] = round((time.perf_counter() - t0) * 1000)
                yield ev
        return events()
    return timed_create


async def run_scenario(sc, run, model, anthropic_key):
    agent, *_ = await rc._build_agent(sc.caller_phone, allow_writes=True)
    if anthropic_key:
        agent._openai = AnthropicChat(anthropic_key)
    tools_used = []
    real_execute = agent.dispatcher.execute

    async def execute(name, args, context=None):
        tools_used.append(name)
        return _simulated(name, args) if name in SIMULATED else await real_execute(name, args, context)
    agent.dispatcher.execute = execute

    # The live greeting warms the model with turn 1's own prefix.
    m, prefix, tools = await agent._request_prefix()
    warm = await agent._openai.chat.completions.create(
        model=m, messages=prefix + [{"role": "user", "content": "Hello?"}], tools=tools,
        stream=True, max_completion_tokens=16)
    async for _ in warm:
        pass

    requests = []
    agent._openai.chat.completions.create = _timed(agent._openai.chat.completions.create, requests)
    history, turns = [], []
    for n, turn in enumerate(sc.turns, 1):
        rng = random.Random(f"{sc.key}:{n}")                 # same cuts for every model
        interrupted = None
        if n > 1 and rng.random() < 0.3 and history and history[-1]["role"] == "assistant":
            interrupted = rng.randint(3, 12)
            history[:] = prune_conversation_history(history, confirmed_word_index=interrupted)
        before_req, before_tools = len(requests), len(tools_used)
        history.append({"role": "user", "content": turn.says})
        agent.history = history
        t0, first, parts, error = time.perf_counter(), None, [], None
        try:
            async for piece in agent._default_llm_callback(history):
                if first is None and piece.strip():
                    first = time.perf_counter() - t0
                parts.append(piece)
        except Exception as exc:                           # a provider error is data, not a crash
            error = f"{type(exc).__name__}: {exc}"[:200]
        reply = "".join(parts)
        history.append({"role": "assistant", "content": reply})
        turns.append({
            "run": run, "scenario": sc.key, "turn": n, "caller": turn.says,
            "interrupted_after_words": interrupted,
            "first_words_ms": round(first * 1000) if first else None,
            "full_reply_ms": round((time.perf_counter() - t0) * 1000),
            "model_ttft_ms": [r["ttft_ms"] for r in requests[before_req:]],
            "tools": tools_used[before_tools:],
            "privacy_flags": [b for b in turn.never_says if rc._mentions(reply, b)],
            "reply": reply, "error": error,
        })
    return turns


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def summarise(model, rows):
    ttft = [t for r in rows for t in r["model_ttft_ms"] if t is not None]
    first = [r["first_words_ms"] for r in rows if r["first_words_ms"]]
    plain = [r["full_reply_ms"] for r in rows if not r["tools"] and not r["error"]]
    tool = [r["full_reply_ms"] for r in rows if r["tools"] and not r["error"]]
    counts = {}
    for r in rows:
        for name in r["tools"]:
            counts[name] = counts.get(name, 0) + 1
    def line(xs):
        return f"p50 {_pct(xs, .5)}  p90 {_pct(xs, .9)}  p99 {_pct(xs, .99)}  (n={len(xs)})"
    print(f"\n{model}")
    print(f"  model request -> first token   {line(ttft)} ms")
    print(f"  turn -> first words (heard)    {line(first)} ms")
    print(f"  full reply, no tool            {line(plain)} ms")
    print(f"  full reply, with tools         {line(tool)} ms")
    print(f"  turns {len(rows)}, interrupted {sum(1 for r in rows if r['interrupted_after_words'])}, "
          f"errors {sum(1 for r in rows if r['error'])}, "
          f"privacy flags {sum(len(r['privacy_flags']) for r in rows)}")
    print(f"  tools chosen {dict(sorted(counts.items()))}")


async def main_async(args):
    rc._pin_clock()
    rc.MODEL_OVERRIDE.update(model=args.model, extra=json.loads(args.extra),
                             base_url=None, key_env=None)
    key = os.environ["ANTHROPIC_API_KEY"] if args.anthropic else None
    rows = []
    for run in range(1, args.runs + 1):
        for sc in rc.SCENARIOS:
            rows += await run_scenario(sc, run, args.model, key)
        print(f"run {run}/{args.runs} done", flush=True)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(rows, fh, indent=1)
    summarise(args.model, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--extra", default="{}", help="JSON merged into every model request")
    ap.add_argument("--anthropic", action="store_true", help="run on Anthropic's native API")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", help="write every turn as JSON")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
