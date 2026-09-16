"""
tests/test_backchannel_barge_in.py — two faults heard on one real call.

**"Mhmm" stopped the agent dead.** Every string below is verbatim from the
call log of 3 September. Thirteen backchannels cut the agent off, including
"Go on. Go on." and "Okay. Continue." — the caller explicitly asking it to
keep talking — and not one produced a "backchannel ignored" line. Two reasons,
and they compounded:

  the cut was triggered by acoustic energy on the FIRST voiced frame, before
  a single word existed to judge, and

  the cut flipped the state to AWAITING_INPUT, so when the words finally
  arrived route_transcript no longer believed the agent was speaking and
  could not classify them as backchannels at all.

**A long answer could not be interrupted at all.** Cartesia streams faster
than real time, so a long reply is fully handed to Twilio seconds before the
caller has heard it. The state flipped to AWAITING_INPUT at send-time, and
barge-in is gated on AGENT_SPEAKING — so for the rest of the playback the
caller could talk and nothing was listening.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.voice_agent.cascaded_orchestrator import (
    BARGE_IN_COMMIT_FRAMES, CascadedPipelineOrchestrator,
)
from services.voice_agent.vad import ConversationState, is_backchannel_word

# Verbatim from the call. Each of these cut the agent off.
HEARD_ON_THE_CALL = [
    "Mhmm.", "Yeah.", "Right.", "Okay. Mhmm.", "Go on. Go on.",
    "Okay. Continue.", "Go.",
]
# These must always take the floor.
REAL_INTERRUPTIONS = [
    "Stop.", "Wait, no.", "Actually, cancel that.",
    "What about the pets?", "Sorry. Remind me what dates am I booked in for?",
    "And reference number again, please?",
]


@pytest.fixture
def speaking():
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.cartesia = MagicMock()
    agent.cartesia.cancel_stream = AsyncMock()
    agent.state = ConversationState.AGENT_SPEAKING
    agent._agent_audio_started = True
    agent.is_running = True
    return agent


class TestTheWords:
    @pytest.mark.parametrize("said", HEARD_ON_THE_CALL)
    def test_a_continuer_is_a_backchannel(self, said):
        assert is_backchannel_word(said), said

    @pytest.mark.parametrize("said", REAL_INTERRUPTIONS)
    def test_a_real_interruption_is_not(self, said):
        assert not is_backchannel_word(said), said


class TestABackchannelLeavesTheAgentTalking:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("said", HEARD_ON_THE_CALL)
    async def test_it_does_not_cut_and_does_not_reach_the_model(self, speaking, said):
        speaking.trigger_barge_in = AsyncMock()

        await speaking.handle_user_turn_complete(said)

        speaking.trigger_barge_in.assert_not_awaited()
        assert speaking.state == ConversationState.AGENT_SPEAKING
        assert speaking.history == []            # the model never hears "mhmm"
        assert speaking._backchannels_held == 1

    @pytest.mark.asyncio
    async def test_the_same_words_ARE_forwarded_once_the_agent_has_finished(self, speaking):
        """Suppression is about the floor, not the words. When the agent is not
        speaking, "yeah" is an answer and must reach the model."""
        speaking.state = ConversationState.AWAITING_INPUT
        speaking._ensure_call_context = AsyncMock()

        await speaking.handle_user_turn_complete("Yeah.")

        # The turn goes on to run the model, so the user message is in the
        # history rather than at the end of it. Present is the whole claim.
        assert {"role": "user", "content": "Yeah."} in speaking.history


class TestAShortRealInterruptionStillCuts:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("said", ["Stop.", "Wait, no.", "Actually, cancel that."])
    async def test_the_words_commit_it_when_the_speech_was_too_short(self, speaking, said):
        """"Stop." never lasts half a second, so the acoustic path will not
        commit it. The transcript has to."""
        speaking.trigger_barge_in = AsyncMock()
        speaking._ensure_call_context = AsyncMock()

        await speaking.handle_user_turn_complete(said)

        speaking.trigger_barge_in.assert_awaited_once_with(reason="semantic_interrupt")


class TestSustainedSpeechCutsWithoutWaitingForWords:
    @pytest.mark.asyncio
    async def test_half_a_second_of_speech_is_a_bid_for_the_floor(self, speaking):
        frame = b"\x00\x01\x02\x03" * 40
        with patch.object(speaking.deepgram, "send_audio", AsyncMock()), \
             patch.object(speaking.vad, "process_mulaw", return_value=True), \
             patch.object(speaking.vad, "is_immune", return_value=False), \
             patch.object(speaking, "trigger_barge_in", AsyncMock()) as cut:
            for _ in range(BARGE_IN_COMMIT_FRAMES):
                await speaking.handle_twilio_audio(frame)
        cut.assert_awaited_once_with(reason="sustained_speech")


class TestTheDrainWaitsOnAudioNotOnMarks:
    """
    Reported from a real call on v424: "once the audio crosses near 3-4s,
    interruption becomes dead". It did.

    The drain stood down when mark_tracker.confirmed_index reached
    _total_words_sent. The word index feeding those marks advanced by a flat 3
    words per audio chunk — 900 words a minute at 200ms chunks, against a real
    rate near 150. So it hit its ceiling after about a SIXTH of the audio,
    every later mark carried that same maximum index, and the first one echoed
    back made playback look finished. A sixth of a twenty-second answer is
    three seconds.

    Bytes of mu-law at 8kHz are an exact duration. The wait needs no estimate.
    """

    @pytest.mark.asyncio
    async def test_marks_reaching_their_ceiling_early_does_not_end_the_wait(self, speaking):
        import time as _t
        speaking._total_words_sent = 40
        speaking._audio_bytes_sent = 8000            # exactly 1s of audio
        speaking._playback_started_at = _t.time()
        # Exactly the broken condition: every mark already confirmed at max.
        speaking.mark_tracker.confirmed_index = 40

        t0 = _t.time()
        await speaking._await_playback(interrupted=False, turn_id=speaking._turn_id)
        waited = _t.time() - t0

        assert waited > 0.5, (
            f"stood down after {waited:.2f}s with a second of audio still playing — "
            "barge-in is disarmed for the rest of it"
        )

    @pytest.mark.asyncio
    async def test_it_stands_down_once_the_audio_has_actually_finished(self, speaking):
        import time as _t
        speaking._audio_bytes_sent = 800             # 0.1s of audio
        speaking._playback_started_at = _t.time() - 30   # long since played out
        speaking.mark_tracker.confirmed_index = 0        # marks never came back

        await asyncio.wait_for(
            speaking._await_playback(interrupted=False, turn_id=speaking._turn_id),
            timeout=1.0)


class TestTheWordIndexTracksRealSpeech:
    """That index is what barge-in prunes history against, so an overcount
    makes the agent believe the caller heard words it never played."""

    def test_the_rate_is_within_reach_of_human_speech(self):
        from services.voice_agent.cascaded_orchestrator import (
            MULAW_BYTES_PER_SECOND, SPOKEN_WORDS_PER_SECOND,
        )
        wpm = SPOKEN_WORDS_PER_SECOND * 60
        assert 120 <= wpm <= 200, f"{wpm:.0f} wpm is not a speaking rate"
        # The old behaviour, for the record: 3 words per 200ms chunk.
        old_wpm = 3 / (1600 / MULAW_BYTES_PER_SECOND) * 60
        assert old_wpm > 800        # 900 wpm


class TestAFinishedTurnCannotClobberANewerOne:
    """A turn that waits for its audio can be overtaken. Its teardown then set
    AWAITING_INPUT on a turn that was still speaking, cutting the new reply off
    mid-sentence."""

    @pytest.mark.asyncio
    async def test_the_wait_ends_when_a_newer_turn_starts(self, speaking):
        import time as _t
        speaking._audio_bytes_sent = 80000           # 10s of audio
        speaking._playback_started_at = _t.time()
        # Real turns are numbered from 1; 0 means "no turn", which switches the
        # guard off deliberately.
        speaking._turn_id = 1
        mine = speaking._turn_id

        async def next_turn_starts():
            await asyncio.sleep(0.1)
            speaking._turn_id += 1

        asyncio.create_task(next_turn_starts())
        await asyncio.wait_for(
            speaking._await_playback(interrupted=False, turn_id=mine), timeout=2.0)


class TestALongAnswerStaysInterruptible:
    """The caller is still hearing the agent long after we have finished
    sending. Standing down at send-time disarmed barge-in for the whole of the
    rest of the playback."""

    @pytest.mark.asyncio
    async def test_it_keeps_listening_until_twilio_confirms_playback(self, speaking):
        speaking._total_words_sent = 40
        speaking._audio_bytes_sent = 8000          # one second of mu-law
        speaking._playback_started_at = asyncio.get_event_loop().time() * 0  # far past
        import time as _t
        speaking._playback_started_at = _t.time()
        speaking.mark_tracker.confirmed_index = 10  # only a quarter played

        async def finish_playing():
            await asyncio.sleep(0.15)
            speaking.mark_tracker.confirmed_index = 40

        asyncio.create_task(finish_playing())
        await speaking._await_playback(interrupted=False)

        assert speaking.mark_tracker.confirmed_index == 40

    @pytest.mark.asyncio
    async def test_a_dropped_mark_cannot_leave_the_agent_deaf_forever(self, speaking):
        """The wait is bounded by the audio's own duration. A mark that never
        comes back must not strand the call in a state where it never listens
        again."""
        import time as _t
        speaking._total_words_sent = 40
        speaking._audio_bytes_sent = 800           # 0.1s of audio
        speaking._playback_started_at = _t.time() - 10   # long finished
        speaking.mark_tracker.confirmed_index = 0        # marks never arrived

        await asyncio.wait_for(speaking._await_playback(interrupted=False), timeout=2.0)

    @pytest.mark.asyncio
    async def test_an_interrupted_turn_does_not_wait_at_all(self, speaking):
        speaking._total_words_sent = 40
        speaking.mark_tracker.confirmed_index = 0
        await asyncio.wait_for(speaking._await_playback(interrupted=True), timeout=1.0)
