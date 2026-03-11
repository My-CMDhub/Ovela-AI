# Stage B — LLM Swap, Prompt Tightening & UX Ceiling Analysis
**Date:** 2026-03-11  
**Branch:** `personal/assistant`  
**Status:** Active — gpt-4.1-nano is the winner so far

---

## 0. Model Comparison Results (2026-03-11 Production Logs)

### LLMs Tested on Deepgram Managed

| Model | avg TTFT (normal turns) | avg e2e | Notes |
|-------|------------------------|---------|-------|
| `gpt-4.1-mini` (baseline) | 973ms | 2251ms | Solid, reliable function calling |
| `claude-haiku-4-5` (managed) | **2916ms** | 4815ms | ❌ Significantly slower than baseline |
| `gemini-2.0-flash` (managed) | **777ms** | 2792ms | ⚠️ Fast TTFT but response truncation bug |
| `gpt-4.1-nano` (managed) | **732ms** | 2625ms | ✅ **Winner — faster + clean** |
| `gpt-5.2-instant` | TBD | TBD | Verified accepted by Deepgram, not yet tested in call |

### Gemini 2.0 Flash Issue (Diagnosed)
Gemini streams so fast that Deepgram's internal TTS mux picks up the first 1-2 tokens before ConversationText fires.
Our agent logs only see the remaining tokens, producing fragments: `at?`, `, how can I help?`, `with today?`.
**The caller may hear the full sentence (Deepgram handles TTS internally), but our transcript and filler detection are broken.** Do not use Gemini until this is confirmed fixed or worked around.

### Claude haiku-4-5 Issue
Deepgram managed routing for Claude adds overhead vs OpenAI. avg TTFT 2916ms = nearly 3× slower than gpt-4.1-mini. Not viable.

### gpt-4.1-nano — Current Default
- avg TTFT: **732ms** (25% faster than gpt-4.1-mini)
- Fastest TTFT observed: **606ms** (T8), **648ms** (T6)
- Function calling: ✅ working (check_availability, lookup_booking confirmed)
- Subjectively: "feels absolutely instant" on direct conversational turns

### gpt-5.2-instant — Next to Test
- Verified accepted by Deepgram WebSocket test (SettingsApplied ✓)
- Not yet production tested — set `llm_model: "gpt-5.2-instant"` in Appwrite voice_settings to try

---

## 0.1 Bugs Fixed (2026-03-11)

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| **Double filler for lookup** | `lookup_booking` called twice in same LLM turn (by ref then by email) → each triggered SLOW_TOOLS filler independently | Added `_filler_played_this_turn` flag; resets on each user utterance, gates SLOW_TOOLS system filler to fire at most once per user turn |
| **Multi-sentence leaking** | Exception clause "booking data collection" was too broad — model added "Would you like to...?" meta-offers after every answer | Tightened to: exception ONLY for actively collecting a specific missing field (dates/name/email/phone). "Would you like to..." and "Shall I..." are now explicitly forbidden as trailing sentences |
| **3-min auto-hangup in demo** | `DEMO_CONFIG` had `hard_cap_minutes: 3` — too short for test calls | Extended to `soft: 5min, hard: 8min`. Production config unchanged (10/12 min with staff transfer) |

---

## 1. Where We Are (Stage A Baseline)

### What Was Fixed in Stage A (release/v4)
| Change | Impact |
|--------|--------|
| STT: nova-3 → nova-2 | Reduced cold-start STT latency |
| `utterance_end_ms` → `endpointing: 300` (correct Voice Agent API field) | Endpointing now actually applied (was silently ignored before) |
| `smart_format: True` removed from provider block | Eliminated 200–400ms lookahead wait that was added illegally |
| LatencyTracker fully wired | Structured per-turn telemetry now available in all production logs |
| FIRST SENTENCE RULE added to prompt | First token is now shorter and self-contained |
| `check_availability` fast-start (concurrent filler) | Sub-100ms user-perceived wait before PMS result |
| SLOW_TOOLS grace period: 0.5s → 0.3s | 200ms saved on tool-call responses |

### Confirmed NOT the Problem
- **Cartesia TTS**: 0–17ms first-token-to-audio. Completely eliminated.
- **Deepgram VAD/STT**: Working correctly after endpointing fix. Short turns: 7–440ms. Long turns: 1000–4600ms (includes actual speech duration, expected).

