# Ovela AI - Active Plan

This tracks our active granular task checklists. We focus on a high-level, senior-level architectural audit and full-system fortification of the entire voice agent system for production-grade scale, reliability, and multi-agent ADK graph orchestration.

---

## 🚩 Current Active Phase: Phase 3 - Voice Agent Integration & Bridging

Now that our core modules (ADK Graph, Caller Memory Bank, Stripe payments, and Interruption trimming) are fully built, audited, and tested with a 30/30 green unit test suite, our active objective is to connect these fortified systems directly into the live Twilio voice streaming handler (`handler.py`).

---

## 📝 Active Task Board

### 🎯 Task 1: Wire CallerMemoryBank into twilio initialization [IN_PROGRESS]
- [ ] Connect `CallerMemoryBank` instance to the main `OvelaVoiceAgent` class.
- [ ] In `_handle_twilio_start` or connection establishment, fetch caller profile using `get_profile(caller_phone)`.
- [ ] Inject retrieved caller data (e.g. name, room preferences, last visit date) into the initial system prompt or greeting context so returning guests are instantly recognized.
- [ ] In `update_guest_info` tool dispatcher hook, ensure new/updated guest profiles are asynchronously committed back to the DB via `save_profile(caller_phone, updated_data)`.
- [ ] Verify error containment: prove database connectivity issues do not block or delay live websocket establishment.

### 🎯 Task 2: Bridge ADK Graph Webhook Routing [UPCOMING]
- [ ] Instantiate `ADKOrchestrator` in FastAPI backend server.
- [ ] Wire Gemini webhook tool triggers (from Deepgram Cold Path) to route availability checking, bookings, and details through `ADKOrchestrator.query(call_sid, session_id, query)`.
- [ ] Verify that ADK session variables retain state correctly across sequential multi-agent tool handoffs.

### 🎯 Task 3: Map Stripe checkout to Booking Tool Dispatch [UPCOMING]
- [ ] In the booking confirmation webhook tool handler, extract guest phone and email.
- [ ] Call `stripe_handlers.create_checkout_session(amount_aud, room_type, booking_ref)`.
- [ ] If Stripe URL is generated successfully, trigger a background task to SMS the link to the guest (or output the URL via Cartesia TTS if they ask for it directly).
- [ ] Gracefully handle blank/missing Stripe API keys by falling back to "Soft Hold / Manual Confirm at Reception".

### 🎯 Task 4: Stress Testing, Caching & Performance Tuning [UPCOMING]
- [ ] Integrate **Gemini Prompt Caching** inside ADK graph models to optimize token overhead and slash TTFT latency.
- [ ] Inject **Interruption System Tags** (`[System Note: ... ]`) on VAD interruption triggers to preserve conversational context.
- [ ] Fine-tune **Cartesia SSML Filler Parameters** (fast verbal responses + dynamic pauses) to cover back-end tool execution times.
- [ ] Build the **Behind-the-Scenes live visual feed UI** in the Next.js dashboard showing real-time caller preferences, ADK routing decisions, database searches, and payment events.
- [ ] Perform concurrency stress tests to verify WebSocket memory boundaries under load.
- [ ] Clean up minor tech-debt items: `_transfer_tts_done` ghost events and max-capping silence monitor loops.

