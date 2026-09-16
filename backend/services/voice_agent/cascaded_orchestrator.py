"""
services/voice_agent/cascaded_orchestrator.py
===============================================
Phase 12.3 — Cascaded Pipeline Orchestrator.

Decoupled real-time voice orchestration pipeline that coordinates:
1. Local VAD (`VadProcessor`) — sub-40ms acoustic barge-in & echo immunity (Decision 1)
2. Standalone Deepgram Listen (`DeepgramStandaloneBridge`) — STT & Flux v2 semantic endpointing (Decision 2)
3. Standalone Cartesia TTS (`CartesiaStandaloneBridge`) — direct streaming mu-law audio synthesis
4. Interruption Manager (`MarkTracker`, `prune_conversation_history`) — accurate word-slicing & history trimming
5. LLM Engine — async response generation with tool/function execution
"""

import asyncio
import base64
import json
import logging
import time
import uuid
import inspect
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Callable, Coroutine, AsyncGenerator
import httpx
import sentry_sdk
from sentry_sdk.ai import set_conversation_id
from fastapi import WebSocket

from core.config import settings
# is_backchannel_word is applied through route_transcript, not here — the
# decision belongs with the state it depends on.
from services.voice_agent.vad import VadProcessor, ConversationState
from services.voice_agent.interruption import (
    MarkTracker,
    prune_conversation_history,
    route_transcript,
    cognitive_delay,
)
from services.voice_agent.bridges.deepgram_standalone import DeepgramStandaloneBridge
from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge
from services.voice_agent.text_utils import prepare_for_tts
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt, build_caller_context_note
from services.voice_agent.call_state import CallState, recent_transcript
from services.voice_agent.text_utils import booking_summary_confirmed, spelling_honoured
from services.voice_agent.grounding import unsourced_claims, business_facts
from services.voice_agent.text_utils import transfer_consent_given
from services.voice_agent.functions.coalcreek_definitions import get_coalcreek_functions

logger = logging.getLogger(__name__)

# How much continuous speech commits a barge-in without waiting for words.
# 20ms webrtcvad frames. LiveKit's acoustic interruption model needs a median
# of 216ms before it will commit; without a model, half a second is the
# conservative equivalent — long enough that "mhmm" and "yeah" fall short,
# short enough that a real interruption is not talked over. Anything below the
# threshold is decided by is_backchannel_word() once Flux returns the text.
BARGE_IN_COMMIT_FRAMES = 25          # 25 x 20ms = 500ms

# mu-law at 8kHz: one byte is one sample, 8000 samples a second. Turning bytes
# sent into seconds of speech is what lets the drain wait be bounded by the
# audio that actually exists rather than by a flat guess.
MULAW_BYTES_PER_SECOND = 8000.0

# Words per second of synthesised speech, used to place Twilio marks against
# audio actually played. The marks used to advance by a flat 3 words per audio
# chunk, which at 200ms chunks credits 900 words a minute against a real rate
# nearer 150 — a 6x overcount. `_current_turn_word_count` therefore hit its
# ceiling after about a sixth of the audio, every later mark carried the same
# maximum index, and the first of those echoed back made playback look
# finished. Calibration knob: measure a recording and adjust, do not guess it
# away. Cartesia at "normal" speed sits around 2.5.
SPOKEN_WORDS_PER_SECOND = 2.5

# Slack on top of the audio's own duration before giving up on Twilio's marks.
# The wait exists so a long reply stays interruptible while it plays; the cap
# exists so a dropped mark cannot leave the agent permanently deaf.
PLAYBACK_DRAIN_GRACE_S = 2.0


def split_buffer_into_phrases(text_buffer: str, is_final: bool) -> tuple[List[str], str]:
    """
    Split text_buffer into phrases based on punctuation or length (>= 6 words).
    Returns list of phrases and the remaining text_buffer.
    """
    phrases = []
    punctuation_marks = ['.', '?', '!', ',', ';', ':']
    
    while text_buffer:
        first_punc_idx = -1
        for char in punctuation_marks:
            idx = text_buffer.find(char)
            if idx != -1:
                if first_punc_idx == -1 or idx < first_punc_idx:
                    first_punc_idx = idx
        
        if first_punc_idx != -1:
            phrase = text_buffer[:first_punc_idx + 1]
            text_buffer = text_buffer[first_punc_idx + 1:]
            phrases.append(phrase)
            continue
            
        words = text_buffer.split()
        if len(words) >= 6:
            phrase_words = words[:6]
            phrase = " ".join(phrase_words)
            idx = text_buffer.find(phrase)
            if idx != -1:
                text_buffer = text_buffer[idx + len(phrase):]
            else:
                text_buffer = " ".join(words[6:])
            phrases.append(phrase)
            continue
            
        if is_final:
            phrase = text_buffer.strip()
            if phrase:
                phrases.append(phrase)
            text_buffer = ""
            break
        else:
            break
            
    return phrases, text_buffer


