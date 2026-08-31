"""
scripts/probe_asr_confidence.py — what does Flux actually report on a hard name?

Deepgram Flux returns one transcript and no alternatives, so there is no n-best
list to fall back on. What it does return is `words`, each with its own
confidence, and the orchestrator throws that away. This asks whether it is worth
keeping: does the confidence on a misheard name actually drop, or does Flux
report a wrong name just as confidently as a right one?

No phone and no human. Cartesia speaks the line at 8 kHz mu-law — the exact
codec of the Twilio leg — and that audio is streamed into Flux the same way a
caller's audio is. It is not a real accent over a real carrier, so it is a floor
on the error rate, not a model of it. What it does measure honestly is the
relationship between what Flux heard and how sure it says it is.

Usage (from backend/):
    python -m scripts.probe_asr_confidence
    python -m scripts.probe_asr_confidence --text "My name is Dhruv Patel."
"""

import argparse
import asyncio
import base64
import json

from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge
from services.voice_agent.bridges.deepgram_standalone import DeepgramStandaloneBridge

FRAME_BYTES = 160          # 20 ms of 8 kHz mu-law, the Twilio frame size
MULAW_SILENCE = b"\xff"    # mu-law zero amplitude

# The utterance shape that matters: a caller saying who they are.
LINES = [
    "My name is Dhruv Patel.",
    "This is Priya Patel.",
    "It's Siobhan O'Connor.",
    "My name is Xiuying Zhang.",
    "This is Andrew Drew.",
    "My name is Mohammed Al-Rashid.",
    "It's Katherine Smyth.",
    "This is Catherine Smith.",
    "My name is Jean-Luc Beaumont.",
]


async def speak(text: str) -> bytes:
    """Synthesise one line and return it as raw 8 kHz mu-law."""
    tts = CartesiaStandaloneBridge()
    if not await tts.connect():
        raise RuntimeError("Cartesia would not connect")
    try:
        await tts.send_transcript_chunk("probe", text, continue_stream=False)
        chunks = []
        async for event in tts.receive_audio_events():
            kind = event.get("type")
            if kind == "chunk" and event.get("data"):
                chunks.append(base64.b64decode(event["data"]))
            elif kind == "done":
                break
            elif kind == "error":
                raise RuntimeError(f"Cartesia refused the line: {event}")
        return b"".join(chunks)
    finally:
        await tts.close()


async def hear(audio: bytes) -> list:
    """Stream audio into Flux at real time and collect every turn event."""
    stt = DeepgramStandaloneBridge()
    if not await stt.connect():
        raise RuntimeError("Deepgram would not connect")

    events = []

    async def collect():
        async for event in stt.receive_events():
            events.append(event)
            if event.get("event") == "EndOfTurn":
                return

    reader = asyncio.create_task(collect())
    try:
        for offset in range(0, len(audio), FRAME_BYTES):
            await stt.send_audio(audio[offset:offset + FRAME_BYTES])
            await asyncio.sleep(0.02)          # pace it like a live call
        # Flux ends the turn on silence, not on the socket closing.
        for _ in range(100):                   # 2 s of quiet
            await stt.send_audio(MULAW_SILENCE * FRAME_BYTES)
            await asyncio.sleep(0.02)
        await asyncio.wait_for(reader, timeout=5)
    except asyncio.TimeoutError:
        reader.cancel()
    finally:
        await stt.close()
    return events


def report(said: str, events: list) -> dict:
    turn = next((e for e in reversed(events) if e.get("event") == "EndOfTurn"), None)
    if not turn:
        kinds = sorted({e.get("event") or e.get("type") for e in events})
        print(f"\n  said  {said!r}\n  heard  — no EndOfTurn (saw {kinds})")
        return {"said": said, "heard": None, "words": []}

    heard = (turn.get("transcript") or "").strip()
    words = turn.get("words") or []
    print(f"\n  said   {said!r}")
    print(f"  heard  {heard!r}   end_of_turn_confidence={turn.get('end_of_turn_confidence')}")
    if words:
        rendered = "  ".join(
            f"{w.get('word')}({float(w.get('confidence', 0)):.2f})" for w in words
        )
        print(f"  words  {rendered}")
    else:
        print("  words  — none returned")
    return {"said": said, "heard": heard, "words": words,
            "end_of_turn_confidence": turn.get("end_of_turn_confidence")}


async def run(lines: list) -> list:
    out = []
    for line in lines:
        audio = await speak(line)
        print(f"\n[{len(audio)} bytes of mu-law = {len(audio) / 8000:.1f}s]", end="")
        out.append(report(line, await hear(audio)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="append", help="probe one line (repeatable)")
    ap.add_argument("--json", help="write the raw results to this path")
    args = ap.parse_args()
    results = asyncio.run(run(args.text or LINES))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
