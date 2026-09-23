"""
Replay a real call's caller track into Deepgram Flux and keep everything it says.

The live pipeline logs only that EagerEndOfTurn / EndOfTurn arrived. It keeps
neither Flux's end-of-turn confidence nor the audio time each event refers to,
so nobody can say how long Flux waited after the caller's last word, or what a
different threshold would have done. This finds out without a phone: the
caller channel of a dual-channel Twilio recording is exactly the audio Flux
heard live (the inbound leg, 8 kHz), streamed back at real time through the
same bridge the orchestrator uses.

Output: every TurnInfo event as {rx_s, event, confidence, audio_end_s, transcript},
where rx_s is when it arrived measured from the first audio frame sent. With
--json the whole stream is kept, including every Update's confidence, so a
threshold can be re-judged offline without re-streaming.

Costs Deepgram streaming minutes (the length of the recording). Not a pytest.

Usage (from backend/):
    python -m scripts.flux_replay ../docs/evidence/take3-booking.wav
    python -m scripts.flux_replay call.wav --eager 0.3 --seconds 20 --json out.json
"""
import argparse
import asyncio
import json
import subprocess
import time

from scripts.turn_gaps import channels, spurts
from services.voice_agent.bridges.deepgram_standalone import DeepgramStandaloneBridge

FRAME = 160                      # 20 ms of 8 kHz mu-law, the Twilio frame
# The tenant's voice_settings as read from Appwrite on 23 Sep 2026.
PROD = {"eot": 0.7, "eager": 0.5, "timeout": 800}


def caller_mulaw(path, channel, seconds=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-af", f"pan=mono|c0=c{channel}",
           "-ar", "8000", "-f", "mulaw"]
    if seconds:
        cmd[5:5] = ["-t", str(seconds)]
    return subprocess.run(cmd + ["-"], capture_output=True, check=True).stdout


async def stream(audio, eot, eager, timeout):
    stt = DeepgramStandaloneBridge(eot_threshold=eot, eager_eot_threshold=eager,
                                   eot_timeout_ms=timeout)
    if not await stt.connect():
        raise SystemExit("Deepgram would not connect")
    events, t0 = [], None

    async def collect():
        async for evt in stt.receive_events():
            events.append((time.monotonic() - t0 if t0 else 0.0, evt))

    reader = asyncio.create_task(collect())
    try:
        t0 = time.monotonic()
        frames = [audio[i:i + FRAME] for i in range(0, len(audio), FRAME)]
        frames += [b"\xff" * FRAME] * 150              # 3 s of quiet so the last turn can end
        for n, frame in enumerate(frames):
            await stt.send_audio(frame)
            # absolute schedule: sleep drift would stretch the call's own clock
            await asyncio.sleep(max(0.0, t0 + (n + 1) * 0.02 - time.monotonic()))
        await asyncio.sleep(1.0)
    finally:
        await stt.close()
        reader.cancel()
    return events


def turn_events(events):
    out = []
    for rx, e in events:
        if e.get("type") != "TurnInfo":
            if e.get("type") not in ("Connected",):
                out.append({"rx_s": round(rx, 3), "event": e.get("type"), "raw": e})
            continue
        out.append({"rx_s": round(rx, 3), "event": e.get("event"),
                    "confidence": e.get("end_of_turn_confidence"),
                    "audio_end_s": e.get("audio_window_end"),
                    "transcript": e.get("transcript", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--caller", type=int, choices=(0, 1),
                    help="caller's channel (default: the one that does not greet)")
    ap.add_argument("--eot", type=float, default=PROD["eot"])
    ap.add_argument("--eager", type=float, default=PROD["eager"])
    ap.add_argument("--timeout", type=int, default=PROD["timeout"])
    ap.add_argument("--seconds", type=float, help="only the first N seconds")
    ap.add_argument("--json", help="write every event here")
    args = ap.parse_args()

    tracks = [spurts(p) for p in channels(args.recording)]
    agent = min((0, 1), key=lambda i: tracks[i][0][0] if tracks[i] else 1e9)
    caller = args.caller if args.caller is not None else 1 - agent
    audio = caller_mulaw(args.recording, caller, args.seconds)
    events = turn_events(asyncio.run(stream(audio, args.eot, args.eager, args.timeout)))
    result = {"recording": args.recording, "caller_channel": caller,
              "settings": {"eot": args.eot, "eager": args.eager, "timeout_ms": args.timeout},
              "caller_spurts": tracks[caller], "events": events}
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=1)
    for e in events:
        if e["event"] != "Update":
            print(json.dumps({k: v for k, v in e.items() if k != "raw"})[:200])


if __name__ == "__main__":
    main()