class CascadedPipelineOrchestrator:
    """
    Orchestrates the decoupled STT -> LLM -> TTS pipeline for real-time Twilio calls.
    """
    def __init__(
        self,
        twilio_ws: WebSocket,
        stream_sid: Optional[str] = None,
        llm_callback: Optional[Callable[[List[Dict[str, Any]]], Coroutine[Any, Any, str]]] = None,
    ):
        self.twilio_ws = twilio_ws
        self.stream_sid = stream_sid
        self.llm_callback = llm_callback or self._default_llm_callback

        # Populated from the Twilio `start` event's customParameters.
        self.user_phone: str = ""
        self.tenant_id: str = settings.TENANT_ID
        self.call_sid: str = ""

        # Built once per call by _ensure_call_context(); the lock stops the
        # start-event task and the first turn from building it twice.
        self._context_ready: bool = False
        self._context_lock: asyncio.Lock = asyncio.Lock()
        self.tenant_config: Dict[str, Any] = {}
        self.dispatcher = None
        self._openai = None

        # Core state & history
        self.state = ConversationState.AWAITING_INPUT
        self.history: List[Dict[str, Any]] = []
        # What the tools established, kept outside the model. `history` holds
        # only spoken words; every tool result is discarded at the end of its
        # own turn, so without this the agent forgets its own lookups.
        self.call_state = CallState()
        # Per-call scratch shared with the tool handlers. Availability answers
        # are memoised here for the length of one call.
        self._tool_context: Dict[str, Any] = {"availability_cache": {}}
        self.is_running = False
        self.current_context_id: Optional[str] = None
        # The turn currently being spoken. Named for what it is: this used to
        # be `_pending_llm_task` and doubled as the handle TurnResumed cancels,
        # so a TurnResumed could kill the reply the caller was listening to.
        self._turn_task: Optional[asyncio.Task] = None

        # Phase 12 modular components
        self.vad = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        self.mark_tracker = MarkTracker()
        self.deepgram = DeepgramStandaloneBridge(sample_rate=8000, model="flux-general-en")
        self.cartesia = CartesiaStandaloneBridge(model_id="sonic-3", sample_rate=8000)

        # Word tracking for current TTS turn
        self._current_turn_word_count = 0
        # What the agent has said SO FAR this turn. On self, not local to the
        # run loop, because a barge-in has to be able to write it into history —
        # the caller heard it, so the agent has to remember saying it.
        self._current_turn_parts: List[str] = []

        # How much audio this turn has handed to Twilio, and when the first of
        # it went. Together they say how long the caller will still be hearing
        # the agent after we have finished sending.
        self._audio_bytes_sent: int = 0
        self._playback_started_at: float = 0.0

        # Which agent turn is current. A turn that waits for its audio to
        # finish playing can be overtaken by the next one, and its teardown
        # would then set AWAITING_INPUT on a turn that is still speaking —
        # cutting the new reply off mid-sentence. Teardown only touches shared
        # state while it is still the current turn.
        self._turn_id: int = 0

        # The call's own record, written once at teardown. Nothing was saved
        # for a live call before this: save_call_transcript only ever fired on
        # the rate-limit-blocked path, so reviewing what happened meant pulling
        # the Twilio recording and running it through Whisper. These counters
        # are the things that turned out to matter when doing that by hand.
        self._call_started_at: float = time.time()
        self._transcript_saved: bool = False
        self._tools_called: List[str] = []
        self._refusals: List[str] = []
        self._unsourced: List[str] = []
        self._barge_ins: int = 0
        self._backchannels_held: int = 0

        # True once this turn's first audio chunk has reached Twilio. Barge-in
        # stays disarmed until then so LLM think-time can't be interrupted.
        self._agent_audio_started: bool = False

        # Consecutive 20ms frames of speech heard while the agent is talking.
        # Acoustic energy alone used to cut the agent off on the FIRST voiced
        # frame, which is why "mhmm" and "go on" stopped it dead: a continuer
        # and a bid for the floor look identical to a VAD. Now the frames have
        # to add up to real speech before anything is cancelled, and a short
        # utterance is decided on its WORDS when Flux delivers them.
        self._speech_frames: int = 0

        # Control-flow tool actions. The dispatcher signals call termination by
        # returning {"action": "hangup"}; it is executed after the farewell has
        # finished streaming, not at dispatch time.
        # A one-way action promised during a turn, and the turn that promised
        # it. Without the turn, whichever teardown ran first consumed it: a
        # transfer promised in turn 1 was dialled by turn 2's teardown after
        # turn 2 had answered something else, and a hangup promised in turn 1
        # dropped the line at the end of turn 2's answer — the caller asks a
        # follow-up, gets it answered, and the call ends.
        self._pending_hangup: bool = False
        self._pending_transfer: Optional[str] = None
        self._pending_turn: int = 0

        # The single Cartesia reader. One socket, one consumer — see
        # `_stop_audio_reader`.
        self._audio_reader: Optional[asyncio.Task] = None

        # Turns the caller has finished, waiting to be answered, and the one
        # worker that answers them. Reading the socket and running a turn are
        # separate jobs: the read loop only enqueues, so nothing the caller
        # says goes unread, and the worker keeps the invariant the rest of
        # this class is written for — exactly one turn live at a time.
        self._finished_turns: asyncio.Queue = asyncio.Queue()
        self._turn_worker_task: Optional[asyncio.Task] = None
        self._hangup_triggered: bool = False

        # Sentry transaction and span tracking
        self._sentry_transaction = None
        self._span_1 = None
        self._span_3 = None

    async def start(self) -> bool:
        """
        Connect standalone bridges and start processing loops.
        """
        dg_ok = await self.deepgram.connect()
        tts_ok = await self.cartesia.connect()

        if not dg_ok or not tts_ok:
            logger.error(f"🔴 [CascadedOrchestrator] Failed to connect bridges (DG: {dg_ok}, TTS: {tts_ok})")
            await self.stop()
            return False

        # Turn-taking thresholds are already set as query params on the connect
        # URL, so no runtime Configure round-trip is needed here.

        self.is_running = True
        logger.info("🟢 [CascadedOrchestrator] Pipeline started successfully")
        return True

    async def handle_twilio_audio(self, mulaw_payload: bytes) -> None:
        """
        Handle incoming raw mu-law audio frame from Twilio.
        """
        if not self.is_running or not mulaw_payload:
            return

        # Forward immediately to Deepgram (Decision 2 - semantic endpointing)
        await self.deepgram.send_audio(mulaw_payload)

        # Check local VAD (Decision 1 - acoustic barge-in)
        # Note: webrtcvad strictly requires 10ms, 20ms, or 30ms chunks (e.g. 160 bytes for 20ms at 8kHz mu-law)
        if len(mulaw_payload) == 160:
            try:
                is_speech = self.vad.process_mulaw(mulaw_payload)
                if (
                    self.state == ConversationState.AGENT_SPEAKING
                    and self._agent_audio_started
                    and not self.vad.is_immune()
                ):
                    if is_speech:
                        self._speech_frames += 1
                        # Sustained speech is a bid for the floor whatever the
                        # words turn out to be. Below the threshold nothing is
                        # cancelled — the decision waits for Flux.
                        if self._speech_frames == BARGE_IN_COMMIT_FRAMES:
                            await self.trigger_barge_in(reason="sustained_speech")
                    else:
                        self._speech_frames = 0
            except ValueError:
                pass

    async def handle_twilio_mark(self, mark_name: str) -> None:
        """
        Handle echoed milestone marks from Twilio (`mark_word_N`).
        """
        self.mark_tracker.confirm_mark(mark_name)
        logger.debug(f"📍 [CascadedOrchestrator] Confirmed Twilio mark: {mark_name}")

    async def trigger_barge_in(self, reason: str = "acoustic") -> None:
        """
        Instantly cut off agent speech when user interrupts.
        1. Cancel Cartesia TTS stream
        2. Clear Twilio playback buffer
        3. Prune un-heard words from conversation history using mark tracker
        """
        if self.state != ConversationState.AGENT_SPEAKING:
            return

        logger.info(f"🛑 [CascadedOrchestrator] Barge-in triggered ({reason}). Cutting audio!")
        self.state = ConversationState.AWAITING_INPUT
        self._barge_ins += 1

        # 1. Cancel ongoing Cartesia TTS generation
        if self.current_context_id:
            await self.cartesia.cancel_stream(self.current_context_id)

        # 2. Clear Twilio buffer so caller hears silence immediately
        if self.stream_sid:
            clear_event = {"event": "clear", "streamSid": self.stream_sid}
            try:
                await self.twilio_ws.send_text(json.dumps(clear_event))
            except Exception as e:
                logger.warning(f"🟡 [CascadedOrchestrator] Failed to send clear event to Twilio: {e}")

        # 3. Record what the caller actually heard of this turn.
        #
        # This used to prune without appending, and the message it pruned was
        # the PREVIOUS turn's — the current one is only appended by the run
        # loop after streaming finishes, and that append is skipped when the
        # turn was interrupted. So an interrupted reply vanished from the
        # agent's own memory while the caller had heard it, and the turn before
        # it was truncated to this turn's word count.
        #
        # Heard on a real call: "Check-in is from 2 p.m." answered three times
        # in ninety seconds, because each answer was cut off and then forgotten.
        spoken = " ".join(self._current_turn_parts).strip()
        self._current_turn_parts = []
        if spoken:
            self.history.append({"role": "assistant", "content": spoken})
        # Now prune targets the message it was always meant to: this one. A
        # confirmed index of zero drops it, which is right — nothing was heard.
        confirmed_idx = self.mark_tracker.confirmed_index
        self.history = prune_conversation_history(self.history, confirmed_word_index=confirmed_idx)
        self.mark_tracker.reset()

    async def trigger_initial_greeting(self) -> None:
        """
        Streams pre-recorded zero-latency greeting audio clip (`smart_greeting.mulaw.raw`)
        immediately upon call connect, falling back to Cartesia TTS if missing.
        """
        greeting = "Hello! Thanks for calling Coal Creek Accommodation. How can I help you today?"
        logger.info(f"🗣️ [CascadedOrchestrator] Triggering initial greeting: '{greeting}'")
        self.history.append({"role": "assistant", "content": greeting})
        self.state = ConversationState.AGENT_SPEAKING

        # Greeting audio starts immediately, so barge-in is armed from here
        # (gated by the 3s echo-immunity window below).
        self._agent_audio_started = True
        self.vad.arm_immunity(duration_s=3.0)

        # Check for pre-recorded cached audio clip to eliminate cold-start TTS latency
        audio_clip_path = Path(__file__).resolve().parent / "audio" / "f786b574-daa5-4673-aa0c-cbe3e8534c02" / "smart_greeting.mulaw.raw"
        if audio_clip_path.exists():
            try:
                raw_bytes = audio_clip_path.read_bytes()
                logger.info(f"⚡ [CascadedOrchestrator] Playing zero-latency cached smart_greeting ({len(raw_bytes)} bytes)")
                
                # Stream in 1600-byte (200ms) chunks to Twilio
                chunk_size = 1600
                for i in range(0, len(raw_bytes), chunk_size):
                    if not self.is_running or self.state != ConversationState.AGENT_SPEAKING:
                        break
                    chunk = raw_bytes[i:i + chunk_size]
                    payload_b64 = base64.b64encode(chunk).decode("utf-8")
                    media_event = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": payload_b64}
                    }
                    if self.twilio_ws:
                        await self.twilio_ws.send_text(json.dumps(media_event))
                    await asyncio.sleep(0.18)  # ~200ms pacing for 8kHz mu-law audio
                if self.state == ConversationState.AGENT_SPEAKING:
                    self.state = ConversationState.AWAITING_INPUT
                return
            except Exception as e:
                # Deliberately no `finally` standing the agent down here. There
                # was one, and because it ran on the failure path too — before
                # control fell through to the synthesis fallback below, whose
                # first check is `state != AGENT_SPEAKING` — a truncated or
                # unreadable clip opened the call in total silence. The exact
                # failure the fallback exists to prevent.
                logger.warning(f"🟡 [CascadedOrchestrator] Failed playing cached greeting audio clip: {e}")

        # Fallback: synthesise the greeting, for a call that would otherwise
        # open in silence if the cached clip is missing or unreadable.
        #
        # This block used to call `self.cartesia.stream_speech(...)`, which is
        # not a method on CartesiaStandaloneBridge and never has been, so the
        # `async for` raised AttributeError before a single byte existed and
        # the caller heard nothing at all.
        try:
            self.current_context_id = f"greeting_{int(time.time()*1000)}"
            self._audio_bytes_sent = 0
            self._playback_started_at = 0.0
            await self.cartesia.send_transcript_chunk(
                context_id=self.current_context_id,
                transcript=greeting,
                continue_stream=False,
            )

            greeting_context = self.current_context_id

            async def greeting_reader() -> None:
                first = True
                async for audio_evt in self.cartesia.receive_audio_events():
                    if not self.is_running or self.state != ConversationState.AGENT_SPEAKING:
                        return
                    evt_ctx = audio_evt.get("context_id")
                    if evt_ctx and evt_ctx != greeting_context:
                        continue
                    kind = audio_evt.get("type")
                    if kind == "chunk":
                        payload_b64 = audio_evt.get("data")
                        if not payload_b64:
                            continue
                        if first:
                            first = False
                            # Audible from here, so barge-in is armed from
                            # here — with the echo-immunity window the cached
                            # path uses. Standing down at send time instead
                            # left the greeting uninterruptible and still
                            # playing under the first answer.
                            self._agent_audio_started = True
                            self._playback_started_at = time.time()
                            self.vad.arm_immunity(duration_s=3.0)
                        if self.twilio_ws:
                            await self.twilio_ws.send_text(json.dumps({
                                "event": "media",
                                "streamSid": self.stream_sid,
                                "media": {"payload": payload_b64},
                            }))
                        self._audio_bytes_sent += (len(payload_b64) * 3) // 4
                    elif kind in ("done", "error"):
                        if kind == "error":
                            logger.error(
                                "🔴 [CascadedOrchestrator] Cartesia rejected the greeting: %s",
                                audio_evt,
                            )
                        return

            # Registered, so the first turn's `_stop_audio_reader()` can find
            # it. Left unregistered, a greeting the caller talked over stayed
            # parked in recv() on the one Cartesia socket, the first turn
            # opened a second reader, and the call was mute from its first
            # word.
            await self._stop_audio_reader()
            self._audio_reader = asyncio.create_task(greeting_reader())
            await self._audio_reader

            # Everything is handed to Twilio; the caller has not heard it yet.
            await self._await_playback(
                interrupted=self.state != ConversationState.AGENT_SPEAKING,
                turn_id=None,
            )
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Failed streaming initial greeting: {e}")
        finally:
            await self._stop_audio_reader()
            if self.state == ConversationState.AGENT_SPEAKING:
                self.state = ConversationState.AWAITING_INPUT

    async def process_deepgram_events(self) -> None:
        """
        Process conversational events from Deepgram Flux v2.
        """
        async for event in self.deepgram.receive_events():
            event_type = event.get("type")

            # Flux v2 always sets type="TurnInfo" and carries the turn state in
            # `event` (Update/StartOfTurn/EagerEndOfTurn/TurnResumed/EndOfTurn).
            # Legacy Listen v1 puts the state in `type`, so fall back to it.
            turn_state = event.get("event") or event_type

            # Extract transcript across Flux v2 (TurnInfo/transcript) and legacy formats
            transcript = ""
            if "transcript" in event and event["transcript"]:
                transcript = str(event["transcript"]).strip()
            elif "channel" in event:
                alternatives = event.get("channel", {}).get("alternatives", [])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "").strip()

            if event_type in ("Error", "FatalError", "ConfigureFailure"):
                logger.error(f"🔴 [CascadedOrchestrator] Deepgram rejected the stream: {event}")
                continue

            if event_type == "Connected":
                logger.info("🤝 [CascadedOrchestrator] Deepgram session confirmed Connected")
                continue

            if turn_state in ("StartOfTurn", "SpeechStarted", "UserStartedSpeaking"):
                # Deliberately does NOT cut. This event fires the moment Flux
                # hears voice, before there is a single word to judge, so
                # cutting here is the same mistake as cutting on a VAD frame:
                # "mhmm" and "stop" are indistinguishable until the text lands.
                # Sustained speech (handle_media) or the transcript itself
                # (handle_user_turn_complete) commits the interruption.
                logger.debug("👂 [CascadedOrchestrator] Caller started speaking")

            elif turn_state == "EagerEndOfTurn":
                logger.info("⚡ [CascadedOrchestrator] EagerEndOfTurn received. Pre-warming LLM...")

            elif turn_state == "TurnResumed":
                # The caller paused and carried on, so Flux withdraws the end
                # of turn it had proposed. There is nothing of ours to undo:
                # the EagerEndOfTurn branch above only logs, so no speculative
                # work was ever started.
                #
                # This branch used to cancel `_pending_llm_task`, which was
                # also the handle for the live turn — so it could cancel the
                # answer being spoken, losing all record of it from history
                # (the reply is appended only after its playback drains).
                #
                # Correction to the claim in commit 948a54d: that cancel was
                # NOT reachable before the turn stopped being awaited here.
                # This loop is the only reader of Deepgram events, and it was
                # blocked inside the turn, so a TurnResumed was not read until
                # the turn was already done and `.done()` made the cancel a
                # no-op. It is a hazard that fix created, not one it found —
                # and the repeated question on call 2 is explained by the
                # backlog, not by this.
                logger.info("🔄 [CascadedOrchestrator] TurnResumed — caller is still talking.")

            elif turn_state in ("EndOfTurn", "SpeechEnded", "Results"):
                # `Update` is interim — deliberately excluded so the LLM fires
                # once on turn end, not on every partial transcript.
                #
                # Handed to the worker rather than run here. Running it here
                # blocked this loop for the whole reply and the caller's next
                # question was not read until the answer finished playing;
                # running it here as a fire-and-forget task instead let two
                # turns share one orchestrator, which cost a silent socket, a
                # transfer dialled by the wrong turn, and an answer the caller
                # heard vanishing from history. A queue does both jobs.
                if transcript:
                    self._finished_turns.put_nowait(transcript)

    async def _turn_worker(self) -> None:
        """
        Answer finished turns, one at a time, newest first.

        Races the turn in progress against the next thing the caller says. If
        the caller speaks first, the floor changes: the turn is abandoned in
        order — barge-in records what was heard, the pipeline is cancelled and
        awaited — before the next one starts. So the socket is never blocked
        by a reply, and no two turns are ever live at once.
        """
        pending = await self._finished_turns.get()
        while self.is_running and pending is not None:
            turn = asyncio.create_task(self.handle_user_turn_complete(pending))
            nxt = asyncio.create_task(self._finished_turns.get())
            done, _ = await asyncio.wait(
                {turn, nxt}, return_when=asyncio.FIRST_COMPLETED
            )
            if nxt in done:
                # The caller has moved on. Stop waiting on this turn; the next
                # `handle_user_turn_complete` takes the floor from it properly.
                pending = nxt.result()
                turn.cancel()
            else:
                nxt.cancel()
                if turn.done() and not turn.cancelled() and turn.exception():
                    exc = turn.exception()
                    logger.error("🔴 [CascadedOrchestrator] Turn failed: %s", exc, exc_info=exc)
                    sentry_sdk.capture_exception(exc)
                pending = await self._finished_turns.get()

    async def _abandon_current_turn(self) -> None:
        """
        Take the floor from whatever holds it, and do not return until it has
        let go.

        Awaiting the cancellation is the point. Leaving an abandoned turn
        running is what put two readers on the Cartesia websocket, let one
        turn finish another's Sentry transaction, and let one turn's teardown
        dial a transfer another had promised.
        """
        task, self._turn_task = self._turn_task, None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # Only swallow the turn's cancellation, never our own: absorbing
            # ours made `stop()` fail to stop anything, and a call that had
            # already hung up went on to dial a transfer.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
        except Exception as exc:
            logger.error(
                "🔴 [CascadedOrchestrator] Abandoned turn failed: %s", exc, exc_info=exc
            )

    async def handle_user_turn_complete(self, transcript: str) -> None:
        """
        Handle finalized user utterance after Deepgram Flux verifies turn completion.
        """
        # Judged against the state the agent is ACTUALLY in. This check used to
        # be reached only after an acoustic barge-in had already flipped the
        # state to AWAITING_INPUT — so a backchannel was never recognised as
        # one, because by the time its words arrived the agent was no longer
        # "speaking". On a real call, thirteen "mhmm"/"yeah"/"go on" turns cut
        # the agent off and not one of them was logged as ignored.
        action = route_transcript(transcript, state=self.state)
        if action == "ignore":
            logger.info(
                "🔇 [CascadedOrchestrator] Backchannel — letting the agent finish: %r",
                transcript,
            )
            self._speech_frames = 0
            self._backchannels_held += 1
            return

        # A short but genuine interruption — "stop", "no, wait" — never reaches
        # the sustained-speech threshold. The words are what commit it.
        if action == "interrupt" and self.state == ConversationState.AGENT_SPEAKING:
            await self.trigger_barge_in(reason="semantic_interrupt")

        logger.info(f"🗣️ [CascadedOrchestrator] User finished turn: '{transcript}'")

        # Whatever was speaking has now been cut (above) and must let go before
        # this turn touches the state it was using.
        await self._abandon_current_turn()

        self.history.append({"role": "user", "content": transcript})
        self.state = ConversationState.AGENT_SPEAKING

        # Immunity is armed when the first audio chunk actually reaches Twilio,
        # not here — see audio_receiver().
        self._agent_audio_started = False
        self._speech_frames = 0
        self.mark_tracker.reset()
        self._current_turn_word_count = 0
        self.current_context_id = f"ctx_{uuid.uuid4().hex[:8]}"

        # The floor changes HERE, not inside the task below.
        #
        # This increment used to live at the top of the pipeline, which runs a
        # tick later — so between this method returning and the new task's
        # first step, the previous turn's `mine()` was still true while the
        # context id and the mark generation had already moved on. Every
        # per-turn guard had that window built into it.
        self._turn_id += 1
        my_turn = self._turn_id

        # Start Sentry transaction and Span 1
        self._sentry_transaction = sentry_sdk.start_transaction(name="user_voice_turn_transaction")
        self._span_1 = self._sentry_transaction.start_child(
            op="pipeline.span1",
            name="Span 1: User Speech Ended -> First Token Yielded"
        )
        self._span_3 = None

        # Awaited here, and that is safe now: this runs on `_turn_worker`,
        # not on the Deepgram read loop. Awaiting it on the read loop is what
        # left the caller unheard for the length of a reply —
        #
        #     05:48:28.412472  EagerEndOfTurn
        #     05:48:28.412677  TurnResumed
        #     05:48:28.412808  EagerEndOfTurn
        #     05:48:28.412928  User finished turn: 'do you allow pets?'
        #
        # four events inside 0.5ms, a backlog draining rather than speech.
        # Not awaiting it at all was worse: two turns then shared one
        # orchestrator, and every piece of per-turn state on `self` became a
        # race. The worker reads ahead and this awaits, so neither happens.
        self._turn_task = asyncio.create_task(
            self._run_parallel_streaming_pipeline(
                my_turn,
                context_id=self.current_context_id,
                transaction=self._sentry_transaction,
                span_1=self._span_1,
            )
        )
        await self._turn_task

    async def _run_parallel_streaming_pipeline(
        self,
        my_turn: int,
        context_id: str,
        transaction=None,
        span_1=None,
    ) -> None:
        """
        Coordinates parallel LLM token generation, phrase extraction,
        TTS synthesis, and Twilio audio streaming.

        Everything this turn owns arrives as an argument and stays in a local.
        Turns overlap in time now — an overtaken one is still winding down
        while its successor speaks — so anything read off `self` at use time
        belongs to whichever turn wrote it last, which is not necessarily this
        one. Three faults came from exactly that: the old turn synthesised its
        trailing phrase into the NEW turn's Cartesia context, the old turn's
        teardown finished the NEW turn's Sentry transaction (making every
        latency figure after an interruption fiction), and a transfer promised
        in one turn was dialled by another turn's teardown.

        `self.state` alone cannot say whose turn it is either: barge-in sets
        AWAITING_INPUT and `handle_user_turn_complete` sets AGENT_SPEAKING
        straight back for the new turn, so a loop watching only that flag
        wakes up, sees "speaking", and keeps working for a turn that is over.
        """
        start_time = time.time()
        llm_queue = asyncio.Queue()
        span_3 = None
        total_words_sent = 0

        def mine() -> bool:
            return (self.state == ConversationState.AGENT_SPEAKING
                    and self._turn_id == my_turn)

        # 1. Start LLM Producer Task
        async def llm_producer():
            try:
                res = self.llm_callback(self.history)
                first_token = True
                if hasattr(res, "__anext__") or inspect.isasyncgen(res):
                    async for token in res:
                        if first_token:
                            first_token = False
                            # Span 1 ends at the first token. What used to be
                            # "Span 2" was opened and closed on this same line,
                            # so it always measured 0.01ms — the real detail now
                            # lives in the llm.stream / tool.execute children.
                            nonlocal span_3
                            if span_1:
                                span_1.finish()
                            if transaction:
                                span_3 = transaction.start_child(
                                    op="pipeline.span3",
                                    name="Span 3: First Token Yielded -> Cartesia First Audio Chunk Ingestion"
                                )
                        if not mine():
                            break
                        await llm_queue.put(token)
                else:
                    text = await res
                    if first_token:
                        first_token = False
                        if span_1:
                            span_1.finish()
                        if transaction:
                            span_3 = transaction.start_child(
                                op="pipeline.span3",
                                name="Span 3: First Token Yielded -> Cartesia First Audio Chunk Ingestion"
                            )
                    if text:
                        await llm_queue.put(text)
            except Exception as e:
                logger.error(f"🔴 [CascadedOrchestrator] LLM producer error: {e}", exc_info=True)
                sentry_sdk.capture_exception(e)
            finally:
                await llm_queue.put(None)  # Sentinel to end stream

        producer_task = asyncio.create_task(llm_producer())

        # 2. Run Text Chunk Sender and Audio Playout concurrently
        #
        # The previous turn's reader is stopped BEFORE this turn's counters are
        # reset and its own reader starts, because Cartesia multiplexes every
        # context over ONE websocket and `websockets` refuses a second
        # concurrent read: "cannot call recv while another coroutine is already
        # running recv". That ConcurrencyError lands in receive_audio_events'
        # bare `except Exception`, which sets is_connected = False — after
        # which send_transcript_chunk returns at its first line, silently, for
        # the rest of the call. One interruption and the caller hears dead air
        # until they hang up. An overtaken reader is parked in recv() and
        # cannot notice it has been overtaken, because after a barge-in cancel
        # there is no next event to wake it.
        #
        # Cancelling a reader parked in recv() is safe: the socket stays OPEN
        # and the next reader receives everything (verified against a real
        # websockets 15.0.1 server, not a mock).
        await self._stop_audio_reader()

        self._current_turn_parts = []
        full_response_parts = self._current_turn_parts
        self._audio_bytes_sent = 0
        self._playback_started_at = 0.0

        async def audio_receiver():
            first_chunk_ingested = False
            # After a barge-in cancel the killed context still emits trailing
            # chunks and a `done`; without this filter that stale `done` breaks
            # the next turn's receiver and the caller hears silence.
            turn_context_id = context_id
            try:
                async for audio_evt in self.cartesia.receive_audio_events():
                    if not mine():
                        break  # barge-in, or a newer turn owns the line now

                    evt_context_id = audio_evt.get("context_id")
                    if evt_context_id and turn_context_id and evt_context_id != turn_context_id:
                        logger.debug(
                            f"⏭️ [CascadedOrchestrator] Ignoring stale Cartesia event "
                            f"for {evt_context_id} (current turn: {turn_context_id})"
                        )
                        continue

                    evt_type = audio_evt.get("type")
                    if evt_type == "chunk":
                        if not first_chunk_ingested:
                            first_chunk_ingested = True
                            # The agent only becomes *audible* here. Arm barge-in
                            # and echo immunity now — not when the user's turn
                            # ended, which is 2-3s of think-time earlier and left
                            # every reply cancellable before it was ever heard.
                            self._agent_audio_started = True
                            self._playback_started_at = time.time()
                            self.vad.arm_immunity(duration_s=0.5)
                            # End Span 3
                            if span_3:
                                span_3.finish()
                            if transaction:
                                total_latency_ms = (time.time() - start_time) * 1000.0
                                transaction.set_data("first_audio_latency_ms", total_latency_ms)
                                transaction.finish()

                        base64_data = audio_evt.get("data")
                        if base64_data and self.stream_sid:
                            media_payload = {
                                "event": "media",
                                "streamSid": self.stream_sid,
                                "media": {"payload": base64_data},
                            }
                            await self.twilio_ws.send_text(json.dumps(media_payload))
                            # base64 -> 3 bytes of audio per 4 characters.
                            self._audio_bytes_sent += (len(base64_data) * 3) // 4

                            # Where the caller's ear has reached, derived from
                            # the audio actually sent rather than from a flat
                            # per-chunk guess. This index is what barge-in
                            # prunes history against, so an overcount makes the
                            # agent believe the caller heard words it never
                            # played.
                            self._current_turn_word_count = min(
                                int((self._audio_bytes_sent / MULAW_BYTES_PER_SECOND)
                                    * SPOKEN_WORDS_PER_SECOND),
                                total_words_sent,
                            )
                            mark_name = self.mark_tracker.register_word(self._current_turn_word_count)
                            mark_payload = {
                                "event": "mark",
                                "streamSid": self.stream_sid,
                                "mark": {"name": mark_name},
                            }
                            await self.twilio_ws.send_text(json.dumps(mark_payload))
                    elif evt_type == "done":
                        break
                    elif evt_type == "error":
                        # voice_id / tts_model come straight from tenant DB with
                        # no validation. Without this branch a bad value gives
                        # 15s of dead air and a timeout log that names nothing.
                        logger.error(
                            f"🔴 [CascadedOrchestrator] Cartesia rejected synthesis: {audio_evt}"
                        )
                        sentry_sdk.capture_message(
                            f"Cartesia synthesis error: {audio_evt.get('error')}", level="error"
                        )
                        break
            except Exception as e:
                logger.error(f"🔴 [CascadedOrchestrator] Audio receiver error: {e}", exc_info=True)
                sentry_sdk.capture_exception(e)

        receiver_task = asyncio.create_task(audio_receiver())
        self._audio_reader = receiver_task

        text_buffer = ""
        is_first_phrase = True

        try:
            while True:
                if not mine():
                    break

                chunk = await llm_queue.get()
                is_final = (chunk is None)

                # Yield control to let the producer put the sentinel None if it's done
                await asyncio.sleep(0)

                is_queue_done = False
                if not is_final:
                    if llm_queue.qsize() > 0 and llm_queue._queue[0] is None:
                        is_queue_done = True

                is_last_chunk = is_final or is_queue_done

                if not is_final:
                    text_buffer += chunk

                phrases, text_buffer = split_buffer_into_phrases(text_buffer, is_last_chunk)

                for phrase in phrases:
                    if not mine():
                        break

                    full_response_parts.append(phrase.strip())

                    # Call text normalizer (Decision 4 - prepare_for_tts)
                    clean_phrase, _ = prepare_for_tts(phrase)
                    clean_phrase_stripped = clean_phrase.strip()

                    if not clean_phrase_stripped:
                        continue

                    # Local, not an attribute: an overtaken turn kept adding
                    # its words onto the successor's freshly-zeroed count,
                    # raising the new turn's mark ceiling above the real ear
                    # position. Nothing outside this pipeline reads it.
                    total_words_sent += len(clean_phrase_stripped.split())

                    # Apply cognitive delay if it is the first phrase
                    if is_first_phrase:
                        is_first_phrase = False
                        elapsed_s = time.time() - start_time
                        delay_ms = cognitive_delay(elapsed_s)
                        if delay_ms > 0:
                            await asyncio.sleep(delay_ms / 1000.0)

                    is_last_phrase = is_last_chunk and (not text_buffer) and (phrases.index(phrase) == len(phrases) - 1)

                    # This turn's context, captured before it could move. Read
                    # off `self` here, after the 120ms cognitive delay below
                    # and with no re-check, it synthesised the tail of the
                    # previous answer into the NEW turn's context — the caller
                    # heard the old reply stutter into the new one, and the
                    # context_id filter could not reject it because the id was
                    # genuinely current.
                    await self.cartesia.send_transcript_chunk(
                        context_id=context_id,
                        transcript=clean_phrase_stripped,
                        continue_stream=not is_last_phrase,
                    )

                if is_final:
                    break
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Phrase streaming error: {e}", exc_info=True)
        finally:
            # Cleanup any active Sentry spans
            # These awaits are bounded. If Cartesia never emits `done` (e.g.
            # after a cancelled context) an unbounded await here would block the
            # single Twilio/Deepgram run loop and mute the call permanently.
            for name, task in (("producer", producer_task), ("receiver", receiver_task)):
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"🟡 [CascadedOrchestrator] {name} task did not finish in 15s — "
                        "cancelling so the call stays alive"
                    )
                    task.cancel()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"🔴 [CascadedOrchestrator] {name} task failed: {e}", exc_info=True)

            # Swept only once the producer and the receiver have stopped, so
            # nothing can write to a finished span afterwards. Sweeping first
            # meant that on a short uninterrupted turn — where the text is
            # fully streamed before Cartesia's first audio arrives — the
            # transaction was finished at ~0ms and the receiver then wrote
            # first_audio_latency_ms onto it after the fact.
            for span in (span_1, span_3, transaction):
                if span is not None and getattr(span, 'timestamp', None) is None:
                    try:
                        span.finish()
                    except Exception:
                        pass

            # Everything has been HANDED to Twilio; the caller has not heard it
            # yet. Cartesia streams faster than real time, so a long reply is
            # fully sent seconds before it finishes playing — and flipping to
            # AWAITING_INPUT here disarmed barge-in for the whole of the rest
            # of the playback. That is why long answers could not be
            # interrupted: the caller talked, and nothing was listening.
            #
            # Twilio echoes a mark as each word is actually played, so wait for
            # the last one before standing down. Bounded, because a dropped
            # mark must not strand the call in a state where the agent will
            # never listen again.
            await self._await_playback(
                interrupted=self.state != ConversationState.AGENT_SPEAKING,
                turn_id=my_turn,
            )

            # Overtaken while waiting for playback: another turn is speaking
            # now and this one must not touch the state it is using.
            if self._turn_id != my_turn:
                return

            interrupted = self.state != ConversationState.AGENT_SPEAKING
            if not interrupted:
                full_text = " ".join(full_response_parts).strip()
                self._current_turn_parts = []
                if full_text:
                    self.history.append({"role": "assistant", "content": full_text})
                    # Did any price, date or reference in that come from
                    # nowhere? Logged, never blocked. Measured over ten replays
                    # — five clean, five at heavy speech noise, ~410 replies —
                    # the rate of invented booking references was zero, and the
                    # two flagged claims were both correct arithmetic the agent
                    # is meant to do (checkout = check-in + nights; total =
                    # rate x nights). Blocking on that would gag the agent for
                    # doing the sums while catching nothing. This is here to
                    # find out whether a real phone line says otherwise.
                    # NOTE: full_response_parts holds the MODEL's text. The
                    # spoken text is rewritten by prepare_for_tts, which turns
                    # "2026-09-19" into "2026-9th-19" — checking that end finds
                    # nothing, forever.
                    try:
                        for kind, claim in unsourced_claims(
                                full_text,
                                self.call_state.evidence
                                + [m.get("content", "") for m in self.history
                                   if m.get("role") == "user"]
                                + business_facts()):
                            self._unsourced.append(f"{kind}:{claim}")
                            logger.warning(
                                "🧾 [CascadedOrchestrator] unsourced %s spoken: %s "
                                "— traced to no tool result, nothing the caller "
                                "said, and nothing in the knowledge base",
                                kind, claim,
                            )
                    except Exception as exc:
                        logger.debug("🧾 grounding check skipped: %s", exc)
                self.state = ConversationState.AWAITING_INPUT

            # Farewell has finished streaming — now end the call. A caller who
            # spoke over the goodbye is still talking, so the hangup is dropped
            # rather than deferred.
            # Only the turn that made the promise may keep it. A promise from
            # an earlier turn is void here, and saying so out loud matters
            # more than the drop: the agent's own offer is still in the
            # history, so the model can make it again.
            if self._pending_turn and self._pending_turn != my_turn:
                if self._pending_hangup or self._pending_transfer:
                    logger.warning(
                        "🟡 [CascadedOrchestrator] promise from turn %s abandoned at "
                        "turn %s (hangup=%s transfer=%s) — the caller interrupted the "
                        "turn that made it",
                        self._pending_turn, my_turn,
                        self._pending_hangup, bool(self._pending_transfer),
                    )
                    sentry_sdk.capture_message(
                        "One-way action abandoned: promised in turn "
                        f"{self._pending_turn}, reached turn {my_turn}",
                        level="warning",
                    )
                self._pending_hangup = False
                self._pending_transfer = None
                self._pending_turn = 0

            if self._pending_hangup:
                self._pending_hangup = False
                self._pending_turn = 0
                if interrupted:
                    logger.info(
                        "🛑 [CascadedOrchestrator] Hangup aborted — user spoke during farewell"
                    )
                else:
                    await self._hangup_call()

            # A transfer is never aborted by barge-in WITHIN its own turn: the
            # caller asking again while the handoff line plays still wants the
            # human. Across turns it is abandoned above.
            if self._pending_transfer:
                transfer_to, self._pending_transfer = self._pending_transfer, None
                self._pending_turn = 0
                await self._transfer_call(transfer_to)

    async def _stop_audio_reader(self) -> None:
        """
        Leave exactly one consumer on the Cartesia websocket.

        Cartesia multiplexes every context over one connection, and
        `websockets` raises ConcurrencyError on a second concurrent read. That
        error is caught by `receive_audio_events`' bare `except Exception`,
        which sets `is_connected = False`, after which `send_transcript_chunk`
        returns at its first line for the rest of the call — silent dead air
        from the first interruption onwards. The bridge already carries a
        comment warning about that failure; this is a second door into it.

        An overtaken reader cannot stand down by itself: it is parked in
        `recv()`, and after a barge-in cancel its context produces no further
        event to wake it on.
        """
        reader, self._audio_reader = self._audio_reader, None
        if reader is None or reader.done():
            return
        reader.cancel()
        try:
            await reader
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise          # ours, not the reader's — see _abandon_current_turn
        except Exception:
            pass

    async def _hangup_call(self) -> None:
        """
        Terminate the live PSTN leg via the Twilio REST API.

        Closing our WebSocket does not end the call — only a status update to
        `completed` does. Idempotent: the model re-fires `hang_up_call` when a
        first attempt appears to do nothing.
        """
        if self._hangup_triggered:
            return
        self._hangup_triggered = True

        if not self.call_sid:
            logger.warning("🟡 [CascadedOrchestrator] Cannot hang up: no Call SID")
            return

        logger.info(f"📵 [CascadedOrchestrator] Hanging up call: {self.call_sid}")
        try:
            url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{settings.TWILIO_ACCOUNT_SID}/Calls/{self.call_sid}.json"
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    url,
                    data={"Status": "completed"},
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
                response.raise_for_status()
            logger.info("✅ [CascadedOrchestrator] Call terminated successfully")
            self.is_running = False
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Failed to hang up call: {e}")
            sentry_sdk.capture_exception(e)

    async def _transfer_call(self, transfer_to: str) -> None:
        """
        Hand the live call to a human by replacing its TwiML with a `<Dial>`.

        If nobody answers within TRANSFER_TIMEOUT, Twilio falls through to the
        redirect and the caller lands back on the AI rather than on dead air.
        """
        if not self.call_sid:
            logger.warning("🟡 [CascadedOrchestrator] Cannot transfer: no Call SID")
            return

        masked = f"{'*' * max(len(transfer_to) - 4, 0)}{transfer_to[-4:]}"
        logger.info(f"📞 [CascadedOrchestrator] Transferring call to {masked}")
        try:
            from twilio.twiml.voice_response import VoiceResponse, Dial

            twiml = VoiceResponse()
            dial = Dial(
                timeout=settings.TRANSFER_TIMEOUT,
                caller_id=settings.TWILIO_PHONE_NUMBER,
                action=f"{settings.BACKEND_URL}/twilio/transfer-status",
            )
            dial.number(transfer_to)
            twiml.append(dial)
            twiml.say("Our staff are currently unavailable. Let me see how else I can help you.")
            twiml.redirect(f"{settings.BACKEND_URL}/twilio/voice")

            url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{settings.TWILIO_ACCOUNT_SID}/Calls/{self.call_sid}.json"
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    url,
                    data={"Twiml": str(twiml)},
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
                response.raise_for_status()

            logger.info("✅ [CascadedOrchestrator] Transfer initiated")
            # Stop generating AI audio into a leg that now belongs to staff.
            self.is_running = False
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Transfer failed: {e}")
            sentry_sdk.capture_exception(e)

    async def _await_playback(self, interrupted: bool, turn_id: int = 0) -> None:
        """
        Stay AGENT_SPEAKING until Twilio says the caller has actually heard it.

        The agent is audible for as long as Twilio has buffered audio, which is
        far longer than it takes us to send it. Barge-in is gated on
        AGENT_SPEAKING, so standing down at send-time made every long reply
        uninterruptible — the caller spoke, the VAD saw it, and the state check
        threw it away.

        Returns as soon as the last word is confirmed, or on the timeout. The
        timeout matters more than the wait: a mark that never comes back must
        not leave the agent permanently deaf.
        """
        if interrupted or not self._audio_bytes_sent or not self._playback_started_at:
            return

        # Waits on the AUDIO, not on the marks. Gating this on
        # mark_tracker.confirmed_index reaching _total_words_sent looked right
        # and stood down after roughly a sixth of a long answer, because the
        # word estimate feeding those marks ran 6x fast and pinned itself to
        # the maximum early. The caller then talked into an agent that had
        # already stopped listening — reported as "interruption goes dead about
        # three or four seconds in", which is exactly a sixth of a twenty-second
        # reply.
        #
        # Bytes of mu-law at 8kHz are an exact duration, so this needs no
        # estimate at all. Marks keep their real job: saying WHERE in the text
        # to cut when a barge-in does land.
        finishes_at = (self._playback_started_at
                       + self._audio_bytes_sent / MULAW_BYTES_PER_SECOND
                       + PLAYBACK_DRAIN_GRACE_S)
        while time.time() < finishes_at:
            if self.state != ConversationState.AGENT_SPEAKING:
                return          # barge-in committed while we waited; that is the point
            if turn_id and self._turn_id != turn_id:
                return          # a newer turn is speaking; this audio is history
            await asyncio.sleep(0.05)

    def _note_refusal(self, tool: str):
        """Record a gate firing, for the call's own record. Returns None so it
        can sit inside the refusal message it belongs to without changing it."""
        self._refusals.append(tool)
        return None

    async def _save_transcript(self) -> None:
        """
        Write the call down before the process forgets it.

        Nothing was saved for a live call until this existed: save_call_transcript
        only ever fired on the rate-limit-blocked path, so working out what
        happened on a real call meant fetching the Twilio recording and running
        it through Whisper — for every call, every time. The four test calls on
        3 September were diagnosed that way, and half the findings came out of
        the metadata below rather than the words.

        Never raises. A failed write must not stop a call tearing down cleanly,
        and a transcript is worth exactly nothing if it can break the thing it
        is describing.
        """
        if self._transcript_saved or not self.history:
            return
        self._transcript_saved = True

        try:
            lines = []
            for message in self.history:
                text = (message.get("content") or "").strip()
                if not text:
                    continue
                lines.append(f"{'Caller' if message.get('role') == 'user' else 'Agent'}: {text}")
            if not lines:
                return

            state = self.call_state
            tools = OrderedDict()
            for name in self._tools_called:
                tools[name] = tools.get(name, 0) + 1

            from services.appwrite import db_service

            await db_service.save_call_transcript(
                tenant_id=self.tenant_id or "coalcreek",
                call_sid=self.call_sid or "",
                caller_phone=self.user_phone or "",
                transcript="\n".join(lines),
                duration=int(time.time() - self._call_started_at),
                booking_ref=state.booking_reference or "",
                status="completed",
                room_type=state.room_type or "",
                customer_name=state.guest_name or state.heard_name or "Not provided",
                metadata={
                    # The things that turned out to matter when reading these
                    # calls by hand. Barge-ins first: seventeen of them in one
                    # 186-second call was the signal that led to the bug where
                    # an interrupted reply was dropped from the agent's memory.
                    "barge_ins": self._barge_ins,
                    "backchannels_held": self._backchannels_held,
                    "turns": sum(1 for m in self.history if m.get("role") == "user"),
                    "tools": dict(tools),
                    "refusals": self._refusals,
                    "unsourced_claims": self._unsourced,
                    "identity_confirmed": state.identity_confirmed,
                    "identity_basis": state.identity_basis,
                    "promises": state.promises,
                    "availability_quoted": state.availability,
                    "heard_email": state.heard_email,
                    "heard_name": state.heard_name,
                },
            )
            logger.info(
                "📝 [CascadedOrchestrator] Transcript saved | %s | %d turns | "
                "%d barge-ins | tools=%s",
                self.call_sid, sum(1 for m in self.history if m.get("role") == "user"),
                self._barge_ins, dict(tools),
            )
        except Exception as exc:
            logger.error("📝 [CascadedOrchestrator] Transcript save failed: %s", exc, exc_info=True)

    async def stop(self) -> None:
        """
        Stop the orchestrator and close all active bridges.
        """
        self.is_running = False
        for task in (self._turn_worker_task, self._turn_task):
            if task and not task.done():
                task.cancel()
        await self._save_transcript()
        await self.deepgram.close()
        await self.cartesia.close()
        logger.info("🛑 [CascadedOrchestrator] Stopped completely")

    async def _apply_voice_settings(self) -> None:
        """
        Push Appwrite `Tenants.config.voice_settings` onto the live bridges.

        Cartesia sends voice/model in every synthesis payload, so updating the
        attributes is enough — no reconnect. Deepgram's turn thresholds are
        connect-URL params, so they are re-sent via a Flux `Configure` message.
        """
        vs = (self.tenant_config or {}).get("voice_settings", {})
        if not vs:
            logger.warning(
                f"🟡 [CascadedOrchestrator] No voice_settings for tenant={self.tenant_id}; "
                "using code defaults"
            )
            return

        if vs.get("voice_id"):
            self.cartesia.voice_id = vs["voice_id"]
        if vs.get("tts_model"):
            self.cartesia.model_id = vs["tts_model"]

        # The STT model is baked into Deepgram's connect URL, which is opened
        # before this config is available. It currently matches by coincidence;
        # surface the drift loudly rather than silently running the wrong model.
        db_stt_model = vs.get("model")
        if db_stt_model and db_stt_model != self.deepgram.model:
            logger.warning(
                f"🟡 [CascadedOrchestrator] voice_settings.model='{db_stt_model}' but the "
                f"Deepgram socket is already connected with '{self.deepgram.model}'. "
                "The DB value is NOT applied this call — restart is required to change STT model."
            )

        # `speed` may be a legacy string (slow/normal/fast) or a number.
        speed = vs.get("speed")
        if speed is not None:
            named = {"slow": 0.8, "normal": 1.0, "fast": 1.2}
            try:
                value = named[speed.strip().lower()] if isinstance(speed, str) else float(speed)
                self.cartesia.speed = min(max(value, 0.6), 1.5)  # Cartesia range
            except (KeyError, TypeError, ValueError):
                logger.warning(f"🟡 [CascadedOrchestrator] Unrecognised speed '{speed}', ignoring")
        if vs.get("volume") is not None:
            try:
                self.cartesia.volume = min(max(float(vs["volume"]), 0.5), 2.0)
            except (TypeError, ValueError):
                logger.warning(f"🟡 [CascadedOrchestrator] Unrecognised volume '{vs['volume']}', ignoring")

        try:
            eot = float(vs.get("eot_threshold", 0.6))
            eot_timeout = int(vs.get("eot_timeout_ms", 1000))
            eager = float(vs.get("eager_eot_threshold", 0.4))
            # Keep the bridge's own attributes in sync with what Deepgram was
            # told, so logs and reconnects don't report stale values.
            self.deepgram.eot_threshold = eot
            self.deepgram.eot_timeout_ms = eot_timeout
            self.deepgram.eager_eot_threshold = eager
            await self.deepgram.send_configure(
                eot_threshold=eot,
                eot_timeout_ms=eot_timeout,
                eager_eot_threshold=eager,
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"🟡 [CascadedOrchestrator] Bad turn-taking settings, keeping defaults: {e}")

        logger.info(
            f"🎚️ [CascadedOrchestrator] voice_settings applied | voice={self.cartesia.voice_id} "
            f"| tts={self.cartesia.model_id} | eot={vs.get('eot_threshold')} "
            f"| eot_timeout_ms={vs.get('eot_timeout_ms')}"
        )

    async def _ensure_call_context(self) -> None:
        """
        Lazily build per-call context: tenant voice_settings, the function
        dispatcher, and the OpenAI client. Runs once per call.
        """
        if self._context_ready:
            return
        async with self._context_lock:
            if self._context_ready:   # another task won the race
                return
            await self._build_call_context()

    async def _build_call_context(self) -> None:
        from services.appwrite import db_service
        from services.voice_agent.abuse_protection import AbuseProtection
        from services.voice_agent.memory import CallerMemoryBank
        from services.voice_agent.functions import CoalCreekFunctionDispatcher
        from openai import AsyncOpenAI

        self.tenant_config = await db_service.get_tenant_config(self.tenant_id) or {}

        # Reuse the singleton warmed at startup — building the ADK graph
        # per turn cost ~4s of dead air.
        adk_state = getattr(getattr(self.twilio_ws, "app", None), "state", None)
        adk_orchestrator = getattr(adk_state, "adk_orchestrator", None)

        self.dispatcher = CoalCreekFunctionDispatcher(
            db_service=db_service,
            user_phone=self.user_phone,
            save_reservation_fn=lambda data: db_service.save_motel_reservation(
                data, tenant_id=self.tenant_id
            ),
            abuse_protection=AbuseProtection(tenant_id=self.tenant_id),
            caller_memory_bank=CallerMemoryBank(),
            call_sid=self.call_sid,
            adk_orchestrator=adk_orchestrator,
        )
        # Fire the caller's booking lookup now so it overlaps the first model
        # round instead of landing inside the turn as a ~250ms tool call.
        self.dispatcher.prefetch_caller_reservation()
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        await self._apply_voice_settings()
        self._context_ready = True
        logger.info(
            f"🧩 [CascadedOrchestrator] Call context ready | tenant={self.tenant_id} "
            f"| adk_singleton={'yes' if adk_orchestrator else 'no'}"
        )

    async def _execute_tool(self, name: str, args: dict, history: list = None) -> dict:
        """
        Every tool the model asks for passes through here.

        Only one is gated today. Handing the caller to a person ends everything
        the agent can do for them, and on a live call the model dialled a human
        straight after the caller said "Actually, I am calling for Sarah" — which
        agrees to nothing. The prompt already said to dial only on an explicit
        yes; a one-way action should not depend on the model choosing to obey.
        """
        # The turn's own history, which is the same list as self.history on a
        # live call but not in a test that drives one turn directly.
        history = self.history if history is None else history
        if name == "transfer_to_staff" and not transfer_consent_given(history):
            logger.info("🚦 [CascadedOrchestrator] transfer_to_staff blocked — nobody agreed to it")
            return {
                "success": False,
                "transferred": False,
                "message": (
                    self._note_refusal("transfer_to_staff") or "You have not been asked to transfer this call. Ask the caller "
                    "whether they would like to be put through to reception, and "
                    "only call this again if they say yes."
                ),
            }
        # What the caller told us, kept before any gate runs: a refusal is not a
        # reason to forget the name they just spelled out. This is the only copy
        # for a caller with no record.
        self.call_state.heard(args)
        self._tools_called.append(name)

        # The date handlers resolve relative phrases from the caller's own
        # words — "next weekend", "in three days" — and that argument was only
        # ever set by the legacy handler. On this path it was always absent, so
        # every relative date was resolved by the model, unvalidated, and a
        # whole tested resolver never ran. Safe to thread now that an explicit
        # date the model DID resolve takes precedence over anything in the
        # utterance; before that ordering it would have let a passing "tomorrow"
        # move a booking that already had real dates.
        if name in ("check_availability", "create_booking_request") and history:
            latest = next((m.get("content") for m in reversed(history)
                           if m.get("role") == "user"), "")
            if latest:
                args = dict(args)
                args["_user_utterance"] = latest

        # create_booking_request holds a room, queues an email and raises a
        # Stripe checkout. Its own gate is `has_user_confirmed_summary`, an
        # argument the MODEL fills in — the gate asks the model whether the
        # model read the summary back. Measured over ten replays of two booking
        # scenarios: 4 of 7 attempts asserted YES with no price-and-date
        # summary in the transcript at all. In one, the agent had asked "that's
        # ada at example dot com, right?", the caller said "yes, that's all
        # correct" — agreeing to an email spelling — and that became a
        # confirmed booking summary. It is the transfer bug again, and it is
        # fixed the same way: read the transcript.
        if name == "create_booking_request" and not booking_summary_confirmed(history):
            logger.warning(
                "🔒 [CascadedOrchestrator] create_booking_request refused — no "
                "price-and-date summary in the transcript that the caller agreed to"
            )
            return {
                "success": False,
                "error": (
                    self._note_refusal("create_booking_request") or "You have not read the booking summary back to this caller. A "
                    "'yes' to some other question is not confirmation of a booking. "
                    "Say the name, the check-in and check-out dates, the room and "
                    "the nightly rate in one sentence, ask them to confirm, and call "
                    "this again only after they agree to THAT."
                ),
            }

        # A name the caller spelled out, letter by letter, beats the name the
        # model thought it heard. On a real call the recogniser transcribed
        # "s i o b h a n" perfectly and the booking was written as "Cyborn
        # O'Connor" anyway — three times, each confirmed by a caller who could
        # not hear the difference in a spoken read-back.
        if name in ("create_booking_request", "update_guest_info"):
            spelled = self.call_state.spelled_name
            if spelled and not spelling_honoured(spelled, args.get("guest_name", "")):
                self._note_refusal(name)
                logger.warning(
                    "🔒 [CascadedOrchestrator] %s refused — caller spelled %r, "
                    "this would have written %r", name, spelled, args.get("guest_name", ""),
                )
                return {
                    "success": False,
                    "error": (
                        f"The caller spelled their name out letter by letter as "
                        f"'{spelled}'. You passed '{args.get('guest_name', '')}'. Use "
                        f"the spelling exactly — they spelled it because they knew it "
                        f"would be misheard. Read '{spelled}' back to them one letter "
                        f"at a time to confirm, then call this again with that name."
                    ),
                }

        # update_guest_info patches the reservation it finds on the caller's
        # number and re-sends the payment link to whatever email it is given.
        # It is locked to the caller's own number, which stops it reaching a
        # stranger's booking — but a shared handset is exactly the case this
        # pipeline already knows about, and "the number matched" is not "the
        # guest is on the line". Nothing to patch means nothing to protect, so
        # the gate only closes when a reservation actually exists.
        if (name == "update_guest_info"
                and not self.call_state.identity_confirmed
                and self.dispatcher
                and await self.dispatcher.caller_reservation()):
            logger.warning(
                "🔒 [CascadedOrchestrator] update_guest_info refused — a reservation "
                "exists on this number and the caller has not been identified"
            )
            return {
                "success": False,
                "message": (
                    self._note_refusal("update_guest_info") or "You have not identified this caller yet, and there is a "
                    "reservation on this number that this would change. Ask who "
                    "is calling, call lookup_booking with the name they give, and "
                    "only then update their details."
                ),
            }
        # The per-call availability memo only ever worked on the legacy handler,
        # which passes this context; the cascaded path called execute() with two
        # arguments and `context` was None, so check_availability re-ran the
        # whole query every time the model asked — two or three times in a
        # single booking conversation, against an 18s timeout budget.
        result = await self.dispatcher.execute(name, args, self._tool_context)
        # Every tool goes through here, so this is the one place that sees what
        # the call has established. Recorded after the gate above, so a refused
        # tool records nothing.
        self.call_state.observe(name, args, result)
        return result

    async def _default_llm_callback(self, history: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
        """
        Default LLM response generation using ADKOrchestrator query_stream if available,
        or falling back cleanly when disconnected.
        """
        if not history:
            return
        latest_user_text = history[-1].get("content", "")
        if not latest_user_text:
            return
        # Anything in the caller's own sentence worth keeping — an address they
        # spelled out survives here whether or not the model passes it to a
        # tool, and whether or not the turn is still in the window later.
        self.call_state.hear_caller(
            latest_user_text,
            agent_asked=next((m.get("content", "") for m in reversed(history)
                              if m.get("role") == "assistant"), ""),
        )

        try:
            await self._ensure_call_context()
            voice_settings = (self.tenant_config or {}).get("voice_settings", {})
            model = voice_settings.get("llm_model") or "gpt-4.1-nano"

            now = datetime.now(ZoneInfo("Australia/Melbourne"))
            messages: List[Dict[str, Any]] = [{
                "role": "system",
                "content": get_coalcreek_prompt(
                    now.strftime("%Y-%m-%d"), now.strftime("%I:%M %p")
                ),
            }]
            # Who this number belongs to, looked up while the greeting played.
            # It goes in a message of its own AFTER the prompt: the prompt is
            # the cached prefix, and a per-call note in front of it would change
            # the first bytes on every call and throw that cache away.
            caller_note = build_caller_context_note(
                await self.dispatcher.caller_reservation() if self.dispatcher else []
            )
            if caller_note:
                messages.append({"role": "system", "content": caller_note})
            # Only the recent transcript goes in verbatim; what the older
            # turns *established* is in the call-state note, which is placed
            # immediately before the caller's latest words because that is
            # where the model actually attends to it. Fourteen turns back, it
            # did not.
            messages += recent_transcript(history)
            state_note = self.call_state.as_note()
            if state_note and len(messages) > 1:
                messages.insert(len(messages) - 1, {"role": "system", "content": state_note})
            tools = [
                {"type": "function", "function": fn}
                for fn in get_coalcreek_functions()
            ]

            # Bounded so a tool-calling loop can never stall the voice turn.
            for _round in range(3):
                # Time the model wait separately from tool execution. Span 1
                # is ~86% of a turn; without this split neither a human nor
                # the Gemini analyzer can say which half is responsible.
                llm_span = None
                if self._sentry_transaction:
                    llm_span = self._sentry_transaction.start_child(
                        op="llm.stream",
                        name=f"LLM round {_round + 1}: request -> first token ({model})",
                    )
                # A stream that errors or yields no content leaves this span
                # open otherwise — a leaked span in the code that exists to
                # repair leaked spans.
                try:
                    stream = await self._openai.chat.completions.create(
                        model=model, messages=messages, tools=tools, stream=True,
                    # Adds a final chunk carrying usage; its `choices` is empty,
                    # which the guard below already skips.
                        stream_options={"include_usage": True},
                    )
                except Exception:
                    if llm_span:
                        llm_span.finish()
                    raise
                pending: Dict[int, Dict[str, str]] = {}
                assistant_text = ""
                first_event = True

                async for event in stream:
                    usage = getattr(event, "usage", None)
                    if usage and self._sentry_transaction:
                        # Proves whether the prompt cache was warm. The first
                        # turn of a call is ~2x slower than later turns and
                        # this is the number that confirms or kills that theory.
                        details = getattr(usage, "prompt_tokens_details", None)
                        self._sentry_transaction.set_data(
                            "llm.cached_tokens", getattr(details, "cached_tokens", 0) or 0
                        )
                        self._sentry_transaction.set_data(
                            "llm.prompt_tokens", getattr(usage, "prompt_tokens", 0) or 0
                        )
                    if not event.choices:
                        continue
                    if first_event:
                        first_event = False
                        if llm_span:
                            llm_span.finish()
                            llm_span = None
                    delta = event.choices[0].delta
                    if delta.content:
                        assistant_text += delta.content
                        yield delta.content
                    for tc in (delta.tool_calls or []):
                        slot = pending.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["args"] += tc.function.arguments

                if llm_span:
                    llm_span.finish()   # round produced no content event
                    llm_span = None

                if not pending:
                    return

                messages.append({
                    "role": "assistant",
                    "content": assistant_text or None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                        for c in pending.values()
                    ],
                })
                for call in pending.values():
                    try:
                        args = json.loads(call["args"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    logger.info(f"🔧 [CascadedOrchestrator] Tool call: {call['name']}({list(args)})")
                    tool_span = None
                    if self._sentry_transaction:
                        # gen_ai.* naming is what puts these in Sentry's agent
                        # views and the Tool Errors widget; a custom op does not.
                        tool_span = self._sentry_transaction.start_child(
                            op="gen_ai.execute_tool",
                            name=f"execute_tool {call['name']}",
                        )
                        # `start_child()` takes no `attributes=` kwarg in this
                        # SDK — only the top-level start_span() does. The agent
                        # attributes go on via set_data.
                        tool_span.set_data("gen_ai.operation.name", "execute_tool")
                        tool_span.set_data("gen_ai.tool.name", call["name"])
                        tool_span.set_data(
                            "gen_ai.tool.call.arguments", json.dumps(args, default=str)[:1000]
                        )
                    try:
                        result = await self._execute_tool(call["name"], args, history)
                        if tool_span:
                            tool_span.set_data(
                                "gen_ai.tool.call.result", json.dumps(result, default=str)[:1000]
                            )
                    except Exception as tool_exc:
                        if tool_span:
                            tool_span.set_status("internal_error")
                            tool_span.set_data("error.type", type(tool_exc).__name__)
                        raise
                    finally:
                        if tool_span:
                            tool_span.finish()
                    # The dispatcher answers control-flow tools with an `action`
                    # field. Forwarding the dict to the LLM without reading it
                    # makes the model *narrate* the action instead of anyone
                    # performing it — hang_up_call spoke a goodbye and left the
                    # line open.
                    if isinstance(result, dict):
                        if result.get("action") == "hangup":
                            self._pending_hangup = True
                            self._pending_turn = self._turn_id
                        elif result.get("action") == "transfer" and result.get("transfer_to"):
                            self._pending_transfer = result["transfer_to"]
                            self._pending_turn = self._turn_id
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, default=str)[:4000],
                    })
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] LLM generation failed: {e}", exc_info=True)
            yield "I am checking those details right now. Just one moment please."

    async def run_loop(self) -> None:
        """
        Main WebSocket loop for Twilio connection when running in cascaded mode.
        Processes start, media, mark, and stop events while simultaneously
        running the Deepgram event receiver task.
        """
        if not await self.start():
            return

        dg_task = asyncio.create_task(self.process_deepgram_events())
        self._turn_worker_task = asyncio.create_task(self._turn_worker())
        try:
            async for message in self.twilio_ws.iter_text():
                if not self.is_running:
                    break
                try:
                    data = json.loads(message)
                    event_type = data.get("event")
                    if event_type == "start":
                        self.stream_sid = data["start"].get("streamSid", self.stream_sid)
                        # Twilio <Parameter> values: user_phone (privacy-bound
                        # lookups), tenant_id (voice_settings), user_to.
                        params = data["start"].get("customParameters", {}) or {}
                        self.user_phone = params.get("user_phone", "") or ""
                        self.tenant_id = params.get("tenant_id", settings.TENANT_ID)
                        self.call_sid = data["start"].get("callSid", "") or self.call_sid
                        logger.info(
                            f"🚀 [CascadedOrchestrator] Twilio stream started: {self.stream_sid} "
                            f"| tenant={self.tenant_id} | caller={self.user_phone[:6]}***"
                        )
                        # A call IS a conversation, and Twilio already gives it a
                        # stable unique id. Without this every turn arrives in
                        # Sentry as an unrelated LLM call instead of one grouped
                        # multi-turn exchange.
                        if self.call_sid:
                            set_conversation_id(self.call_sid)
                        if self.user_phone:
                            sentry_sdk.set_user({"id": f"{self.user_phone[:5]}***{self.user_phone[-2:]}"})
                        # Load tenant config now, concurrently with the greeting,
                        # so voice_settings are live before the first synthesis
                        # instead of arriving a turn late.
                        asyncio.create_task(self._ensure_call_context())
                        asyncio.create_task(self.trigger_initial_greeting())
                    elif event_type == "media":
                        payload = data["media"].get("payload")
                        if payload:
                            mulaw_bytes = base64.b64decode(payload)
                            await self.handle_twilio_audio(mulaw_bytes)
                    elif event_type == "mark":
                        mark_name = data.get("mark", {}).get("name", "")
                        if mark_name:
                            await self.handle_twilio_mark(mark_name)
                    elif event_type == "stop":
                        logger.info("📴 [CascadedOrchestrator] Twilio stream stopped")
                        break
                except Exception as e:
                    logger.error(f"🔴 [CascadedOrchestrator] Error processing Twilio message: {e}", exc_info=True)
        finally:
            self.is_running = False
            dg_task.cancel()
            await self.stop()