### Confirmed Bottleneck
```
CALL LATENCY SUMMARY: turns=10 | normal(n=6, avg_e2e=2586ms, avg_ttft=1243ms)
```
**GPT-4.1-mini TTFT: 750ms–1696ms, avg 1243ms.** This is the ceiling.

### Secondary Problem: AI Verbosity (Multi-Sentence Dead Air)
Even when TTFT was fast, inter-sentence gaps created UX damage:
```
T1: [Ovela Ack]: Right, (TTFT: 1119ms)
    [Ovela]: I can check room availability, take booking requests...
    [Ovela]: What do you need? (inter-sentence: 6616ms)   ← 6.6s dead air
T2: [Ovela]: the base room is the Standard Queen Room at 135 dollars
    [Ovela]: It's best for couples or solo travelers. (inter-sentence: 4340ms)
    [Ovela]: Anything else you'd like to know? (inter-sentence: 2391ms)
```
**A 756ms TTFT still felt slow because Deepgram had to generate + stream 3 sentences.**

### Stage A Applied Fixes (this session, 2026-03-11)
1. **Prompt tightened**: `MAX 1-2 SHORT SENTENCES` → **`MAX 1 SENTENCE per turn`** (strict, one exception for booking data collection).
2. **Claude 3.5 Haiku** upgraded from old `claude-3-haiku-20240307` to `claude-3-5-haiku-20241022` in `handler.py`. Activated via `USE_CLAUDE=true` + `ANTHROPIC_API_KEY`.

---

## 2. Stage B — LLM Swap Experiment

### Hypothesis
GPT-4.1-mini TTFT is avg 1243ms. Claude 3.5 Haiku has published TTFT benchmarks in the 300–600ms range on comparable short prompts (as of 2025). If true, e2e user-to-audio drops from ~2.5s → ~1.0–1.5s — a step-change improvement.

### Models To Compare

| Model | Provider | Key | Env to Activate |
|-------|----------|-----|-----------------|
| `gpt-4.1-mini` | OpenAI | `OPENAI_API_KEY` | Default (no flag needed) |
| `claude-3-5-haiku-20241022` | Anthropic | `ANTHROPIC_API_KEY` | `USE_CLAUDE=true` |

### How To Run the Experiment
1. Set `USE_CLAUDE=false` (default). Run 3–5 test calls. Collect latency logs.
2. Set `USE_CLAUDE=true` + set `ANTHROPIC_API_KEY` in Heroku config vars. Redeploy. Run 3–5 test calls.
3. Compare `stt_to_first_token_ms` across both sets. That's the pure LLM TTFT.

### What to Look For in Logs
```
# Per-turn
⏱️ TURN LATENCY: T1 | SHORT_ANSWER | stt_to_first_token_ms=??? ← this number

# Call summary
⏱️ CALL LATENCY SUMMARY: ... normal(n=X, avg_e2e=???ms, avg_ttft=???ms)
```

**Success threshold**: avg_ttft < 600ms with Claude 3.5 Haiku.

### Risks with Claude in Deepgram Voice Agent
- Function calling format: Anthropic uses `tool_use` / `tool_result` pattern vs OpenAI's `function_calling`. Deepgram Voice Agent API normalises both — but test carefully.
- Temperature: Claude does not expose a temperature field in Deepgram's Voice Agent provider config. Remove temperature from the Claude config block (already done).
- Prompt format: Claude is instruction-tuned differently. The existing system prompt should work but watch for persona drift (over-verbose or off-character responses) in first few test calls.

### Decision Gate
| Outcome | Next Step |
|---------|-----------|
| avg_ttft < 600ms AND function calling reliable | **Issue resolved.** Switch Claude as default. Document final numbers. |
| avg_ttft < 600ms BUT function calling unreliable | Evaluate prompt engineering for Claude; re-test. |
| avg_ttft > 900ms (no improvement) | Return to GPT-4.1-mini. Move to Section 3 (UX ceiling). |
| avg_ttft 600–900ms (moderate improvement) | Evaluate if sentence-level improvements pushed by prompt changes cross the threshold. |

---

## 3. Prompt Tightening Impact (Parallel Experiment)

