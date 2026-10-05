"""
Things that go wrong around a call rather than in it.

- A restart (Heroku's daily cycle, a deploy, SIGKILL 30 s after SIGTERM) used
  to lose every live call's transcript, because the record is only written at
  hang-up. The shutdown hook now saves what is live, once, within a bound.
- A Media Stream socket that connected and never sent `start` held Deepgram
  and Cartesia open indefinitely — start() opens both before Twilio's first
  message. It is now closed after STREAM_START_TIMEOUT_S.
- The voice rate limits were constants; they are settings now, defaults kept.
"""

import asyncio
import json
import time
import weakref
from unittest.mock import AsyncMock, patch

import pytest

import services.voice_agent.cascaded_orchestrator as orch_mod
from core.config import settings
from services.voice_agent.cascaded_orchestrator import (
    CascadedPipelineOrchestrator,
    save_live_transcripts,
)


@pytest.fixture
def live_calls(monkeypatch):
    """A clean registry, so calls left by other tests never leak in."""
    registry = weakref.WeakSet()
    monkeypatch.setattr(orch_mod, "_LIVE_CALLS", registry)
    return registry


def _call(sid: str) -> CascadedPipelineOrchestrator:
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZ" + sid)
    agent.warm_llm_on_start = False
    agent.call_sid = sid
    agent.history = [
        {"role": "user", "content": "do you have a room on Friday?"},
        {"role": "assistant", "content": "Let me check that for you."},
    ]
    return agent


# --- shutdown saves what is live --------------------------------------------

async def test_shutdown_saves_every_live_call_once_marked_as_server_shutdown(live_calls):
    calls = [_call("CA1"), _call("CA2"), _call("CA3")]
    for call in calls:
        live_calls.add(call)

    saved = AsyncMock(return_value={"ok": True})
    with patch("services.appwrite.db_service.save_call_transcript", saved):
        assert await save_live_transcripts(timeout_s=5) == 3
        # The process may still get to tear the calls down normally after the
        # hook — that must not write a second record.
        for call in calls:
            await call._save_transcript()

    assert saved.await_count == 3
    assert sorted(c.kwargs["call_sid"] for c in saved.await_args_list) == ["CA1", "CA2", "CA3"]
    for c in saved.await_args_list:
        assert c.kwargs["metadata"]["ended_by"] == "server_shutdown"


async def test_shutdown_is_bounded_when_one_save_hangs(live_calls):
    """One stuck Appwrite write must not cost the other calls their records,
    nor hold shutdown past the platform's SIGKILL."""
    for sid in ("CAslow", "CAfast"):
        live_calls.add(_call(sid))
    written = []

    async def save(**kwargs):
        if kwargs["call_sid"] == "CAslow":
            await asyncio.Event().wait()     # never returns
        written.append(kwargs["call_sid"])

    with patch("services.appwrite.db_service.save_call_transcript", side_effect=save):
        began = time.monotonic()
        await save_live_transcripts(timeout_s=0.2)
        assert time.monotonic() - began < 2

    assert written == ["CAfast"]


async def test_a_normal_hang_up_saves_without_ended_by(live_calls):
    """The marker is only for calls the server cut off; a normal call's record
    is exactly what it always was."""
    call = _call("CA9")
    saved = AsyncMock(return_value={"ok": True})
    with patch("services.appwrite.db_service.save_call_transcript", saved):
        await call._save_transcript()
    assert "ended_by" not in saved.await_args.kwargs["metadata"]


async def test_a_call_that_hung_up_is_not_saved_again_on_shutdown(live_calls):
    call = _call("CA7")
    call.deepgram.close = AsyncMock()
    call.cartesia.close = AsyncMock()
    live_calls.add(call)

    saved = AsyncMock(return_value={"ok": True})
    with patch("services.appwrite.db_service.save_call_transcript", saved):
        await call.stop()
        assert call not in live_calls
        assert await save_live_transcripts(timeout_s=5) == 0
    saved.assert_awaited_once()


def test_the_app_shutdown_hook_runs_the_save():
    """Read from source rather than imported: importing main starts the New
    Relic agent inside the test process."""
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    hook = next(node for node in ast.walk(tree)
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "shutdown_event")
    assert any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "on_event"
               and d.args and d.args[0].value == "shutdown" for d in hook.decorator_list)
    calls = [node for node in ast.walk(hook) if isinstance(node, ast.Await)
             and isinstance(node.value, ast.Call)
             and getattr(node.value.func, "id", "") == "save_live_transcripts"]
    assert len(calls) == 1
    timeout = next(k.value.value for k in calls[0].value.keywords if k.arg == "timeout_s")
    assert timeout <= 10, "must leave room inside Heroku's 30 s SIGKILL window"


# --- a socket that never sends `start` --------------------------------------

async def _run(agent, script):
    """run_loop over a scripted socket: each item is a message to send, or a
    number of seconds to stall for. Bridges stubbed; the real stop() runs."""
    async def fake_iter_text():
        for item in script:
            if isinstance(item, (int, float)):
                await asyncio.sleep(item)
            else:
                yield json.dumps(item)

    agent.twilio_ws.iter_text = fake_iter_text
    greeting = AsyncMock()
    stop = AsyncMock(wraps=agent.stop)
    with patch.object(agent.deepgram, "connect", AsyncMock(return_value=True)), \
         patch.object(agent.cartesia, "connect", AsyncMock(return_value=True)), \
         patch.object(agent.deepgram, "close", AsyncMock()), \
         patch.object(agent.cartesia, "close", AsyncMock()), \
         patch.object(agent, "process_deepgram_events", AsyncMock()), \
         patch.object(agent, "trigger_initial_greeting", greeting), \
         patch.object(agent, "_ensure_call_context", AsyncMock()), \
         patch.object(agent, "handle_twilio_audio", AsyncMock()) as audio, \
         patch.object(agent, "stop", stop):
        await asyncio.wait_for(agent.run_loop(), timeout=5)
    return greeting, audio, stop


START = {"event": "start", "start": {"streamSid": "MZ1", "callSid": "CAx",
                                     "customParameters": {}}}
MEDIA = {"event": "media", "media": {"payload": "AAAA"}}


async def test_no_start_in_time_closes_the_socket_and_stops(monkeypatch, live_calls):
    monkeypatch.setattr(settings, "STREAM_START_TIMEOUT_S", 0.1)
    monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "report")
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZ0")
    agent.warm_llm_on_start = False

    # Twilio's `connected` arrives, then nothing: the deadline is for `start`,
    # not for the first message.
    greeting, audio, stop = await _run(agent, [{"event": "connected"}, 3600])

    agent.twilio_ws.close.assert_awaited()
    stop.assert_awaited()
    greeting.assert_not_called()
    assert agent.is_running is False
    assert agent not in live_calls


async def test_a_start_inside_the_deadline_leaves_the_call_unbounded(monkeypatch, live_calls):
    """Once `start` is in, reads wait as long as the call lasts: a caller who
    is silent past the start deadline is not cut off."""
    monkeypatch.setattr(settings, "STREAM_START_TIMEOUT_S", 0.1)
    monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "report")
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZ0")
    agent.warm_llm_on_start = False

    greeting, audio, stop = await _run(agent, [
        {"event": "connected"}, 0.03, START, 0.3, MEDIA, {"event": "stop"},
    ])

    agent.twilio_ws.close.assert_not_called()
    greeting.assert_called_once()
    audio.assert_awaited_once()
    stop.assert_awaited()
