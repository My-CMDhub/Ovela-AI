"""
Should Coal Creek's voice move from Cartesia to Deepgram Flux TTS?

An offline A/B: the same receptionist lines through each provider's streaming
WebSocket, in the exact audio format Twilio plays (8 kHz mu-law), timed from
the moment the text is sent. Two outputs, one per question:

  * Does it sound better?  A blind listening pack: each line's takes are
    written as NN_A.wav / NN_B.wav (/ NN_C.wav) with the provider behind each
    letter shuffled per line (seeded). Listen, note your preference, then
    open key.json.
  * Is it faster?  results.csv (every request) and a printed table of
    time-to-first-audio p50/p90, total synthesis time and error counts.

Nothing in the app is imported or changed; only the API keys are needed.

Providers (--providers, comma-separated):
  cartesia  what production runs: services/voice_agent/bridges/cartesia_standalone.py,
            mirrored message for message (sonic-3, the production voice id,
            raw pcm_mulaw 8000 Hz, cartesia_version=2024-06-10, continue=false;
            ends on {"type": "done"}).
  flux      Deepgram Flux TTS, wss://api.deepgram.com/v2/speak, model
            flux-sharon-en (the only Australian Flux voice). Sends Speak +
            Flush and reads until SpeechMetadata, which the docs name as the
            end of a turn's audio (audio frames still arrive AFTER Flushed).
  aura2     Deepgram Aura-2, wss://api.deepgram.com/v1/speak, model
            aura-2-theia-en (Australian, female). Sends Speak + Flush and
            reads until Flushed.

Timings: TTFB is from just before the first send to the first audio frame;
total is to the provider's end-of-audio message; connect time is recorded
separately and is in neither. Each request opens its own connection. Before
the measured runs each provider does one warm-up request that is discarded.
Only run 1's audio goes into the listening pack.

Usage (from backend/; needs CARTESIA_API_KEY / DEEPGRAM_API_KEY in the
environment or backend/.env — a provider without its key is skipped):
    python -m scripts.tts_ab
    python -m scripts.tts_ab --providers cartesia,flux,aura2 --runs 5 --out tts_ab_out
    python -m scripts.tts_ab --cartesia-model sonic-3.6 --region au --seed 7
    python -m scripts.tts_ab --corpus my_lines.txt --runs 1 --delay 2

Output directory (--out, default tts_ab_out/):
    listen/NN_A.wav ...  16-bit PCM WAVs at 8 kHz, decoded from the mu-law
    listen/lines.txt     what each NN says
    key.json             which provider is behind each letter
    results.csv          one row per request (all runs, warm-up excluded)
    raw/NN_<provider>.ulaw  the exact bytes Twilio would play

Protocol references (checked October 2026):
    Cartesia   https://docs.cartesia.ai/api-reference/tts/websocket
    Flux TTS   https://developers.deepgram.com/docs/flux-tts/overview
               https://developers.deepgram.com/docs/flux-tts/quickstart
               https://developers.deepgram.com/docs/flux-tts/client-messages
               https://developers.deepgram.com/docs/flux-tts/server-messages
               https://developers.deepgram.com/docs/flux-tts/voices
    Aura-2     https://developers.deepgram.com/reference/text-to-speech/speak-streaming
               https://developers.deepgram.com/docs/tts-models
    Regions    https://developers.deepgram.com/reference/regional-endpoints
               (api.au.deepgram.com serves /v1/speak and /v2/speak)
"""
import argparse
import asyncio
import base64
import csv
import json
import os
import random
import statistics
import time
import uuid
import warnings
import wave
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import websockets

try:  # stdlib until 3.13 (deprecated in 3.11+); a decode table stands in after
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop  # type: ignore
except ImportError:  # pragma: no cover - exercised on 3.13+
    audioop = None

SAMPLE_RATE = 8000          # Twilio media streams: 8 kHz, 8-bit mu-law, mono
BACKEND = Path(__file__).resolve().parents[1]

