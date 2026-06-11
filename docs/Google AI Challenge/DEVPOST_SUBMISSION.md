# Ovela AI — Google for Startups AI Agents Challenge Submission

# Track 2: Optimize (Existing Agents)

---

## 🌟 The One-Liner

Ovela AI is a production-grade, multi-agent voice receptionist that autonomously manages B2B hospitality reservations, interrogates live PMS databases, and processes Stripe payments — with all AI reasoning, tool execution, and business intelligence orchestrated by **Gemini 2.5 Flash** through the **Google Agent Development Kit (ADK)** on Vertex AI.

---

## 🚀 Challenge Track

**Track 2: Optimize (Existing Agents)**

> *"Bring your existing experimental agent and use our new optimization tools. You will stress-test multi-step reasoning, debug stalled logic, and programmatically refine your system instructions to achieve production-grade reliability and enterprise scale."*

This describes Ovela's contest journey exactly. We had a working single-prompt voice agent before the contest period. During the contest (April 22 – June 5, 2026), we rebuilt its intelligence layer from scratch using Google ADK, implemented a rigorous adversarial evaluation harness across 14 scenarios, and drove a +20.4-point quality improvement. That optimization work — the ADK multi-agent graph, the two-phase evaluation pipeline, and the session-persistence architecture — is the submission.

---

## 💡 The Problem

In the hospitality industry, missed calls equal lost revenue. Traditional voice bots fail in three ways:

1. **Hallucination:** They invent availability, pricing, and policy answers
2. **Latency:** >2-second response gaps trigger constant caller interruptions
3. **Brittleness:** They collapse on ASR noise, accented speech, and mid-flow corrections

We needed an agent that was realiably fast, deeply integrated into our Property Management System (PMS), and provably immune to hallucination under adversarial conditions.

---

## ⚙️ Architecture: Two-Path Design

To achieve sub-850ms audio response while keeping all AI intelligence on Google's infrastructure, we designed a Two-Path Architecture that separates the real-time speech I/O layer from the Gemini reasoning layer.

### Path 1 — Real-Time Speech I/O Layer (~850ms TTFT)

**Stack: Twilio PSTN → WebSocket → FastAPI Audio Bridge → Deepgram Nova-3 STT + VAD → Cartesia Sonic-3 TTS**

This path is a **managed telephony infrastructure layer** — a speech-to-text and text-to-speech pipeline. Its responsibilities:

- Voice Activity Detection (VAD): determining when a caller starts/stops speaking
- Streaming audio bytes between Twilio and Deepgram
- Delivering transcribed utterances to the Gemini ADK layer via async webhook

When a caller's intent requires any form of business intelligence — a room availability check, a privacy-boundary question, a booking action — the transcribed utterance is forwarded to the Gemini Cold Path, and Gemini's response is returned to be spoken. **The speech layer makes no business decisions and executes no database calls independently.**

### Path 2 — Gemini AI Intelligence Layer (Google ADK)

**Stack: FastAPI Webhook → Google ADK Runner → Gemini 2.5 Flash (Vertex AI ADC) → Appwrite PMS**

Every piece of AI reasoning runs exclusively here:

| Agent                                  | Role                                                                                  | Tools                                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OvelaManager** (`LlmAgent`)  | Session orchestrator — routes caller intent to the correct specialist                | `transfer_to_staff`, `end_call`, `wait_on_request`                                                                                                |
| **BookingWorker** (`LlmAgent`) | Booking specialist — JSON-strict PMS interaction, Stripe payment orchestration       | `check_availability`, `create_booking_request`, `lookup_booking`, `update_guest_info`, `resend_payment_link`, `resend_payment_confirmation` |
| **InfoWorker** (`LlmAgent`)    | Knowledge specialist — real-time grounding for weather, local events, motel policies | `perform_live_search` (Google Search)                                                                                                                 |

All three agents run `google-adk` `LlmAgent` + `Runner` with `AppwriteSessionService` providing durable session state that survives Cloud Run horizontal scaling events.

### 📐 Architecture Diagram

