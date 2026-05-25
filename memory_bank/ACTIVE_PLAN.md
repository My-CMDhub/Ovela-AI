# Ovela AI - Active Plan

This tracks our active granular task checklists. We focus on a high-level, senior-level architectural audit and full-system fortification of the entire voice agent system for production-grade scale, reliability, and multi-agent ADK graph orchestration.

---

## 🚩 Current Active Phase: Phase 4 — Stress Testing, Caching & Performance Tuning

Phase 3 (Voice Agent Integration & Bridging) is **100% COMPLETE** with 37/37 tests green. Phase 4 focuses on performance optimization, real-time UI, and final polish for the judging demo.

---

## 📝 Active Task Board

### 🎯 Task 4.1: Gemini Prompt Caching in ADK Graph [DONE]
- [x] Configure `LlmAgent` instances in `backend/services/adk/graph.py` to leverage Gemini's `cachedContent` for static system instructions.
- [x] Target: reduce token overhead by ~60% on repeated multi-turn calls.
- [x] Verify: ADK unit tests still pass; add latency log check showing reduced TTFT.

### 🎯 Task 4.2: Interruption System Tags [DONE]
- [x] On VAD interruption in `handler.py`, inject `[System Note: Caller interrupted. Continue from last confirmed point.]` into Deepgram message context.
- [x] Ensure the tag is not spoken aloud (stripped from TTS output).
- [x] Write TDD test confirming the tag is added on VAD interrupt and not emitted to TTS.

### 🎯 Task 4.3: Behind-the-Scenes Live Visual Feed UI [UPCOMING]
- [ ] Build a real-time dashboard component in Next.js frontend showing:
  - Active caller's name + room preference (from CallerMemoryBank)
  - ADK routing decisions (which worker was called)
  - Live DB search events, booking events, Stripe payment links
- [ ] Connect via polling to `/api/adk/health` + new `/api/calls/live-state` endpoint.
- [ ] Demo-quality: must look polished for judging presentation.

### 🎯 Task 4.4: Concurrency Stress Testing [UPCOMING]
- [ ] Simulate 3 concurrent Twilio WebSocket connections to `handler.py`.
- [ ] Verify no session cross-contamination between `CallerMemoryBank` instances.
- [ ] Verify `ADKOrchestrator` InMemory sessions are isolated per `call_sid`.
- [ ] Clean up known tech-debt: `_transfer_tts_done` ghost events and max-capping silence monitor.

### 🎯 Task 4.5: GCP Deployment & Final Verification [UPCOMING]
- [ ] Package backend for Google Cloud Run deployment.
- [ ] Validate Twilio webhook URLs point to GCP endpoints.
- [ ] Perform end-to-end voice call test on GCP (not localhost).
- [ ] Final judging demo dry-run with 3-minute presentation script.
