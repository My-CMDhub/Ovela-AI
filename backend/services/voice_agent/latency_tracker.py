"""
Voice Agent Latency Tracker.

Per-turn, per-stage timing instrumentation with correlation IDs.
Logs structured latency data for every conversation turn.

Stages tracked per turn:
  1. user_vad        — UserStartedSpeaking (VAD trigger)
  2. stt_complete    — ConversationText(role=user) received
  3. llm_first_token — ConversationText(role=assistant) first sentence
  4. agent_speaking  — AgentStartedSpeaking event
  5. first_audio_out — First binary audio frame sent to Twilio
  6. agent_done      — AgentAudioDone event

Function-call turns additionally track:
  7. func_request    — FunctionCallRequest received
  8. func_exec_done  — Function execution completed
  9. func_response   — FunctionCallResponse sent to Deepgram
"""

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TurnTiming:
    """Timing data for a single conversation turn."""
    turn_id: int = 0
    has_function_call: bool = False
    turn_type: str = "unknown"  # short_answer | long_answer | tool_call | goodbye | unknown

    # Absolute timestamps (time.monotonic)
    user_vad: float = 0.0
    stt_complete: float = 0.0
    llm_first_token: float = 0.0
    agent_speaking: float = 0.0
    first_audio_out: float = 0.0
    agent_done: float = 0.0

    # Function-call sub-stages
    func_request: float = 0.0
    func_exec_done: float = 0.0
    func_response: float = 0.0

    def _delta(self, start: float, end: float) -> int:
        """Return ms delta or -1 if either is unset."""
        if start > 0 and end > 0:
            return int((end - start) * 1000)
        return -1

    def summary(self) -> dict:
        """Return a dict of computed deltas (ms) for this turn."""
        d = {
            "turn": self.turn_id,
            "tool_call": self.has_function_call,
            "turn_type": self.turn_type,
            "vad_to_stt_ms": self._delta(self.user_vad, self.stt_complete),
            "stt_to_first_token_ms": self._delta(self.stt_complete, self.llm_first_token),
            "first_token_to_audio_ms": self._delta(self.llm_first_token, self.first_audio_out),
            "total_user_to_audio_ms": self._delta(self.user_vad, self.first_audio_out),
            "total_user_to_first_token_ms": self._delta(self.user_vad, self.llm_first_token),
        }
        if self.has_function_call:
            d["func_exec_ms"] = self._delta(self.func_request, self.func_exec_done)
            d["func_total_ms"] = self._delta(self.func_request, self.func_response)
            d["stt_to_func_request_ms"] = self._delta(self.stt_complete, self.func_request)
            d["func_response_to_audio_ms"] = self._delta(self.func_response, self.first_audio_out)
        return d

    def log_line(self) -> str:
        """One-line summary for logging."""
        s = self.summary()
        parts = [f"T{s['turn']}"]
        if self.turn_type != "unknown":
            parts.append(self.turn_type.upper())
        if s["tool_call"]:
            parts.append("TOOL")
        for key in ("vad_to_stt_ms", "stt_to_first_token_ms",
                     "first_token_to_audio_ms", "total_user_to_audio_ms"):
            v = s.get(key, -1)
            if v >= 0:
                parts.append(f"{key}={v}")
        if s["tool_call"]:
            for key in ("func_exec_ms", "func_total_ms"):
                v = s.get(key, -1)
                if v >= 0:
                    parts.append(f"{key}={v}")
        return " | ".join(parts)