CORPUS = [
    "Thanks for calling Coal Creek Motel in Korumburra, this is the front desk. How can I help you today?",
    "Let me check that for you.",
    "A queen room is $129.50 per night, so two nights comes to a total of $259.",
    "The family room is $189 per night, including a continental breakfast for up to four guests.",
    "So that's ada dot lovelace at gmail dot com. Is that right?",
    "I've sent the payment link to j dot nguyen 84 at outlook dot com dot au.",
    "Your booking reference is C C dash 4 7 B 9.",
    "Just to confirm, that's C C dash 4 7 B 9, for two adults.",
    "You're booked in from Friday the 10th of October, checking out Sunday the 12th.",
    "Check-in is from 2:30 p.m., and check-out is by 10 a.m.",
    "Reception closes at 8:30 p.m., but we can leave your key in the after-hours lockbox.",
    "We're on the South Gippsland Highway, about ten minutes from Leongatha.",
    "Phillip Island is about an hour's drive, and Wonthaggi is around forty minutes.",
    "If you're coming from Melbourne, follow the M1 and then the South Gippsland Highway into Korumburra.",
    "Could you spell your surname for me? I have S I O B H A N.",
    "Thank you, Siobhan. I've found your booking.",
    "I'm sorry, we're fully booked on Saturday night. Would Sunday suit you instead?",
    "I'm really sorry about that. I'll pass it on to the manager and someone will call you back this afternoon.",
    "Our deluxe spa room has a king bed, a double spa and a view over the hills. It's $219 per night midweek, and on weekends there's a two night minimum stay.",
    "Yes, we're pet friendly in two of our ground floor rooms, for a $25 cleaning fee per stay.",
    "There's free parking right outside your room, and plenty of space for a boat trailer.",
    "Free Wi-Fi is included, and the password is on the card in your room.",
    "Mm-hmm, no worries.",
    "Can I get a phone number in case we need to reach you? That's zero four one two, three four five, six seven eight.",
    "Your deposit of $64.75 has been received, and the balance is due on arrival.",
    "You can cancel free of charge up to 48 hours before check-in.",
    "The Austral Hotel and the Korumburra Bakery are both a short walk up Commercial Street.",
    "Coal Creek Community Park and Museum is just across the road, and it's open Thursday to Sunday.",
    "Is there anything else I can help you with?",
    "Thanks for calling, have a lovely day. Bye now.",
]


# ── mu-law → 16-bit PCM WAV ──────────────────────────────────────────────────

def _ulaw_sample(u: int) -> int:
    """G.711 mu-law byte to a 16-bit linear sample (the audioop.ulaw2lin result)."""
    u = ~u & 0xFF
    sign, exponent, mantissa = u & 0x80, (u >> 4) & 0x07, u & 0x0F
    magnitude = (((mantissa << 3) + 0x84) << exponent) - 0x84
    return -magnitude if sign else magnitude


ULAW_TABLE = [_ulaw_sample(u) for u in range(256)]


def ulaw_to_pcm16(data: bytes, use_audioop: bool = True) -> bytes:
    """Little-endian 16-bit PCM from mu-law bytes."""
    if use_audioop and audioop is not None:
        return audioop.ulaw2lin(data, 2)
    out = bytearray(len(data) * 2)
    for i, b in enumerate(data):
        out[2 * i:2 * i + 2] = (ULAW_TABLE[b] & 0xFFFF).to_bytes(2, "little")
    return bytes(out)


