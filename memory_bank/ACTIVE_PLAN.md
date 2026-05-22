# Ovela AI - Active Plan

This tracks our active granular task checklists. We focus on a high-level, senior-level architectural audit and full-system fortification of the entire voice agent system for production-grade scale, reliability, and multi-agent ADK graph orchestration.

---

## 🚩 Current Active Phase: Phase 2 - System Audit & Production Fortification

Instead of feature-by-feature iteration, we approach the voice agent with a senior-level audit posture. We evaluate the entire backend layout, expose latent bottlenecks, calibrate multi-agent graph flows using Google's ADK, and build a highly fortified runtime.

---

## 📝 Active Task Board

### ✅ Task 1: Senior-Level Architectural Audit — COMPLETE
- [x] Line-by-line audit of `handler.py`, `config.py`, `abuse_protection.py`.
- [x] Found and fixed `get_preset_phrase()` silent arg inversion (L1322).
- [x] Re-enabled `_generate_call_summary()` (removed hard-disabled `return ""`).
- [x] Removed stale in-function `import logging` from transfer block.
- [x] Documented all active risks in `brain/*/audit_and_code_review.md`.

### ✅ Task 2: Vertex AI ADK Graph & CallerMemoryBank — COMPLETE
- [x] Installed `google-adk 2.0.0` + added to `requirements.txt`.
- [x] Built `backend/services/adk/graph.py`: ADKOrchestrator with OvelaManager → BookingWorker + InfoWorker.
- [x] Built `backend/services/voice_agent/memory.py`: CallerMemoryBank (get_profile + save_profile).
- [x] 9 new TDD tests: `test_memory_bank.py` (5) + `test_adk_graph.py` (4). All passing.
- [x] Total test suite: **16/16 green**. Commit: `d184754`.

### ✅ Task 3: Conversational Hardening — Interruption Trimming — COMPLETE
- [x] `trim_assistant_transcript(text, elapsed_seconds, wpm=150)` added as module-level pure function in `handler.py`.
- [x] `_tts_playback_start = time.time()` tracked in `_handle_agent_started_speaking()`.
- [x] Trim wired in `_handle_user_started_speaking()` before Twilio clear — prunes last AI transcript entry.
- [x] 8 TDD tests in `test_conversational_hardening.py` — all passing.

### ✅ Task 4: Stripe Automated Payments — COMPLETE
- [x] `backend/services/voice_agent/functions/stripe_handlers.py` created.
- [x] `create_checkout_session(amount_aud, room_type)` → Stripe URL | None. AUD, cents, error-contained.
- [x] 6 TDD tests in `test_stripe_and_email.py` — all passing.
- [x] Total test suite: **30/30 green**. Commit: `75dd03b`.