class LatencyTracker:
    """Per-call latency tracker. One instance per VoiceAgentHandler."""

    def __init__(self):
        self._turn_counter = 0
        self._current: TurnTiming | None = None
        self._history: list[TurnTiming] = []

        # Call-level setup timings (monotonic)
        self.call_start: float = 0.0
        self.deepgram_connected: float = 0.0
        self.settings_sent: float = 0.0
        self.tenant_config_loaded: float = 0.0
        self.first_audio_received: float = 0.0

    # ── Call-level marks ─────────────────────────────────────────────

    def mark_call_start(self):
        self.call_start = time.monotonic()

    def mark_tenant_config_loaded(self):
        self.tenant_config_loaded = time.monotonic()

    def mark_deepgram_connected(self):
        self.deepgram_connected = time.monotonic()

    def mark_settings_sent(self):
        self.settings_sent = time.monotonic()

    def mark_first_audio_received(self):
        if self.first_audio_received == 0.0:
            self.first_audio_received = time.monotonic()

    def log_setup_latency(self):
        """Log call-setup timing breakdown."""
        if self.call_start <= 0:
            return
        parts = []
        if self.tenant_config_loaded > 0:
            parts.append(f"config={int((self.tenant_config_loaded - self.call_start) * 1000)}ms")
        if self.deepgram_connected > 0:
            parts.append(f"dg_connect={int((self.deepgram_connected - self.call_start) * 1000)}ms")
        if self.settings_sent > 0:
            parts.append(f"settings={int((self.settings_sent - self.call_start) * 1000)}ms")
        if self.first_audio_received > 0:
            parts.append(f"first_audio={int((self.first_audio_received - self.call_start) * 1000)}ms")
        logger.info(f"⏱️ SETUP LATENCY: {' | '.join(parts)}")

    # ── Per-turn marks ───────────────────────────────────────────────

    def new_turn(self) -> int:
        """Start a new turn and return its ID."""
        if self._current and self._current.user_vad > 0:
            self._history.append(self._current)
        self._turn_counter += 1
        self._current = TurnTiming(turn_id=self._turn_counter)
        return self._turn_counter

    @property
    def current(self) -> TurnTiming | None:
        return self._current

    def mark_user_vad(self):
        if not self._current or self._current.stt_complete > 0:
            self.new_turn()
        if self._current:
            self._current.user_vad = time.monotonic()

    def mark_stt_complete(self):
        if self._current:
            self._current.stt_complete = time.monotonic()

    def mark_llm_first_token(self):
        if self._current and self._current.llm_first_token == 0.0:
            self._current.llm_first_token = time.monotonic()

    def mark_agent_speaking(self):
        if self._current:
            self._current.agent_speaking = time.monotonic()

    def mark_first_audio_out(self):
        if self._current and self._current.first_audio_out == 0.0:
            self._current.first_audio_out = time.monotonic()

    def mark_agent_done(self):
        if self._current:
            self._current.agent_done = time.monotonic()

    def mark_func_request(self):
        if self._current:
            self._current.has_function_call = True
            self._current.func_request = time.monotonic()

    def mark_func_exec_done(self):
        if self._current:
            self._current.func_exec_done = time.monotonic()

    def mark_func_response(self):
        if self._current:
            self._current.func_response = time.monotonic()

    def set_turn_type(self, t: str):
        """Tag the current turn type (short_answer|long_answer|tool_call|goodbye|unknown)."""
        if self._current:
            self._current.turn_type = t
            if t == "tool_call":
                self._current.has_function_call = True

    def audio_lead_ms(self) -> int:
        """How many ms audio bytes arrived BEFORE the ConversationText event.

        Positive means audio was already streaming to the caller before we
        got the text transcript — i.e. the ack word was being heard already.
        Returns 0 if audio hasn't arrived yet or no first_audio_out recorded.
        """
        if (self._current
                and self._current.first_audio_out > 0
                and self._current.llm_first_token > 0):
            delta = self._current.llm_first_token - self._current.first_audio_out
            return max(0, int(delta * 1000))
        return 0

    def log_turn(self):
        """Log the current turn's latency summary."""
        if self._current and self._current.user_vad > 0 and self._current.stt_complete > 0:
            logger.info(f"⏱️ TURN LATENCY: {self._current.log_line()}")

    # ── End-of-call summary ──────────────────────────────────────────

    def log_call_summary(self):
        """Log aggregate stats for the entire call."""
        all_turns = list(self._history)
        if self._current and self._current.user_vad > 0:
            all_turns.append(self._current)
        if not all_turns:
            return

        normal = [t for t in all_turns if not t.has_function_call and t.first_audio_out > 0 and t.user_vad > 0]
        tool = [t for t in all_turns if t.has_function_call and t.first_audio_out > 0 and t.user_vad > 0]

        def _avg(turns: list[TurnTiming], attr_start: str, attr_end: str) -> int:
            vals = []
            for t in turns:
                s, e = getattr(t, attr_start, 0.0), getattr(t, attr_end, 0.0)
                if s > 0 and e > 0:
                    vals.append((e - s) * 1000)
            return int(sum(vals) / len(vals)) if vals else -1

        parts = [f"turns={len(all_turns)}"]
        if normal:
            avg_e2e = _avg(normal, "user_vad", "first_audio_out")
            avg_ttft = _avg(normal, "stt_complete", "llm_first_token")
            parts.append(f"normal(n={len(normal)}, avg_e2e={avg_e2e}ms, avg_ttft={avg_ttft}ms)")
        if tool:
            avg_e2e = _avg(tool, "user_vad", "first_audio_out")
            avg_exec = _avg(tool, "func_request", "func_exec_done")
            parts.append(f"tool(n={len(tool)}, avg_e2e={avg_e2e}ms, avg_exec={avg_exec}ms)")

        logger.info(f"⏱️ CALL LATENCY SUMMARY: {' | '.join(parts)}")
