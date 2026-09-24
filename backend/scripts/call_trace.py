"""
One call's turns as JSON, in milliseconds from the moment Twilio rang us.

Adds no logging. It reads what the call already left behind and joins it:

  * Heroku's own log lines, which carry millisecond timestamps — the turn ends
    Deepgram reported, every OpenAI request that came back, every tool call,
    every barge-in, and the greeting warm-up.
  * Sentry's per-turn spans, which carry the durations the logs do not — how
    long the model took to first token, how long a tool ran, and the gap
    between the first token and the first audio chunk. Only with --sentry.

Per turn it also counts Flux's negotiation before the turn was called
(`eager_eot`, `turn_resumed`), the backchannels held while the agent spoke,
and marks `caller_not_done` when the caller carried on — the turn was dropped
before reaching the model (`superseded`), or they "barged in" within
EARLY_BARGE_MS of the turn being called. That is the log's view of an early answer. `scripts/turn_gaps.py` is the
audio's view, and the only one that knows the caller's real last word.

What it cannot tell you, because nothing records it:
  * when the caller REALLY stopped talking. `caller_stopped_ms` is when
    Deepgram Flux decided the turn had ended, which trails the last word by
    up to `eot_timeout_ms` (800 ms in the tenant's voice_settings). Measure
    the true stop off the dual-channel recording's caller track.
  * when the OpenAI request was SENT. Only its return is logged; with
    --sentry the send is back-calculated from the round's duration.
  * how much of an interrupted reply the caller had actually heard. The
    orchestrator keeps that word index but logs it at DEBUG, and the log level
    is hardcoded to INFO (main.py). The saved transcript shows the kept text.

Usage (from backend/):
    heroku logs -a ovela -n 1500 > /tmp/call.log
    python -m scripts.call_trace /tmp/call.log                    # last call in the log
    python -m scripts.call_trace /tmp/call.log --call CAxxxx --sentry 1h
    python -m scripts.call_trace - < /tmp/call.log > trace.json
"""
import argparse
import json
import re
import sys
from datetime import datetime

