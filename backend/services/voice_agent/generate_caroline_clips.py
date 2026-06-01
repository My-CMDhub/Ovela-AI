#!/usr/bin/env python3
"""
Generate Caroline US system audio clips for Ovela AI.

Voice: Caroline US  (f9836c6e-a0bd-460e-9d3c-f7299fa60f94)
Output format: raw PCM µ-law, 8 kHz, no header  (.mulaw.raw)
Output dir: backend/services/voice_agent/audio/f9836c6e-a0bd-460e-9d3c-f7299fa60f94/

Run from repo root:
    /Applications/Journey\ of\ pro/Nona/backend/venv/bin/python \
        backend/services/voice_agent/generate_caroline_clips.py

Each key maps to ONE deterministic phrase (not a random pool) so playback is
always consistent with the voice identity across calls.
"""

import os
import sys
import time
import httpx
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY", "sk_car_JZh3ddFR2qCNA53rRfRg25")
CAROLINE_VOICE_ID = "f9836c6e-a0bd-460e-9d3c-f7299fa60f94"
OUTPUT_DIR = Path(__file__).resolve().parent / "audio" / CAROLINE_VOICE_ID

# ── Clip map: key → exact phrase to synthesise ───────────────────────────────
# Phrases are tuned for Ovela's Coal Creek Motel persona:
#   - Warm, concise, Australian-hospitality tone
#   - No markdown, no em-dashes, no spelled-out symbols
#   - Phonetically safe (no ordinals, no URLs, no booking references)
CLIPS: dict[str, str] = {
    "smart_greeting": (
        "Coal Creek Motel. This call is recorded. How can I help?"
    ),
    "silence_soft": (
        "Still there?"
    ),
    "silence_hard": (
        "Hello? Still with me?"
    ),
    "abuse_warning": (
        "I'm here to help with Coal Creek Motel enquiries. "
        "What dates were you thinking of staying?"
    ),
    "filler_short": (
        "Just a moment while I check that for you."
    ),
    "filler_long": (
        "Bear with me a sec, I'm checking the details."
    ),
    "transfer": (
        "I'll put you through now."
    ),
    "transfer_failed": (
        "I'm sorry, I couldn't complete the transfer. Let me take a message instead."
    ),
    "farewell": (
        "Thanks for calling Coal Creek. Take care."
    ),
    "duration_soft": (
        "We've been chatting for a while. I want to make sure I help you as quickly as possible."
    ),
}

CARTESIA_URL = "https://api.cartesia.ai/tts/bytes"
HEADERS = {
    "X-API-Key": CARTESIA_API_KEY,
    "Cartesia-Version": "2025-04-16",
    "Content-Type": "application/json",
}


def synthesise(text: str) -> bytes:
    payload = {
        "model_id": "sonic-3",
        "transcript": text,
        "voice": {"mode": "id", "id": CAROLINE_VOICE_ID},
        "output_format": {
            "container": "raw",
            "encoding": "pcm_mulaw",
            "sample_rate": 8000,
        },
        "language": "en",
    }
    resp = httpx.post(CARTESIA_URL, headers=HEADERS, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.content


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🎙️  Caroline US voice: {CAROLINE_VOICE_ID}")
    print(f"📁 Output directory : {OUTPUT_DIR}\n")

    success = 0
    failures: list[str] = []

    for clip_key, phrase in CLIPS.items():
        out_path = OUTPUT_DIR / f"{clip_key}.mulaw.raw"
        print(f"  ▶ [{clip_key}]  \"{phrase}\"")
        try:
            audio = synthesise(phrase)
            out_path.write_bytes(audio)
            duration_ms = len(audio) / 8.0  # 8000 samples/s × 1 byte/sample
            print(f"    ✅  {len(audio):,} bytes  ({duration_ms:.0f}ms)  → {out_path.name}")
            success += 1
        except Exception as exc:
            print(f"    ❌  FAILED: {exc}")
            failures.append(clip_key)
        # Cartesia rate-limit guard: 1 req/s is plenty safe
        time.sleep(0.4)

    print(f"\n{'='*60}")
    print(f"✅ Generated : {success}/{len(CLIPS)} clips")
    if failures:
        print(f"❌ Failed    : {', '.join(failures)}")
        sys.exit(1)
    else:
        print("🎉 All clips generated. Caroline voice cache is complete.")
        print()
        print("Next step: remove the 'blake_fallback' block in handler.py")
        print("           _get_clip_path() — Caroline folder now exists.")


if __name__ == "__main__":
    main()
