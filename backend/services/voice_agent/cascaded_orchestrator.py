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
from typing import Optional, List, Dict, Any, Callable, Coroutine, AsyncGenerator
import sentry_sdk
from fastapi import WebSocket

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

        # Core state & history
        self.state = ConversationState.AWAITING_INPUT
        self.history: List[Dict[str, Any]] = []
        self.is_running = False
        self.current_context_id: Optional[str] = None
        self._pending_llm_task: Optional[asyncio.Task] = None

        # Phase 12 modular components
        self.vad = VadProcessor(aggressiveness=3, sample_rate=8000, frame_ms=20)
        self.mark_tracker = MarkTracker()
        self.deepgram = DeepgramStandaloneBridge(sample_rate=8000, model="flux", version="v2")
        self.cartesia = CartesiaStandaloneBridge(model_id="sonic-english", sample_rate=8000)

        # Word tracking for current TTS turn
        self._current_turn_word_count = 0

        # Sentry transaction and span tracking
        self._sentry_transaction = None
        self._span_1 = None
        self._span_2 = None
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

        # Optimize semantic turn-taking endpointing
        await self.deepgram.send_configure(eot_threshold=0.6, eot_timeout_ms=1000)

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
                if is_speech and self.state == ConversationState.AGENT_SPEAKING:
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

    async def process_deepgram_events(self) -> None:
        """
        Process conversational events from Deepgram Flux v2.
        """
        async for event in self.deepgram.receive_events():
            event_type = event.get("type")

            if event_type == "StartOfTurn" or event_type == "SpeechStarted":
                if self.state == ConversationState.AGENT_SPEAKING and not self.vad.is_immune():
                    await self.trigger_barge_in(reason="deepgram_start_of_turn")

            elif event_type == "EagerEndOfTurn":
                logger.info("⚡ [CascadedOrchestrator] EagerEndOfTurn received. Pre-warming LLM...")
                # Could trigger early LLM preparation here

            elif event_type == "TurnResumed":
                logger.info("🔄 [CascadedOrchestrator] TurnResumed received. Canceling early LLM preparation.")
                if self._pending_llm_task and not self._pending_llm_task.done():
                    self._pending_llm_task.cancel()

            elif event_type == "EndOfTurn" or event_type == "SpeechEnded":
                channel = event.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "").strip()
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

        # Arm echo immunity for the first 500ms of agent response
        self.vad.arm_immunity(duration_s=0.5)
        self.mark_tracker.reset()
        self._current_turn_word_count = 0
        self.current_context_id = f"ctx_{uuid.uuid4().hex[:8]}"

        # Start Sentry transaction and Span 1
        self._sentry_transaction = sentry_sdk.start_transaction(name="user_voice_turn_transaction")
        self._span_1 = self._sentry_transaction.start_child(
            op="pipeline.span1",
            name="Span 1: User Speech Ended -> Tool/DB Resolution"
        )
        self._span_2 = None
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
                            # Finish Span 1 (Tool/DB Resolution complete)
                            if self._span_1:
                                self._span_1.finish()
                            # Start and immediately finish Span 2 (First Token Yielded)
                            if self._sentry_transaction:
                                self._span_2 = self._sentry_transaction.start_child(
                                    op="pipeline.span2",
                                    name="Span 2: Tool/DB Resolution -> First Token Yielded"
                                )
                                self._span_2.finish()
                                # Start Span 3: First Token Yielded -> Cartesia First Audio Chunk Ingestion
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
                        # Finish Span 1
                        if self._span_1:
                            self._span_1.finish()
                        # Start and finish Span 2
                        if self._sentry_transaction:
                            self._span_2 = self._sentry_transaction.start_child(
                                op="pipeline.span2",
                                name="Span 2: Tool/DB Resolution -> First Token Yielded"
                            )
                            self._span_2.finish()
                            # Start Span 3
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
            try:
                async for audio_evt in self.cartesia.receive_audio_events():
                    if self.state != ConversationState.AGENT_SPEAKING:
                        break  # Barge-in occurred mid-stream!

                    evt_type = audio_evt.get("type")
                    if evt_type == "chunk":
                        if not first_chunk_ingested:
                            first_chunk_ingested = True
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
            if self._span_2 and getattr(self._span_2, 'timestamp', None) is None:
                try:
                    self._span_2.finish()
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

            try:
                await producer_task
            except asyncio.CancelledError:
                pass

            try:
                await receiver_task
            except asyncio.CancelledError:
                pass

            if self.state == ConversationState.AGENT_SPEAKING:
                full_text = " ".join(full_response_parts).strip()
                if full_text:
                    self.history.append({"role": "assistant", "content": full_text})
                self.state = ConversationState.AWAITING_INPUT

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
            from services.adk.graph import ADKOrchestrator
            orchestrator = ADKOrchestrator()
            user_id = self.stream_sid or "cascaded_session"
            session = await orchestrator.get_or_create_session(user_id=user_id)
            async for chunk in orchestrator.query_stream(
                user_id=user_id,
                session_id=session.id,
                text=latest_user_text,
            ):
                yield chunk
        except Exception as e:
            logger.warning(f"🟡 [CascadedOrchestrator] ADK fallback generation warning: {e}")
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
                        logger.info(f"🚀 [CascadedOrchestrator] Twilio stream started: {self.stream_sid}")
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