def write_wav(path: Path, ulaw: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(ulaw_to_pcm16(ulaw))


# ── Providers ────────────────────────────────────────────────────────────────

class ProviderError(Exception):
    """The provider sent an error frame or closed before the end of audio."""


@dataclass
class Synth:
    audio: bytes = b""
    ttfb_ms: float | None = None
    total_ms: float | None = None
    error: str = ""

    @property
    def audio_s(self) -> float:
        return len(self.audio) / SAMPLE_RATE


class _Timer:
    """Times one request: t0 at the first send, TTFB at the first audio byte."""

    def __init__(self, result: Synth, clock):
        self.r, self.clock = result, clock
        self.t0 = clock()

    def audio(self, chunk: bytes) -> None:
        if chunk and self.r.ttfb_ms is None:
            self.r.ttfb_ms = (self.clock() - self.t0) * 1000
        self.r.audio += chunk

    def done(self) -> None:
        self.r.total_ms = (self.clock() - self.t0) * 1000


class Provider:
    name = ""
    key_env = ""

    def __init__(self, key: str):
        self.key = key

    def url(self) -> str:
        raise NotImplementedError

    def headers(self) -> dict:
        return {}

    async def synthesize(self, ws, text: str, clock=time.perf_counter) -> Synth:
        raise NotImplementedError

    def redact(self, msg: str) -> str:
        return msg.replace(self.key, "***") if self.key else msg


class Cartesia(Provider):
    """Same URL, payload and end condition as CartesiaStandaloneBridge."""
    name, key_env = "cartesia", "CARTESIA_API_KEY"

    def __init__(self, key: str, model: str = "sonic-3",
                 voice: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
                 version: str = "2024-06-10"):
        super().__init__(key)
        self.model, self.voice, self.version = model, voice, version

    def url(self) -> str:
        return (f"wss://api.cartesia.ai/tts/websocket?api_key={self.key}"
                f"&cartesia_version={self.version}")

    def payload(self, text: str, context_id: str) -> dict:
        return {
            "context_id": context_id,
            "model_id": self.model,
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice},
            "output_format": {"container": "raw", "encoding": "pcm_mulaw",
                              "sample_rate": SAMPLE_RATE},
            "continue": False,
        }

    async def synthesize(self, ws, text, clock=time.perf_counter):
        r = Synth()
        timer = _Timer(r, clock)
        await ws.send(json.dumps(self.payload(text, f"ab-{uuid.uuid4().hex[:12]}")))
        async for msg in ws:
            if not isinstance(msg, str):
                continue
            data = json.loads(msg)
            kind = data.get("type")
            if kind == "chunk" and data.get("data"):
                timer.audio(base64.b64decode(data["data"]))
            elif kind == "error":
                raise ProviderError(f"{data.get('status_code', '')} "
                                    f"{data.get('message') or data.get('error') or data}".strip())
            if kind == "done" or data.get("done") is True:
                timer.done()
                return r
        raise ProviderError("connection closed before done")


class _Deepgram(Provider):
    key_env = "DEEPGRAM_API_KEY"
    path = ""
    end_type = ""

    def __init__(self, key: str, model: str, region: str = ""):
        super().__init__(key)
        self.model = model
        self.host = f"api.{region}.deepgram.com" if region else "api.deepgram.com"

    def url(self) -> str:
        q = urlencode({"model": self.model, "encoding": "mulaw", "sample_rate": SAMPLE_RATE})
        return f"wss://{self.host}{self.path}?{q}"

    def headers(self) -> dict:
        return {"Authorization": f"Token {self.key}"}

    async def synthesize(self, ws, text, clock=time.perf_counter):
        r = Synth()
        timer = _Timer(r, clock)
        await ws.send(json.dumps({"type": "Speak", "text": text}))
        await ws.send(json.dumps({"type": "Flush"}))
        async for msg in ws:
            if isinstance(msg, (bytes, bytearray)):
                timer.audio(bytes(msg))
                continue
            data = json.loads(msg)
            kind = data.get("type")
            if kind == "Error":
                raise ProviderError(f"{data.get('code', '')} {data.get('description', '')}".strip())
            if kind == self.end_type:
                timer.done()
                try:
                    await ws.send(json.dumps({"type": "Close"}))
                except Exception:
                    pass
                return r
        raise ProviderError(f"connection closed before {self.end_type}")


class Flux(_Deepgram):
    # Flushed means "all the text is in"; audio keeps coming until SpeechMetadata.
    name, path, end_type = "flux", "/v2/speak", "SpeechMetadata"


class Aura2(_Deepgram):
    name, path, end_type = "aura2", "/v1/speak", "Flushed"


async def _ws_connect(url: str, headers: dict):
    """websockets >= 14 takes additional_headers, older releases extra_headers."""
    kw = {"open_timeout": 10, "max_size": None}
    if not headers:
        return await websockets.connect(url, **kw)
    try:
        return await websockets.connect(url, additional_headers=headers, **kw)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, **kw)