### What Changed
```diff
- MAX 1-2 SHORT SENTENCES per turn. If more needed, STOP and wait for caller.
+ MAX 1 SENTENCE per turn (strict — not 1-2, ONE). Exception: booking data collection
+ where you add a single follow-up question to keep momentum (e.g. "That's $135/night —
+ what dates?"). Never generate a third sentence.
```

### Expected UX Impact
Even WITHOUT LLM swap this change should fix the **inter-sentence dead-air problem**:
- T1 would become: `"Right, I can check availability, make bookings, answer questions, or connect you to staff."` — ONE sentence, done. No 6.6s `"What do you need?"` dangling at the end.
- T2 would become: `"The base room is the Standard Queen Room at $135/night."` — done, no trailing sentences.

### How to Verify
Look for `(inter-sentence: Xms)` lines in logs. After this change, most turns should produce **zero inter-sentence lines**. If you see more than one inter-sentence line per turn, the prompt rule is being ignored → investigate with explicit temperature reduction.

---

## 4. UX Ceiling Scenario Testing (If Needed After Stage B)

If LLM swap + prompt tightening still leaves avg_ttft > 900ms or specific scenarios feel broken, the issue is a **scenario-level ceiling** — certain combinations of system state, call complexity, or user phrasing that consistently hit bad paths.

### Testing Framework

#### Category A: Standard Flow (baseline pass/fail)
| Scenario | Expected e2e | Tracking |
|----------|-------------|---------|
| "Do you have any rooms available this weekend?" | < 1500ms TTFT, 1 sentence answer | |
| "What's the price for a queen room?" | < 1200ms TTFT, 1 sentence answer | |
| "Can I book for 2 nights starting Saturday?" | < 1500ms TTFT, collects dates | |
| "Is anyone available to talk?" (transfer request) | < 1000ms TTFT, transfer initiated | |
| Short answer ("Yes", "No", "Okay") | < 800ms TTFT | |

#### Category B: Degraded-Input Scenarios (Phone Audio Quality)
| Scenario | Expected Behaviour |
|----------|--------------------|
| Background noise + clear speech | Transcribes correctly, normal TTFT |
| Background noise + unclear speech | Graceful clarification request, no hallucinated answer |
| Caller speaks very slowly | `vad_to_stt_ms` high (expected), TTFT normal |
| Mixed languages / accents | Correct STT (nova-2 is robust), TTFT normal |
| Caller cuts off mid-sentence | Deepgram completes turn on endpointing timer, AI responds to partial input sensibly |

#### Category C: Conversational Edge Cases
| Scenario | Expected Behaviour |
|----------|--------------------|
| "Give me a second" / "Hold on" | Wait mode activates within 2s (LLM call OR deterministic fallback) |
| Caller silent for 10s | Soft silence prompt fires, no dead air beyond 10s |
| Caller asks about non-motel topic | Polite redirect, no hallucinated answer |
| Repeated misunderstanding (3 turns) | Still polite, no robotic repetition, offers staff transfer |
| "Book me a room" with no dates | AI collects dates step-by-step, <= 2 turns to collect all info |
| Very long booking request (all data at once) | Correctly parses dates/names/contact, no double-asking |

#### Category D: Tool-Call Scenarios (Function Calling Reliability)
| Scenario | Expected | Key Metrics |
|----------|----------|-------------|
| `check_availability` (dates given) | filler fires within 300ms, result < 4s | `func_exec_ms` < 3000ms |
| `create_booking_request` | Confirmation message clear, no hallucinated booking number | turn type = `tool_call` |
| `get_room_pricing` | Correct price returned, no extra sentences | 1 sentence answer |
| `request_human_callback` | Callback queued, SMS sent to staff, AI confirms calmly | |
| `end_call` / `transfer_to_staff` | Correct function fired, not confused with each other | |

#### Category E: Duration & Stress
| Scenario | Expected Behaviour |
|----------|-------------------|
| 3-minute call (hits soft cap) | Transparent handoff to staff initiated |
| Multiple tool calls in sequence | Each turn's latency independent, no accumulation |
| Function execution timeout (PMS slow) | Graceful error message, not silent hang |
| Deepgram reconnect mid-call | Handler recovers or degrades gracefully |

### How to Run This Testing
1. Use `backend/scripts/test_coalcreek_reliability.py` as the fixture runner.
2. Add each scenario as a named test case with an expected latency budget.
3. Run 3x per scenario to smooth variance.
4. Collect all `⏱️ TURN LATENCY` lines; compute avg and p95.
5. Flag any scenario where p95 `total_user_to_audio_ms` > 2500ms as a UX issue.