# Heroku prefixes every line with its own millisecond timestamp; the app's
# formatter adds a second one. The prefix is the one that is always there.
STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+[+\-]\d\d:\d\d) app\[")
EVENTS = (
    ("call", re.compile(r"Voice webhook from .* CallSid: (CA[0-9a-f]+)")),
    ("greeting", re.compile(r"Triggering initial greeting")),
    ("warm", re.compile(r"LLM warmed in (\d+) ms")),
    ("eot", re.compile(r"User finished turn: '(.*)'")),
    ("llm", re.compile(r"api\.openai\.com/v1/chat/completions \"HTTP/[\d.]+ 200 OK\"")),
    ("tool", re.compile(r"Tool call: (\w+)\(")),
    ("barge", re.compile(r"Barge-in triggered \((\w+)\)")),
    # Flux's turn negotiation. Each eager guess is a draft stage 1 would start;
    # each resume is one it would throw away — the ratio bounds its cost.
    ("eager", re.compile(r"EagerEndOfTurn received")),
    ("resumed", re.compile(r"TurnResumed — caller is still talking")),
    ("backchannel", re.compile(r"Backchannel — letting the agent finish: (.*)$")),
    ("end", re.compile(r"Transcript saved \| (CA[0-9a-f]+)")),
)


EARLY_BARGE_MS = 2500    # caller "interrupts" this soon after the turn was called: they weren't done


def parse_log(text):
    out = []
    for line in text.splitlines():
        stamp = STAMP.match(line)
        if not stamp:
            continue
        when = datetime.fromisoformat(stamp.group(1)).timestamp()
        for kind, pattern in EVENTS:
            found = pattern.search(line)
            if found:
                out.append((kind, when, found.groups()[0] if found.groups() else None))
                break
    return out


def sentry_turns(period, t0, t_end):
    """Per-turn span durations for the call's window, oldest turn first."""
    from scripts.analyze_trace import fetch_spans
    from collections import defaultdict

    by_trace = defaultdict(list)
    for span in fetch_spans(period):
        when = span.get("timestamp")
        if when and t0 <= datetime.fromisoformat(when).timestamp() <= t_end + 5:
            by_trace[span.get("trace")].append(span)
    turns = []
    for spans in sorted(by_trace.values(), key=lambda s: min(x["timestamp"] for x in s)):
        durations = {s.get("span.description"): s.get("span.duration", 0) for s in spans}
        # The span name carries the model, so match the prefix: a literal
        # "(gpt-4.1-nano)" went blank the day the model changed.
        round1 = next((v for k, v in durations.items()
                       if k and k.startswith("LLM round 1: request -> first token")), None)
        turns.append({
            "model_to_first_token_ms": round1,
            "speech_end_to_first_token_ms": durations.get("Span 1: User Speech Ended -> First Token Yielded"),
            "first_token_to_first_audio_ms": durations.get(
                "Span 3: First Token Yielded -> Cartesia First Audio Chunk Ingestion"),
            "tool_ms": {k[len("execute_tool "):]: v for k, v in durations.items()
                        if k and k.startswith("execute_tool ")},
        })
    return turns


def build(events, sentry=None):
    calls = [i for i, e in enumerate(events) if e[0] == "call"]
    if not calls:
        raise SystemExit("no 'Voice webhook' line in that log — wrong file, or the call rolled off")
    start = calls[-1]
    t0 = events[start][1]
    call_sid = events[start][2]
    trace = {"call_sid": call_sid, "started_at": datetime.fromtimestamp(t0).isoformat(),
             "warm_up_ms": None, "turns": []}
    turn = None
    negotiation = {"eager_eot": 0, "turn_resumed": 0}    # belongs to the turn it precedes
    for kind, when, value in events[start + 1:]:
        ms = round((when - t0) * 1000)
        if kind == "call":
            break
        if kind in ("eager", "resumed"):
            negotiation["eager_eot" if kind == "eager" else "turn_resumed"] += 1
        elif kind == "backchannel":
            if turn is not None:
                turn["backchannels_held"].append({"at_ms": ms, "said": value})
        elif kind == "warm":
            trace["warm_up_ms"] = int(value)
        elif kind == "greeting":
            trace["greeting_ms"] = ms
        elif kind == "eot":
            turn = {"turn": len(trace["turns"]) + 1, "caller_stopped_ms": ms,
                    "caller_said": value, "model_returned_ms": [], "tools": [],
                    "barge_in": None, "audio_started_ms": None,
                    "backchannels_held": [], **negotiation}
            negotiation = {"eager_eot": 0, "turn_resumed": 0}
            if trace["turns"] and not trace["turns"][-1]["model_returned_ms"]:
                # the previous turn never reached the model: Flux called it over,
                # the caller carried on, and the worker dropped it for this one
                trace["turns"][-1]["superseded"] = True
            trace["turns"].append(turn)
        elif turn is None:
            continue            # before the first turn: the greeting's own round
        elif kind == "llm":
            turn["model_returned_ms"].append(ms)
            for tool in turn["tools"]:
                if tool["end_ms"] is None:
                    tool["end_ms"] = ms      # the next model round begins after it
        elif kind == "tool":
            turn["tools"].append({"name": value, "start_ms": ms, "end_ms": None})
        elif kind == "barge":
            turn["barge_in"] = {"detected_ms": ms, "reason": value,
                                "action": "audio cut; remaining reply discarded; "
                                          "heard part kept in history"}
        elif kind == "end":
            trace["ended_ms"] = ms

    for i, t in enumerate(trace["turns"]):
        barge = t["barge_in"]
        # 20 Sep, turn 3: Flux called "...family suite for four people?" over,
        # the caller went on "checking in Friday..." and "barged in" 1.56 s
        # later — finishing their own sentence. A real interruption came 7.6 s in.
        # ponytail: fixed window; tune it against turn_gaps.py's audio verdicts.
        if t.get("superseded") or (barge and barge["detected_ms"] - t["caller_stopped_ms"] < EARLY_BARGE_MS):
            t["caller_not_done"] = True
        s = (sentry or [])[i] if sentry and i < len(sentry) else {}
        span1, span3 = s.get("speech_end_to_first_token_ms"), s.get("first_token_to_first_audio_ms")
        if span1 is not None and span3 is not None:
            t["audio_started_ms"] = round(t["caller_stopped_ms"] + span1 + span3)
        if s.get("model_to_first_token_ms") and t["model_returned_ms"]:
            t["model_sent_ms"] = round(t["model_returned_ms"][0] - s["model_to_first_token_ms"])
        for tool in t["tools"]:
            ran = (s.get("tool_ms") or {}).get(tool["name"])
            if ran is not None:
                tool["ran_ms"] = round(ran)
        t["sentry"] = s or None
    return trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="file written by `heroku logs`, or - for stdin")
    ap.add_argument("--call", help="CallSid to pick out (default: the last call in the log)")
    ap.add_argument("--sentry", help="also join Sentry spans over this period, e.g. 1h")
    args = ap.parse_args()

    text = sys.stdin.read() if args.log == "-" else open(args.log, encoding="utf-8").read()
    events = parse_log(text)
    if args.call:
        keep, seen = [], False
        for e in events:
            if e[0] == "call":
                seen = e[2] == args.call
            if seen:
                keep.append(e)
        events = keep
    spans = None
    if args.sentry:
        calls = [e for e in events if e[0] == "call"]
        ends = [e for e in events if e[0] == "end"]
        if calls:
            spans = sentry_turns(args.sentry, calls[-1][1], (ends[-1][1] if ends else calls[-1][1] + 600))
    print(json.dumps(build(events, spans), indent=2))


def _selfcheck():
    stamp = "2026-09-20T05:48:{:06.3f}+00:00 app[web.1]: "
    lines = [(0.0, "Voice webhook from +61 CallSid: CAabc123"),
             (5.0, "⚡ [CascadedOrchestrator] EagerEndOfTurn received. Pre-warming LLM..."),
             (5.1, "🔄 [CascadedOrchestrator] TurnResumed — caller is still talking."),
             (6.0, "🗣️ [CascadedOrchestrator] User finished turn: 'I need to change'"),
             (6.4, "🗣️ [CascadedOrchestrator] User finished turn: 'my booking'"),
             (6.9, 'POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"'),
             (8.0, "🔇 [CascadedOrchestrator] Backchannel — letting the agent finish: 'Mhmm.'"),
             (9.0, "🛑 [CascadedOrchestrator] Barge-in triggered (sustained_speech). Cutting audio!"),
             (11.0, "🗣️ [CascadedOrchestrator] User finished turn: 'no, the suite'"),
             (11.5, 'POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"'),
             (12.0, "🛑 [CascadedOrchestrator] Barge-in triggered (sustained_speech). Cutting audio!")]
    trace = build(parse_log("\n".join(stamp.format(s) + msg for s, msg in lines)))
    first, second, third = trace["turns"]
    assert (first["eager_eot"], first["turn_resumed"], first.get("caller_not_done")) == (1, 1, True), first
    assert (second["eager_eot"], second.get("caller_not_done")) == (0, None), second   # barged 2.6 s in
    assert second["backchannels_held"] == [{"at_ms": 8000, "said": "'Mhmm.'"}], second
    assert third.get("caller_not_done") is True, third                                # barged 1.0 s in
    print("selfcheck ok")


if __name__ == "__main__":
    _selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
