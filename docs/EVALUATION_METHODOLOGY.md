# Ovela AI — Evaluation Methodology & System Card

This system card provides a comprehensive overview of Ovela AI's evaluation framework, benchmark rubrics, simulation environment parameters, and the methodology used to calculate our performance metrics.

By subjecting the agent to adversarial, edge-case heavy scenarios across three cognitive difficulty levels, we ensure production-grade stability in live telephony environments.

---

## 🏆 Executive Summary: Audited Benchmark Results

Ovela AI is continuously evaluated against **14 adversarial guest scenarios** spanning Booking Lifecycle, Privacy Governance, Fault Tolerance, and Conversational Stability. Results are graded by an independent LLM judge on a strict 100-point rubric and persisted to the live Appwrite evaluation dashboard for verifiability.

* **Phase 1 (Deterministic Text Baseline):** **91.4 / 100** Average Score (14 scenarios)
* **Phase 2 (ASR Voice Emulation):** Enabled — measures voice realism resistance (noise-induced score delta per scenario)
* **Evaluation Engine:** Full ADK graph (OvelaManager → BookingWorker / InfoWorker) on **Gemini 2.5 Flash** via Vertex AI ADC — not a flat prompt baseline.

<div align="center">
  <br />
  <a href="https://ovela.dev/evaluations" target="_blank">
    <img src="../images/eval_dashboard.png" alt="Live Evaluation Dashboard UI" width="100%" />
  </a>
  <br />
  <strong><a href="https://ovela.dev/evaluations" target="_blank">🔗 Access the Live Evaluation Dashboard (ovela.dev/evaluations)</a></strong>
</div>

---

## 🔄 The Two-Phase Testing Pipeline

To guarantee reliability before deploying to live telephony, every scenario is executed through a rigorous two-phase pipeline:

### Phase 1: Deterministic Text Simulation
The agent is prompted with clean, grammatically correct text inputs. This establishes Ovela's baseline cognitive ability to reason, execute ADK tool calls, retrieve property data, and route complex intents correctly.

### Phase 2: ASR Noise Simulator (Real-World Emulation)
To simulate a real phone call with background noise, latency, or thick accents, the test harness routes inputs through a deterministic **ASR Noise Simulator** ([`asr_noise_simulator.py`](../backend/tests/asr_noise_simulator.py)). This applies:
- **Phonetic Swaps:** (e.g., "twin room" → "twin kind of room", "queen" → "green").
- **Speech Disfluencies:** Inserting filler words ("uh", "um", "like", "sort of").
- **Acoustic Distortions:** Simulating dropped packets and word omissions.

*This phase verifies Ovela's accent resilience and phonetic clarification logic, ensuring that a bad connection doesn't result in a dropped booking.*

---

## 🧪 Scenario Matrix (14 Scenarios)

Ovela AI is tested across three cognitive difficulty levels simulating real-world hospitality edge cases:

| Scenario | Cognitive Level | Category | Description |
|----------|-----------------|----------|-------------|
| **A1: Happy Path** | Level 1 | Booking Lifecycle | Availability check + Hold + Booking capture + Stripe email |
| **A2: FAQ Pivot** | Level 1 | Conversational Stability | Interrupting a booking flow with policy questions |
| **A3: No Availability** | Level 1 | Booking Lifecycle | Graceful empathic alternatives when sold out |
| **B1: Date Correction** | Level 2 | Conversational Stability | Customer corrects dates mid-sentence without losing intent |
| **B2: Missing Email** | Level 2 | Booking Lifecycle | Extraction recovery loop on missing required entity |
| **B3: Tool Retry** | Level 2 | Fault Tolerance | Graceful structured options after vague user request |
| **B4: Abrupt Hang-up** | Level 2 | Conversational Stability | Safe session termination mid-booking with end_call tool |
| **C1: Last Room Race** | Level 3 | Booking Lifecycle | Urgent real-time hold under booking pressure |
| **C2: Payment Status** | Level 3 | Data Governance | Secure booking lookup for return caller with pending payment |
| **C3: Backend Failure** | Level 3 | Fault Tolerance | Graceful human handoff under website failure frustration |
| **C4: Pre-Booking Gate** | Level 3 | Booking Lifecycle | Strict phonetic email confirmation + summary gate before DB write |
| **C5: Privacy Boundary** | Level 3 | Data Governance | Caller-phone-locked data access — refuses unmatched number lookup |
| **C6: Unpaid Resend Guard** | Level 3 | Data Governance | Blocks confirmation email for unpaid hold; resends payment link |
| **C7: Interruption Tolerance** | Level 3 | Conversational Stability | Semantic filler filtering without derailing booking flow |

> **Source:** [`backend/tests/evaluation_run.json`](../backend/tests/evaluation_run.json) — full transcript traces and per-scenario scores.

---

## 👨‍⚖️ Scoring Rubric

Conversations are logged as transcript traces and graded by an independent GPT-4o-mini Judge on a strict 100-point rubric:

1. **Tool Invocation Accuracy (30 Points):** Correct execution of ADK tools with matching dates/types/schemas.
2. **Conversational Stability (25 Points):** Context retention and avoidance of repetition or circular loops.
3. **Markdown & Telephony Bleed (20 Points):** 100% natural voice outputs free of markdown annotations.
4. **Interruption & Pivot Grace (15 Points):** Handling mid-response customer interruptions and intent shifts.
5. **Gate Compliance & Privacy Governance (10 Points):** Pre-booking gate enforcement and caller-phone privacy lock.

---

## ⚠️ Deterministic Sandbox Parameters

In an isolated testing sandbox, certain live production capabilities (like processing real credit cards) cannot be executed. The evaluation harness applies the following scoring waivers:

| Sandbox Constraint | Simulation Reality | Scoring Adjustment |
|--------------------|--------------------|--------------------|
| **Stripe Checkout** | Sandbox environment does not process live credit cards. | If the agent generates and confirms the Stripe payment link via email, it receives a **perfect score**. |
| **Fully Booked Rooms** | If the PMS database reports a room is sold out, the agent cannot complete the booking. | The agent is graded on *accurately reporting the sold-out status and suggesting alternatives*, rather than forcing a booking. |
| **No-Fault Success** | On a successful, error-free run, no backend errors occur to "recover" from. | The judge awards the full **10/10 points** for Fault Recovery (instead of penalizing for the lack of errors). |
| **Telephony Hang-ups** | In a real call, the guest hanging up closes the stream. In simulation, trailing script turns are logged. | Truncated responses or trailing simulation artifacts are **waived** if the customer already initiated the hang-up. |

---

## 🔗 Harness Source Files

| File | Purpose |
|------|---------|
| [`run_multi_agent_evaluation.py`](../backend/tests/run_multi_agent_evaluation.py) | Full 14-scenario harness. Exercises real ADK graph on Vertex AI ADC. |
| [`asr_noise_simulator.py`](../backend/tests/asr_noise_simulator.py) | Deterministic ASR noise emulator (light / medium / heavy). |
| [`evaluation_run.json`](../backend/tests/evaluation_run.json) | Last persisted run. Full transcripts + LLM judge scores. |

---
*Evaluated on Google Gemini Enterprise ADK — Gemini 2.5 Flash via Vertex AI Application Default Credentials.*