### Success Criteria for Consistent UX
| Metric | Target |
|--------|--------|
| avg `stt_to_first_token_ms` (all models) | < 700ms |
| p95 `total_user_to_audio_ms` (short turns) | < 2000ms |
| p95 `total_user_to_audio_ms` (tool calls) | < 4000ms |
| Inter-sentence appearance rate | < 10% of turns |
| Function calling accuracy | > 98% on Category D |
| Wait-mode activation rate on hold phrases | 100% (LLM OR deterministic fallback) |

---

## 5. Deployment Checklist (Current State)

### Active Model: gpt-4.1-nano
```json
// Set in Appwrite voice_settings for coalcreek tenant:
{ "llm_model": "gpt-4.1-nano" }
```
No Heroku config var changes needed. Model inferred as `open_ai` provider automatically.

### To Test gpt-5.2-instant
```json
{ "llm_model": "gpt-5.2-instant" }
```
Verified accepted by Deepgram. Test 3–5 calls, compare avg_ttft vs 732ms baseline.

### To Revert to gpt-4.1-mini Baseline
```json
{ "llm_model": "gpt-4.1-mini" }
```

### Deploy Current Fixes
```bash
git add backend/services/voice_agent/handler.py \
        backend/services/voice_agent/config.py \
        backend/services/voice_agent/prompts_coalcreek.py
git commit -m "fix: double filler guard, demo time cap 8min, tighter 1-sentence rule"
git push heroku personal/assistant:main
```

---

## 6. Path to Consistent ~600ms TTFT

### Where We Are
- **Current best avg TTFT: 732ms** (gpt-4.1-nano, normal turns)
- **Fastest observed: 606ms** (short turns)
- **Gap to target: ~130ms median, ~100ms for fastest turns**

The remaining gap is not in TTS (0–17ms, done) or STT (post-endpointing fix, fast). It is in the **Deepgram → LLM first-token pipeline**, which has two components:
1. Deepgram's internal routing delay (transcript → LLM API call)
2. LLM TTFT on the managed side

### Lever 1: Try gpt-5.2-instant (immediate, no code change)
Confirmed Deepgram-managed. Set in DB, run 5 test calls. Log the avg TTFT.
Expected: OpenAI's "instant" tier is optimized for first-token speed.

### Lever 2: Reduce system prompt token count (code change, ~1 hour)
Each LLM call carries the full system prompt in context. Current estimate ~1800 tokens.
Trimming to <1200 tokens saves ~100–200ms on LLM TTFT.
**How:** Audit the prompt for redundant rules, verbose examples, duplicated instructions.
Target: Remove ≥400 tokens while keeping all behaviour rules intact.

### Lever 3: Endpointing tuning (test, no code change)
Current: `endpointing: 300` (300ms silence = turn end).
Could try `endpointing: 200` — saves 100ms per turn finalization.
Risk: More premature cut-offs on natural speech pauses.
**Only worth it if Lever 1+2 aren't enough and noisy-call stability is confirmed unaffected.**

### Lever 4: Gemini 2.5 Flash (when transcript bug is diagnosed)
Deepgram managed. Sub-700ms TTFT expected.
Before using: confirm whether the truncated ConversationText is a Deepgram logging artifact (caller hears full sentence) or a real generation bug (caller hears "at?" as the full response).
**Test:** Enable gemini-2.5-flash, run a call, listen carefully to audio vs logs.

### What Will NOT Help Further
- Switching to BYO LLM endpoints — adds ~300–400ms of HTTP hop latency
- Cartesia optimization — already at 0–17ms, done
- Nova-2 STT tuning — endpointing is working, VAD includes speech time (expected)
- Multi-model UpdateThink swapping — swap overhead erases any ack gain

### Decision Gate
| avg TTFT after Levers 1+2 | Decision |
|--------------------------|---------|
| < 600ms | ✅ Target reached. Ship. |
| 600–700ms | ✅ Acceptable. Ship with Lever 3 as optional follow-up. |
| 700–900ms | Diagnose Gemini truncation bug; try Gemini 2.5 Flash. |
| > 900ms (regression) | Revert to gpt-4.1-mini baseline. |