@dataclass
class Row:
    provider: str
    idx: int
    run: int
    text: str
    connect_ms: float | None = None
    ttfb_ms: float | None = None
    total_ms: float | None = None
    audio_s: float = 0.0
    bytes: int = 0
    error: str = ""
    audio: bytes = field(default=b"", repr=False)


async def run_one(p: Provider, idx: int, run: int, text: str, timeout: float) -> Row:
    """Connect, synthesize one line, close. Errors land in the row, never raise."""
    row = Row(p.name, idx, run, text)
    ws = None
    try:
        t = time.perf_counter()
        ws = await _ws_connect(p.url(), p.headers())
        row.connect_ms = (time.perf_counter() - t) * 1000
        r = await asyncio.wait_for(p.synthesize(ws, text), timeout)
        row.ttfb_ms, row.total_ms, row.audio = r.ttfb_ms, r.total_ms, r.audio
        row.audio_s, row.bytes = r.audio_s, len(r.audio)
        if not r.audio:
            row.error = "no audio"
    except asyncio.TimeoutError:
        row.error = f"timeout after {timeout:.0f}s"
    except Exception as e:  # noqa: BLE001 - every failure is a result here
        row.error = p.redact(f"{type(e).__name__}: {e}")[:300]
    finally:
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
    return row


# ── Stats, blind pack, outputs ───────────────────────────────────────────────

def percentile(xs, p: float) -> float | None:
    """Linear-interpolated percentile (p in 0..100); None for no data."""
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarize(rows: list[Row]) -> dict:
    out = {}
    for name in dict.fromkeys(r.provider for r in rows):
        mine = [r for r in rows if r.provider == name]
        ok = [r for r in mine if not r.error]
        ttfb = [r.ttfb_ms for r in ok]
        total = [r.total_ms for r in ok]
        out[name] = {
            "n": len(mine), "errors": len(mine) - len(ok),
            "ttfb_p50": percentile(ttfb, 50), "ttfb_p90": percentile(ttfb, 90),
            "total_p50": percentile(total, 50), "total_p90": percentile(total, 90),
            "audio_s": statistics.mean(r.audio_s for r in ok) if ok else None,
        }
    return out


def _ms(x) -> str:
    return "-" if x is None else f"{x:.0f}"


def print_summary(stats: dict) -> None:
    print(f"\n{'provider':10} {'n':>4} {'err':>4} {'ttfb p50':>9} {'ttfb p90':>9} "
          f"{'total p50':>10} {'total p90':>10} {'avg audio':>10}")
    for name, s in stats.items():
        audio = "-" if s["audio_s"] is None else f"{s['audio_s']:.1f}s"
        print(f"{name:10} {s['n']:>4} {s['errors']:>4} {_ms(s['ttfb_p50']):>9} {_ms(s['ttfb_p90']):>9} "
              f"{_ms(s['total_p50']):>10} {_ms(s['total_p90']):>10} {audio:>10}")
    print("(ms; warm-up excluded; errors excluded from percentiles)")


def blind_assignment(n_lines: int, providers: list[str], seed: int) -> dict:
    """{"01": {"A": provider, "B": provider, ...}} shuffled per line, reproducible."""
    rng = random.Random(seed)
    key = {}
    for i in range(1, n_lines + 1):
        order = list(providers)
        rng.shuffle(order)
        key[f"{i:02d}"] = {chr(ord("A") + j): name for j, name in enumerate(order)}
    return key


def write_listening_pack(out: Path, corpus: list[str], first_run: list[Row],
                         providers: list[str], seed: int) -> dict:
    listen, raw = out / "listen", out / "raw"
    listen.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    audio = {(r.idx, r.provider): r.audio for r in first_run if r.audio}
    assignment = blind_assignment(len(corpus), providers, seed)
    key = {"seed": seed, "lines": {}}
    for nn, letters in assignment.items():
        idx = int(nn)
        missing = []
        for letter, name in letters.items():
            clip = audio.get((idx, name))
            if clip is None:
                missing.append(letter)
                continue
            write_wav(listen / f"{nn}_{letter}.wav", clip)
            (raw / f"{nn}_{name}.ulaw").write_bytes(clip)
        key["lines"][nn] = {"text": corpus[idx - 1], **letters}
        if missing:
            key["lines"][nn]["missing"] = missing
    (listen / "lines.txt").write_text(
        "".join(f"{i:02d}  {t}\n" for i, t in enumerate(corpus, 1)), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return key


CSV_FIELDS = ["provider", "idx", "run", "connect_ms", "ttfb_ms", "total_ms",
              "audio_s", "bytes", "error", "text"]


def write_csv(path: Path, rows: list[Row]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(getattr(r, k), 1) if isinstance(getattr(r, k), float)
                            else getattr(r, k)) for k in CSV_FIELDS})


