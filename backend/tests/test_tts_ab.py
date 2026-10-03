"""
tests/test_tts_ab.py
====================
scripts/tts_ab.py — the offline Cartesia vs Deepgram TTS A/B. No network: every
provider runs against a scripted fake WebSocket.
"""
import base64
import json
import wave

import pytest

from scripts import tts_ab


class FakeWS:
    """Scripted server. Each delivered message advances the fake clock by 1 s,
    so TTFB = position of the first audio frame, in seconds after the send."""

    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []
        self.t = 0.0
        self.closed = False

    def clock(self):
        return self.t

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for m in self.incoming:
            self.t += 1
            yield m


def _j(**kw):
    return json.dumps(kw)


# ── mu-law → WAV ─────────────────────────────────────────────────────────────

class TestUlaw:
    def test_known_values(self):
        # G.711: 0xFF / 0x7F are silence, 0x00 / 0x80 the extremes.
        assert tts_ab.ULAW_TABLE[0xFF] == 0
        assert tts_ab.ULAW_TABLE[0x7F] == 0
        assert tts_ab.ULAW_TABLE[0x00] == -32124
        assert tts_ab.ULAW_TABLE[0x80] == 32124
        assert tts_ab.ULAW_TABLE[0xF0] == 120
        pcm = tts_ab.ulaw_to_pcm16(bytes([0x00, 0xFF, 0x80]), use_audioop=False)
        assert pcm == (-32124).to_bytes(2, "little", signed=True) + b"\x00\x00" \
            + (32124).to_bytes(2, "little", signed=True)

    def test_table_matches_audioop(self):
        if tts_ab.audioop is None:
            pytest.skip("audioop removed in this Python")
        data = bytes(range(256))
        assert tts_ab.ulaw_to_pcm16(data, use_audioop=False) == tts_ab.audioop.ulaw2lin(data, 2)

    def test_pure_python_fallback(self, monkeypatch):
        monkeypatch.setattr(tts_ab, "audioop", None)
        assert tts_ab.ulaw_to_pcm16(bytes([0x80])) == (32124).to_bytes(2, "little", signed=True)

    def test_wav_header(self, tmp_path):
        path = tmp_path / "x.wav"
        tts_ab.write_wav(path, bytes([0xFF, 0x80] * 4000))
        with wave.open(str(path), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.getframerate() == 8000
            assert w.getnframes() == 8000
            frames = w.readframes(2)
        assert frames == b"\x00\x00" + (32124).to_bytes(2, "little", signed=True)


# ── Blind pack ───────────────────────────────────────────────────────────────

class TestBlindPack:
    def test_reproducible_with_seed(self):
        a = tts_ab.blind_assignment(30, ["cartesia", "flux"], seed=7)
        b = tts_ab.blind_assignment(30, ["cartesia", "flux"], seed=7)
        c = tts_ab.blind_assignment(30, ["cartesia", "flux"], seed=8)
        assert a == b
        assert a != c
        assert all(sorted(v.values()) == ["cartesia", "flux"] for v in a.values())
        # Actually shuffled: both providers land on A somewhere.
        assert {v["A"] for v in a.values()} == {"cartesia", "flux"}

    def test_key_maps_letters_to_the_right_audio(self, tmp_path):
        corpus = ["one", "two", "three"]
        rows = []
        for i in range(1, 4):
            rows.append(tts_ab.Row("cartesia", i, 1, corpus[i - 1], audio=bytes([0x80]) * 10))
            rows.append(tts_ab.Row("flux", i, 1, corpus[i - 1], audio=bytes([0x00]) * 10))
        key = tts_ab.write_listening_pack(tmp_path, corpus, rows, ["cartesia", "flux"], seed=3)
        on_disk = json.loads((tmp_path / "key.json").read_text())
        assert on_disk == key and key["seed"] == 3
        expect = {"cartesia": 32124, "flux": -32124}
        for nn, entry in key["lines"].items():
            assert entry["text"] == corpus[int(nn) - 1]
            for letter in ("A", "B"):
                with wave.open(str(tmp_path / "listen" / f"{nn}_{letter}.wav"), "rb") as w:
                    sample = int.from_bytes(w.readframes(1), "little", signed=True)
                assert sample == expect[entry[letter]]
            assert (tmp_path / "raw" / f"{nn}_cartesia.ulaw").read_bytes() == bytes([0x80]) * 10

    def test_missing_audio_is_recorded(self, tmp_path):
        rows = [tts_ab.Row("cartesia", 1, 1, "x", audio=b"\xff" * 8)]
        key = tts_ab.write_listening_pack(tmp_path, ["x"], rows, ["cartesia", "flux"], seed=1)
        entry = key["lines"]["01"]
        flux_letter = "A" if entry["A"] == "flux" else "B"
        assert entry["missing"] == [flux_letter]
        assert not (tmp_path / "listen" / f"01_{flux_letter}.wav").exists()


# ── Stats ────────────────────────────────────────────────────────────────────

class TestStats:
    def test_percentile(self):
        assert tts_ab.percentile([4, 1, 3, 2], 50) == 2.5
        assert tts_ab.percentile([1, 2, 3, 4], 90) == pytest.approx(3.7)
        assert tts_ab.percentile(list(range(1, 11)), 90) == pytest.approx(9.1)
        assert tts_ab.percentile([5], 90) == 5
        assert tts_ab.percentile([], 50) is None
        assert tts_ab.percentile([None, 3], 50) == 3

    def test_summarize_excludes_errors(self):
        rows = [tts_ab.Row("flux", i, 1, "t", ttfb_ms=float(i * 100), total_ms=float(i * 200),
                           audio_s=1.0) for i in range(1, 5)]
        rows.append(tts_ab.Row("flux", 5, 1, "t", error="timeout"))
        rows.append(tts_ab.Row("cartesia", 1, 1, "t", ttfb_ms=90.0, total_ms=300.0, audio_s=2.0))
        s = tts_ab.summarize(rows)
        assert s["flux"]["n"] == 5 and s["flux"]["errors"] == 1
        assert s["flux"]["ttfb_p50"] == 250
        assert s["flux"]["ttfb_p90"] == pytest.approx(370)
        assert s["cartesia"]["ttfb_p90"] == 90
        tts_ab.print_summary(s)  # renders without error


# ── Provider message flows ───────────────────────────────────────────────────

class TestCartesia:
    async def test_flow(self):
        p = tts_ab.Cartesia("k", model="sonic-3.6", voice="v1")
        ws = FakeWS([
            _j(type="timestamps", context_id="c"),
            _j(type="chunk", data=base64.b64encode(b"\xff" * 800).decode(), done=False),
            _j(type="chunk", data=base64.b64encode(b"\x80" * 800).decode(), done=False),
            _j(type="done", done=True),
            _j(type="chunk", data=base64.b64encode(b"\x00").decode()),  # never read
        ])
        r = await p.synthesize(ws, "Hello", clock=ws.clock)
        sent = ws.sent[0]
        assert sent["model_id"] == "sonic-3.6"
        assert sent["transcript"] == "Hello"
        assert sent["voice"] == {"mode": "id", "id": "v1"}
        assert sent["output_format"] == {"container": "raw", "encoding": "pcm_mulaw", "sample_rate": 8000}
        assert sent["continue"] is False and sent["context_id"]
        assert r.ttfb_ms == 2000 and r.total_ms == 4000
        assert r.audio == b"\xff" * 800 + b"\x80" * 800 and r.audio_s == 0.2

    def test_url_mirrors_production(self):
        p = tts_ab.Cartesia("KEY")
        assert p.url() == "wss://api.cartesia.ai/tts/websocket?api_key=KEY&cartesia_version=2024-06-10"
        assert p.model == "sonic-3" and p.voice == "a0e99841-438c-4a64-b679-ae501e7d6091"

    async def test_error_frame(self):
        ws = FakeWS([_j(type="error", status_code=400, message="unsupported encoding")])
        with pytest.raises(tts_ab.ProviderError, match="unsupported encoding"):
            await tts_ab.Cartesia("k").synthesize(ws, "x", clock=ws.clock)

    async def test_closed_before_done(self):
        ws = FakeWS([_j(type="chunk", data=base64.b64encode(b"\xff").decode())])
        with pytest.raises(tts_ab.ProviderError, match="before done"):
            await tts_ab.Cartesia("k").synthesize(ws, "x", clock=ws.clock)


class TestFlux:
    async def test_flow_reads_past_flushed(self):
        p = tts_ab.Flux("k", "flux-sharon-en")
        ws = FakeWS([
            _j(type="Connected", request_id="r"),
            _j(type="SpeechStarted", speech_id="dg_sp_000000000001"),
            b"\xff" * 400,
            _j(type="Flushed", speech_id="dg_sp_000000000001"),
            b"\x80" * 400,          # docs: remaining audio arrives after Flushed
            _j(type="SpeechMetadata", speech_id="dg_sp_000000000001", audio_duration_ms=100),
        ])
        r = await p.synthesize(ws, "G'day", clock=ws.clock)
        assert ws.sent[:2] == [{"type": "Speak", "text": "G'day"}, {"type": "Flush"}]
        assert ws.sent[-1] == {"type": "Close"}
        assert r.ttfb_ms == 3000 and r.total_ms == 6000
        assert len(r.audio) == 800

    def test_url_and_auth(self):
        p = tts_ab.Flux("KEY", "flux-sharon-en")
        assert p.url() == "wss://api.deepgram.com/v2/speak?model=flux-sharon-en&encoding=mulaw&sample_rate=8000"
        assert p.headers() == {"Authorization": "Token KEY"}
        assert tts_ab.Flux("k", "m", region="au").url().startswith("wss://api.au.deepgram.com/v2/speak?")

    async def test_error_frame(self):
        ws = FakeWS([_j(type="Connected"), _j(type="Error", code="INVALID_MODEL", description="no such model")])
        with pytest.raises(tts_ab.ProviderError, match="INVALID_MODEL no such model"):
            await tts_ab.Flux("k", "m").synthesize(ws, "x", clock=ws.clock)

    async def test_closed_before_metadata(self):
        ws = FakeWS([b"\xff", _j(type="Flushed", speech_id="s")])
        with pytest.raises(tts_ab.ProviderError, match="SpeechMetadata"):
            await tts_ab.Flux("k", "m").synthesize(ws, "x", clock=ws.clock)


class TestAura2:
    async def test_flow_stops_on_flushed(self):
        p = tts_ab.Aura2("k", "aura-2-theia-en")
        ws = FakeWS([
            _j(type="Metadata", request_id="r"),
            b"\xff" * 160,
            b"\xff" * 160,
            _j(type="Flushed", sequence_id=0),
            b"\x00" * 160,          # never read
        ])
        r = await p.synthesize(ws, "Hi", clock=ws.clock)
        assert ws.sent == [{"type": "Speak", "text": "Hi"}, {"type": "Flush"}, {"type": "Close"}]
        assert r.ttfb_ms == 2000 and r.total_ms == 4000 and len(r.audio) == 320
        assert p.url() == "wss://api.deepgram.com/v1/speak?model=aura-2-theia-en&encoding=mulaw&sample_rate=8000"


# ── run_one: connection handling and error surfacing ─────────────────────────

class TestRunOne:
    async def test_success_closes_socket(self, monkeypatch):
        ws = FakeWS([b"\xff" * 80, _j(type="Flushed", sequence_id=0)])
        seen = {}

        async def fake_connect(url, headers):
            seen.update(url=url, headers=headers)
            return ws

        monkeypatch.setattr(tts_ab, "_ws_connect", fake_connect)
        row = await tts_ab.run_one(tts_ab.Aura2("KEY", "aura-2-theia-en"), 1, 1, "Hi", timeout=5)
        assert row.error == "" and row.bytes == 80 and row.audio_s == 0.01
        assert row.connect_ms is not None and row.ttfb_ms is not None
        assert seen["headers"] == {"Authorization": "Token KEY"}
        assert ws.closed

    async def test_error_surfaces_redacted(self, monkeypatch):
        async def boom(url, headers):
            raise OSError(f"refused {url}")

        monkeypatch.setattr(tts_ab, "_ws_connect", boom)
        row = await tts_ab.run_one(tts_ab.Cartesia("SECRETKEY"), 1, 1, "Hi", timeout=5)
        assert row.error.startswith("OSError") and "SECRETKEY" not in row.error

    async def test_error_frame_becomes_row_error(self, monkeypatch):
        ws = FakeWS([_j(type="Error", code="RATE_LIMIT", description="slow down")])

        async def fake_connect(url, headers):
            return ws

        monkeypatch.setattr(tts_ab, "_ws_connect", fake_connect)
        row = await tts_ab.run_one(tts_ab.Flux("k", "m"), 1, 1, "Hi", timeout=5)
        assert "RATE_LIMIT" in row.error and row.ttfb_ms is None and ws.closed


# ── CLI plumbing ─────────────────────────────────────────────────────────────

class TestCli:
    def test_missing_key_skips_provider(self, monkeypatch, capsys):
        monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg")
        args = tts_ab.parse_args(["--providers", "cartesia,flux,aura2", "--region", "au"])
        provs = tts_ab.build_providers(args)
        assert [p.name for p in provs] == ["flux", "aura2"]
        assert "skipping cartesia" in capsys.readouterr().out
        assert provs[0].host == "api.au.deepgram.com"

    def test_corpus(self, tmp_path):
        assert 25 <= len(tts_ab.CORPUS) <= 35
        f = tmp_path / "c.txt"
        f.write_text("# comment\nFirst line.\n\n  Second line.  \n")
        assert tts_ab.load_corpus(str(f)) == ["First line.", "Second line."]
        assert tts_ab.load_corpus(None) == tts_ab.CORPUS

    def test_csv(self, tmp_path):
        rows = [tts_ab.Row("flux", 1, 1, "Hi, there", ttfb_ms=123.456, audio=b"x")]
        tts_ab.write_csv(tmp_path / "r.csv", rows)
        text = (tmp_path / "r.csv").read_text()
        assert text.splitlines()[0] == ",".join(tts_ab.CSV_FIELDS)
        assert "123.5" in text and '"Hi, there"' in text