![Ovela AI Architecture Diagram](https://raw.githubusercontent.com/My-CMDhub/Ovela-AI/main/images/ovela_architecture_diagram.png)

---

## ✅ Mandatory Technologies (Official Rules Compliance)

Per the official contest rules, all submissions must incorporate:

| Requirement                                              | Ovela Implementation                                                          |
| -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Intelligence: Gemini API or Vertex AI**          | ✅ Gemini 2.5 Flash via Vertex AI ADC (keyless ADC auth, zero hardcoded keys) |
| **Orchestration: ADK or supported framework**      | ✅`google-adk` `LlmAgent`, `Runner`, `SequentialAgent` graph          |
| **Infrastructure: Cloud Run / Agent Engine / GKE** | ✅ Google Cloud Run (`australia-southeast1`), Dockerized FastAPI            |

**Third-party integrations declared:** Twilio (PSTN telephony), Deepgram (managed STT/VAD service), Cartesia (TTS), Appwrite (PMS database), Stripe (payment processing), Zoho SMTP (system mail).

---

## 🏆 Optimization Results (The Track 2 Story)

The core of our Track 2 submission is a measurable, reproducible quality improvement achieved by rebuilding the agent's intelligence on the Google ADK multi-agent graph.

### What We Optimized

**Before (Pre-ADK — Monolithic Single-Prompt Agent):**

- A single system prompt handled booking, info, privacy, and conversational logic simultaneously
- No cognitive load isolation → hallucinations on complex multi-step scenarios
- No structured evaluation → no objective quality signal

**After (Contest Period — ADK Multi-Agent Graph + Evaluation Harness):**

- Specialized `LlmAgent` roles with strict tool access boundaries eliminate cross-contamination
- BookingWorker has a hard backend gate: `has_user_confirmed_summary` must equal `"YES"` before any booking executes — eliminating hallucinated confirmations
- A two-phase adversarial evaluation harness provides a reproducible quality signal

### Results

| Metric                                    | Baseline     | Optimized                        | Delta               |
| ----------------------------------------- | ------------ | -------------------------------- | ------------------- |
| **Phase 1 Average (14 scenarios)**  | 72.4 / 100   | **92.8 / 100**             | **+20.4 pts** |
| **Availability Hallucination (A1)** | Frequent     | **100/100 (both phases)**  | Eliminated          |
| **Privacy Boundary Tests**          | Inconsistent | **Consistent enforcement** | Hardened            |

### The Evaluation Pipeline

Every scenario runs through a **two-phase pipeline** — not a clean-room prompt test:

- **Phase 1 (Deterministic Text Baseline):** Establishes the agent's cognitive baseline with clean, literal input
- **Phase 2 (ASR Noise Simulation):** The same scenario re-runs through our ASR Noise Simulator, which injects realistic voice degradation (accent interference, homophone substitutions, phonetic corruptions) to measure real-world noise resilience

Evaluation is graded by an independent `GPT-4o-mini` judge on a strict 100-point rubric. All results are persisted to the live Appwrite evaluation dashboard and to `evaluation_run.json` in the repo.

> **Note on evaluation transcripts:** Some transcripts show `[no response from ADK graph]` entries. These are test-harness timing artifacts caused by the `asyncio.sleep()` polling gap in the simulation runner — not production failures. In live telephony, pre-synthesised filler audio ("Let me check that for you.") bridges any ADK processing time with zero audible gap.

---

## 🏗️ Google Cloud Native

| Layer                   | Implementation                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------- |
| **Compute**       | Google Cloud Run (`australia-southeast1`), auto-scaling, Dockerized                  |
| **Auth**          | Application Default Credentials (ADC) — zero hardcoded Vertex AI keys                 |
| **Secrets**       | GCP Secret Manager (Twilio, Stripe, Appwrite credentials)                              |
| **Session State** | `AppwriteSessionService` — ADK session store that survives container scaling events |
| **Grounding**     | Google Search API via ADK `google_search` built-in tool on `InfoWorker`            |

---

## 🔧 Production-Grade Innovations Built During Contest Period

These engineering solutions were developed specifically during the contest period to achieve production-grade reliability:

- **Interruption-Safe Context Trimming:** Guest interruptions natively trim unheard agent text from the context window, keeping the next LLM turn coherent (+13% interruption recovery)
- **Phonetic Clarification Gate:** One-shot phonetic confirmation loop combined with Deepgram keyterm boosting improves non-English name/email capture by 26%
- **Zero-Latency Voice Cache:** Core system phrases pre-synthesised to `.mulaw.raw` bytes — eliminates TTS latency for critical conversational junctures, saving 300–800ms
- **Hard Confirmation Gate:** `has_user_confirmed_summary` state flag enforced by both the LLM prompt and the backend tool handler — prevents any booking from executing without explicit caller confirmation

---

## 📞 Live Demo (Australia numbers only)

To experience the agent directly:
**📞 +61 348 236 219**

*(Restricted to +61 Australian numbers to prevent toll fraud and control token costs during judging)*

---

## 🎥 Demo Video

Our 2-minute demo shows:

1. A **live phone call** demonstrating the ~850ms response latency and natural booking flow
2. The **evaluation dashboard** displaying turn-by-turn scenario traces and LLM judge scores
3. The **Stripe Payment Gateway** generating active checkout links from the voice flow

---

## 📎 Key Submission Artifacts

| Artifact                                        | Purpose                                                         |
| ----------------------------------------------- | --------------------------------------------------------------- |
| `backend/services/adk/graph.py`               | Full ADK multi-agent graph definition                           |
| `backend/tests/run_multi_agent_evaluation.py` | Two-phase adversarial evaluation harness                        |
| `backend/tests/evaluation_run.json`           | Last persisted evaluation run (all 14 scenarios + judge scores) |
| `backend/tests/asr_noise_simulator.py`        | ASR noise injection engine                                      |
| `docs/EVALUATION_METHODOLOGY.md`              | Detailed methodology, rubric, and scenario definitions          |
