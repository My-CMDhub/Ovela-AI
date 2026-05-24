# Ovela AI - End Session

**Session Date:** 2026-05-24 (Session 4)
**Current Active Branch:** `feat/gemini-adk-migration`
**HEAD Commit:** `9fd5a29` (Phase 3 complete — all 3 tasks done)

---

## 🏁 Current Active Status

Phase 3 is **100% COMPLETE**:
- **Task 1 — CallerMemoryBank Hookup:** Profile fetched async-safely in `_handle_twilio_start`, injected into `self.memory["name"]` + `self.memory["room_type"]` before Deepgram Settings are sent. `save_profile()` fired as background task on `update_guest_info`. 7 TDD tests green.
- **Task 2 — ADK Graph Webhook Routing:** `ADKOrchestrator` singleton instantiated in `main.py` startup_event stored in `app.state`. New `/api/adk/query` (POST) + `/api/adk/health` (GET) routes live in `backend/api/adk.py`. `fire_adk_cold_path()` method added to `CoalCreekFunctionDispatcher` — fires after `create_booking_request` success.
- **Task 3 — Stripe Checkout Dispatch:** After `create_booking_request` success, `_send_stripe_link()` coroutine fires as `asyncio.create_task`. Generates Stripe hosted URL and SMS's it to guest phone via `staff_notification_service`. Full graceful fallback if `STRIPE_SECRET_KEY` missing.
- **Suite:** **37 / 37 tests green** (`pytest backend/tests/`)

---

## 🎯 Next Session Starting Target

- **Starting Phase:** Phase 4 — Stress Testing, Caching & Performance Tuning
- **Primary Starting Point:** `backend/services/adk/graph.py`
- **First Goal:** Implement **Gemini Prompt Caching** inside the ADK graph's LlmAgent models to optimize token overhead and reduce TTFT latency for the booking cold path.

---

## 🛠️ Step-by-Step Context Handoff

1. **Gemini Prompt Caching (Task 4.1):**
   - Configure `LlmAgent` in `graph.py` to use Gemini's `cachedContent` API for the static system instructions (Manager, BookingWorker, InfoWorker).
   - Target: reduce token overhead on repeated multi-turn calls by ~60%.
   - Verify: ADK unit tests still pass + latency log shows reduced TTFT.

2. **Interruption System Tags (Task 4.2):**
   - Inject `[System Note: Caller interrupted. Continue from last confirmed point.]` into Deepgram message context on VAD interruption trigger in `handler.py`.
   - Ensure the tag is stripped from TTS output (not spoken aloud).

3. **Behind-the-Scenes Live Visual Feed (Task 4.3):**
   - Build the real-time dashboard component in Next.js that shows:
     - Caller preferences (name, room_type from CallerMemoryBank)
     - ADK routing decisions (which worker handled each query)
     - DB search events, Stripe payment events
   - Connect via WebSocket or polling to new `/api/adk/health` + future `/api/calls/live-state` endpoint.

4. **Concurrency Stress Tests (Task 4.4):**
   - Simulate 3 concurrent WebSocket connections to `handler.py` and verify no session cross-contamination.

5. **DO NOT touch:**
   - VAD clear-event guard logic.
   - `trim_assistant_transcript` formula.
   - `fire_adk_cold_path()` — it is working, don't refactor.

---

## 🛡️ Architecture & Latency Invariants

- **Hot Path Invariant:** Twilio ↔ Deepgram ↔ Gemini 2.0 Flash ↔ Cartesia must bypass all DB and Stripe calls. Target: <850ms.
- **Cold Path Invariant:** ADKOrchestrator, Appwrite CRUD, Stripe checkout are async background tasks via `asyncio.create_task`. Never awaited on the hot path.
- **Interruption Trim Invariant:** `trim_assistant_transcript` (~150 WPM) in `handler.py` is mathematically calibrated and tested — do not modify.