# ── CLI ──────────────────────────────────────────────────────────────────────

def load_env() -> None:
    """os.environ first; backend/.env fills gaps if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(BACKEND / ".env", override=False)


def load_corpus(path: str | None) -> list[str]:
    if not path:
        return list(CORPUS)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def build_providers(args) -> list[Provider]:
    makers = {
        "cartesia": lambda k: Cartesia(k, args.cartesia_model, args.cartesia_voice),
        "flux": lambda k: Flux(k, args.flux_model, args.region),
        "aura2": lambda k: Aura2(k, args.aura_model, args.region),
    }
    envs = {"cartesia": "CARTESIA_API_KEY", "flux": "DEEPGRAM_API_KEY", "aura2": "DEEPGRAM_API_KEY"}
    out = []
    for name in [n.strip() for n in args.providers.split(",") if n.strip()]:
        if name not in makers:
            raise SystemExit(f"unknown provider {name!r}; choose from {', '.join(makers)}")
        key = os.environ.get(envs[name], "")
        if not key:
            print(f"skipping {name}: {envs[name]} is not set (environment or backend/.env)")
            continue
        out.append(makers[name](key))
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Blind A/B and latency: Cartesia vs Deepgram TTS")
    ap.add_argument("--providers", default="cartesia,flux", help="cartesia,flux,aura2")
    ap.add_argument("--runs", type=int, default=3, help="measured repetitions per line")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds per request")
    ap.add_argument("--seed", type=int, default=1234, help="blind-pack shuffle seed")
    ap.add_argument("--corpus", help="text file, one utterance per line ('#' comments)")
    ap.add_argument("--out", default="tts_ab_out", help="output directory")
    ap.add_argument("--cartesia-model", default="sonic-3")
    ap.add_argument("--cartesia-voice", default="a0e99841-438c-4a64-b679-ae501e7d6091")
    ap.add_argument("--flux-model", default="flux-sharon-en")
    ap.add_argument("--aura-model", default="aura-2-theia-en")
    ap.add_argument("--region", default="", help="Deepgram region, e.g. au -> api.au.deepgram.com")
    return ap.parse_args(argv)


async def main(argv=None):
    args = parse_args(argv)
    load_env()
    corpus = load_corpus(args.corpus)
    providers = build_providers(args)
    if not providers:
        raise SystemExit("no provider has a key; nothing to do")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for p in providers:
        w = await run_one(p, 0, 0, "Thanks for calling.", args.timeout)
        print(f"warm-up {p.name:9} {'ok' if not w.error else w.error}")
        await asyncio.sleep(args.delay)

    rows: list[Row] = []
    for run in range(1, args.runs + 1):
        for idx, text in enumerate(corpus, 1):
            for p in providers:
                row = await run_one(p, idx, run, text, args.timeout)
                rows.append(row)
                print(f"run {run} #{idx:02d} {p.name:9} ttfb {_ms(row.ttfb_ms):>5} ms  "
                      f"total {_ms(row.total_ms):>5} ms  audio {row.audio_s:4.1f}s  {row.error}")
                await asyncio.sleep(args.delay)

    write_csv(out / "results.csv", rows)
    write_listening_pack(out, corpus, [r for r in rows if r.run == 1],
                         [p.name for p in providers], args.seed)
    print_summary(summarize(rows))
    print(f"\nlistening pack: {out / 'listen'}   key: {out / 'key.json'}   "
          f"csv: {out / 'results.csv'}")


if __name__ == "__main__":
    asyncio.run(main())
