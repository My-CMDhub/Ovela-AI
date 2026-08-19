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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Callable, Coroutine, AsyncGenerator
import httpx
import sentry_sdk
from fastapi import WebSocket

from core.config import settings
from services.voice_agent.vad import VadProcessor, ConversationState, is_backchannel_word
from services.voice_agent.interruption import (
    MarkTracker,
    prune_conversation_history,
    route_transcript,
    cognitive_delay,
)
from services.voice_agent.bridges.deepgram_standalone import DeepgramStandaloneBridge
from services.voice_agent.bridges.cartesia_standalone import CartesiaStandaloneBridge
from services.voice_agent.text_utils import prepare_for_tts
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt
from services.voice_agent.functions.coalcreek_definitions import get_coalcreek_functions

logger = logging.getLogger(__name__)


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
        self.is_running = False
        self.current_context_id: Optional[str] = None
        self._pending_llm_task: Optional[asyncio.Task] = None

        # Phase 12 modular components
        self.vad = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        self.mark_tracker = MarkTracker()
        self.deepgram = DeepgramStandaloneBridge(sample_rate=8000, model="flux-general-en")
        self.cartesia = CartesiaStandaloneBridge(model_id="sonic-3", sample_rate=8000)

        # Word tracking for current TTS turn
        self._current_turn_word_count = 0

        # True once this turn's first audio chunk has reached Twilio. Barge-in
        # stays disarmed until then so LLM think-time can't be interrupted.
        self._agent_audio_started: bool = False

        # Control-flow tool actions. The dispatcher signals call termination by
        # returning {"action": "hangup"}; it is executed after the farewell has
        # finished streaming, not at dispatch time.
        self._pending_hangup: bool = False
        self._pending_transfer: Optional[str] = None
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
                    is_speech
                    and self.state == ConversationState.AGENT_SPEAKING
                    and self._agent_audio_started
                ):
                    if not self.vad.is_immune():
                        await self.trigger_barge_in(reason="local_vad_acoustic")
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

        # 3. Prune un-heard words from last assistant message per MarkTracker
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
                return
            except Exception as e:
                logger.warning(f"🟡 [CascadedOrchestrator] Failed playing cached greeting audio clip: {e}")
            finally:
                if self.state == ConversationState.AGENT_SPEAKING:
                    self.state = ConversationState.AWAITING_INPUT

        # Fallback: Stream initial greeting via Cartesia TTS
        try:
            self.current_context_id = f"greeting_{int(time.time()*1000)}"
            word_count = 0
            async for audio_chunk, marks in self.cartesia.stream_speech(
                text=greeting,
                context_id=self.current_context_id,
                continue_stream=False
            ):
                if not self.is_running or self.state != ConversationState.AGENT_SPEAKING:
                    break
                payload_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                media_event = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload_b64}
                }
                if self.twilio_ws:
                    await self.twilio_ws.send_text(json.dumps(media_event))

                for mark in marks:
                    mark_event = {
                        "event": "mark",
                        "streamSid": self.stream_sid,
                        "mark": {"name": mark}
                    }
                    if self.twilio_ws:
                        await self.twilio_ws.send_text(json.dumps(mark_event))
                    word_count += 1
            self.mark_tracker.set_total_words(word_count)
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Failed streaming initial greeting: {e}")
        finally:
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
                if (
                    self.state == ConversationState.AGENT_SPEAKING
                    and self._agent_audio_started
                    and not self.vad.is_immune()
                ):
                    await self.trigger_barge_in(reason="deepgram_start_of_turn")

            elif turn_state == "EagerEndOfTurn":
                logger.info("⚡ [CascadedOrchestrator] EagerEndOfTurn received. Pre-warming LLM...")

            elif turn_state == "TurnResumed":
                logger.info("🔄 [CascadedOrchestrator] TurnResumed received. Canceling early LLM preparation.")
                if self._pending_llm_task and not self._pending_llm_task.done():
                    self._pending_llm_task.cancel()

            elif turn_state in ("EndOfTurn", "SpeechEnded", "Results"):
                # `Update` is interim — deliberately excluded so the LLM fires
                # once on turn end, not on every partial transcript.
                if transcript:
                    await self.handle_user_turn_complete(transcript)

    async def handle_user_turn_complete(self, transcript: str) -> None:
        """
        Handle finalized user utterance after Deepgram Flux verifies turn completion.
        """
        action = route_transcript(transcript, state=self.state)
        if action == "ignore":
            logger.info(f"🔇 [CascadedOrchestrator] Ignored transcript/backchannel: '{transcript}'")
            return

        logger.info(f"🗣️ [CascadedOrchestrator] User finished turn: '{transcript}'")
        self.history.append({"role": "user", "content": transcript})
        self.state = ConversationState.AGENT_SPEAKING

        # Immunity is armed when the first audio chunk actually reaches Twilio,
        # not here — see audio_receiver().
        self._agent_audio_started = False
        self.mark_tracker.reset()
        self._current_turn_word_count = 0
        self.current_context_id = f"ctx_{uuid.uuid4().hex[:8]}"

        # Start Sentry transaction and Span 1
        self._sentry_transaction = sentry_sdk.start_transaction(name="user_voice_turn_transaction")
        self._span_1 = self._sentry_transaction.start_child(
            op="pipeline.span1",
            name="Span 1: User Speech Ended -> First Token Yielded"
        )
        self._span_3 = None

        # Start parallel streaming pipeline
        self._pending_llm_task = asyncio.create_task(
            self._run_parallel_streaming_pipeline()
        )
        await self._pending_llm_task

    async def _run_parallel_streaming_pipeline(self) -> None:
        """
        Coordinates parallel LLM token generation, phrase extraction,
        TTS synthesis, and Twilio audio streaming.
        """
        start_time = time.time()
        llm_queue = asyncio.Queue()

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
                            if self._span_1:
                                self._span_1.finish()
                            if self._sentry_transaction:
                                self._span_3 = self._sentry_transaction.start_child(
                                    op="pipeline.span3",
                                    name="Span 3: First Token Yielded -> Cartesia First Audio Chunk Ingestion"
                                )
                        if self.state != ConversationState.AGENT_SPEAKING:
                            break
                        await llm_queue.put(token)
                else:
                    text = await res
                    if first_token:
                        first_token = False
                        if self._span_1:
                            self._span_1.finish()
                        if self._sentry_transaction:
                            self._span_3 = self._sentry_transaction.start_child(
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
        full_response_parts = []
        self._total_words_sent = 0

        async def audio_receiver():
            first_chunk_ingested = False
            # Cartesia multiplexes every context over one socket. After a
            # barge-in cancel, the killed context still emits trailing chunks
            # and a `done`; without this filter that stale `done` breaks the
            # NEXT turn's receiver and the caller hears silence.
            turn_context_id = self.current_context_id
            try:
                async for audio_evt in self.cartesia.receive_audio_events():
                    if self.state != ConversationState.AGENT_SPEAKING:
                        break  # Barge-in occurred mid-stream!

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
                            self.vad.arm_immunity(duration_s=0.5)
                            # End Span 3
                            if self._span_3:
                                self._span_3.finish()
                            if self._sentry_transaction:
                                total_latency_ms = (time.time() - start_time) * 1000.0
                                self._sentry_transaction.set_data("first_audio_latency_ms", total_latency_ms)
                                self._sentry_transaction.finish()

                        base64_data = audio_evt.get("data")
                        if base64_data and self.stream_sid:
                            media_payload = {
                                "event": "media",
                                "streamSid": self.stream_sid,
                                "media": {"payload": base64_data},
                            }
                            await self.twilio_ws.send_text(json.dumps(media_payload))

                            # Send milestone marks every ~3 words to keep Twilio sync tight
                            self._current_turn_word_count += 3
                            if self._current_turn_word_count > self._total_words_sent:
                                self._current_turn_word_count = self._total_words_sent
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

        text_buffer = ""
        is_first_phrase = True

        try:
            while True:
                if self.state != ConversationState.AGENT_SPEAKING:
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
                    if self.state != ConversationState.AGENT_SPEAKING:
                        break

                    full_response_parts.append(phrase.strip())

                    # Call text normalizer (Decision 4 - prepare_for_tts)
                    clean_phrase, _ = prepare_for_tts(phrase)
                    clean_phrase_stripped = clean_phrase.strip()

                    if not clean_phrase_stripped:
                        continue

                    self._total_words_sent += len(clean_phrase_stripped.split())

                    # Apply cognitive delay if it is the first phrase
                    if is_first_phrase:
                        is_first_phrase = False
                        elapsed_s = time.time() - start_time
                        delay_ms = cognitive_delay(elapsed_s)
                        if delay_ms > 0:
                            await asyncio.sleep(delay_ms / 1000.0)

                    is_last_phrase = is_last_chunk and (not text_buffer) and (phrases.index(phrase) == len(phrases) - 1)

                    await self.cartesia.send_transcript_chunk(
                        context_id=self.current_context_id,
                        transcript=clean_phrase_stripped,
                        continue_stream=not is_last_phrase,
                    )

                if is_final:
                    break
        except Exception as e:
            logger.error(f"🔴 [CascadedOrchestrator] Phrase streaming error: {e}", exc_info=True)
        finally:
            # Cleanup any active Sentry spans
            if self._span_1 and getattr(self._span_1, 'timestamp', None) is None:
                try:
                    self._span_1.finish()
                except Exception:
                    pass
            if self._span_3 and getattr(self._span_3, 'timestamp', None) is None:
                try:
                    self._span_3.finish()
                except Exception:
                    pass
            if self._sentry_transaction and getattr(self._sentry_transaction, 'timestamp', None) is None:
                try:
                    self._sentry_transaction.finish()
                except Exception:
                    pass

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

            interrupted = self.state != ConversationState.AGENT_SPEAKING
            if not interrupted:
                full_text = " ".join(full_response_parts).strip()
                if full_text:
                    self.history.append({"role": "assistant", "content": full_text})
                self.state = ConversationState.AWAITING_INPUT

            # Farewell has finished streaming — now end the call. A caller who
            # spoke over the goodbye is still talking, so the hangup is dropped
            # rather than deferred.
            if self._pending_hangup:
                self._pending_hangup = False
                if interrupted:
                    logger.info(
                        "🛑 [CascadedOrchestrator] Hangup aborted — user spoke during farewell"
                    )
                else:
                    await self._hangup_call()

            # A transfer is never aborted by barge-in: the caller asking again
            # while the handoff line plays still wants the human.
            if self._pending_transfer:
                transfer_to, self._pending_transfer = self._pending_transfer, None
                await self._transfer_call(transfer_to)

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

    async def stop(self) -> None:
        """
        Stop the orchestrator and close all active bridges.
        """
        self.is_running = False
        if self._pending_llm_task and not self._pending_llm_task.done():
            self._pending_llm_task.cancel()
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
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        await self._apply_voice_settings()
        self._context_ready = True
        logger.info(
            f"🧩 [CascadedOrchestrator] Call context ready | tenant={self.tenant_id} "
            f"| adk_singleton={'yes' if adk_orchestrator else 'no'}"
        )

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
            }] + list(history)
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
                        tool_span = self._sentry_transaction.start_child(
                            op="tool.execute", name=f"Tool: {call['name']}",
                        )
                    try:
                        result = await self.dispatcher.execute(call["name"], args)
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
                        elif result.get("action") == "transfer" and result.get("transfer_to"):
                            self._pending_transfer = result["transfer_to"]
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

