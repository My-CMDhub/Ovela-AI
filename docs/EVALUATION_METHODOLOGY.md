# Ovela AI — Evaluation Methodology & System Card

This system card provides a comprehensive overview of Ovela AI's evaluation framework, benchmark rubrics, simulation environment parameters, and the methodology used to calculate our fortified performance metrics. 

By subjecting the agent to adversarial, edge-case heavy scenarios, we ensure production-grade stability in live telephony environments.

---

## 🏆 Executive Summary: Fortified Benchmark Results

Ovela AI is continuously evaluated against 10 adversarial guest scenarios. By adjusting automated scoring for sandbox constraints (see Simulation Parameters below), the system achieves the following baseline metrics:

* **Phase 1 (Deterministic Text Baseline):** **98.5%** Average Pass Rate
* **Phase 2 (ASR Voice Emulation):** **99.5%** Average Pass Rate
* **Voice Realism Resistance:** **100%** (Zero degradation under simulated noise, proving the success of our phonetic clarification gate and domain keyterm boosting).

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
To simulate a real phone call with background noise, latency, or thick accents, the test harness routes inputs through a deterministic **ASR Noise Simulator**. This applies:
- **Phonetic Swaps:** (e.g., "twin room" → "twin kind of room", "queen" → "green").
- **Speech Disfluencies:** Inserting filler words ("uh", "um", "like", "sort of").
- **Acoustic Distortions:** Simulating dropped packets and word omissions.

*This phase verifies Ovela's accent resilience and phonetic clarification logic, ensuring that a bad connection doesn't result in a dropped booking.*

---

## 🧪 Scenario Matrix

Ovela AI is tested across three cognitive difficulty levels simulating real-world hospitality edge cases:

| Scenario | Cognitive Level | Phase 1 (Clean Text) | Phase 2 (ASR Noisy Voice) | Description |
|----------|-----------------|----------------------|---------------------------|-------------|
| **A1: Happy Path** | Level 1 | 100 / 100 | 100 / 100 | Availability check + Hold + Booking capture |
| **A2: FAQ Pivot** | Level 1 | 100 / 100 | 100 / 100 | Interrupting a booking flow with policy questions |
| **A3: No Availability**| Level 1 | 100 / 100 | 100 / 100 | Graceful alternative suggestions when sold out |
| **B1: Date Correction**| Level 2 | 100 / 100 | 100 / 100 | Customer changes dates mid-booking flow |
| **B2: Missing Email** | Level 2 | 100 / 100 | 100 / 100 | Extraction recovery loop on invalid contact info |
| **B3: Tool Retry** | Level 2 | 100 / 100 | 100 / 100 | Graceful retry after ambiguous user input |
| **B4: Abrupt Hang-up** | Level 2 | 95 / 100 | 100 / 100 | Call termination mid-booking without data corruption |
| **C1: Last Room Race** | Level 3 | 95 / 100 | 95 / 100 | Handling a race condition (room booked by another user during call) |
| **C2: Payment Status** | Level 3 | 100 / 100 | 100 / 100 | Secure lookup and status validation by return caller |
| **C3: Backend Failure**| Level 3 | 95 / 100 | 100 / 100 | Graceful human handoff under simulated API timeouts |

---

## 👨‍⚖️ Scoring Rubric

Conversations are logged as transcript traces and graded by an independent LLM Judge on a strict 100-point rubric:

1. **Tool Invocation Accuracy (30 Points):** Correct execution of ADK tools with matching dates/types.
2. **Conversational Stability (25 Points):** Context retention and avoidance of repetition or circular loops.
3. **Markdown & Telephony Bleed (20 Points):** 100% natural conversational voice outputs free of markdown annotations (asterisks, hashes, lists).
4. **Interruption & Pivot Grace (15 Points):** Handling mid-response customer interruptions and shifts in intent.
5. **Fault Recovery (10 Points):** Polite handling of database lags, sold-out rooms, or API timeouts.

---

## ⚠️ Deterministic Sandbox Parameters

In an isolated testing sandbox, certain live production capabilities (like processing real credit cards) cannot be executed. To maintain objective fairness and rigor, the evaluation harness applies the following scoring parameters:

| Sandbox Constraint | Simulation Reality | Scoring Adjustment |
|--------------------|--------------------|--------------------|
| **Stripe Checkout** | Sandbox environment does not process live credit cards. | If the agent generates and confirms the Stripe payment link via email, it receives a **perfect score**. |
| **Fully Booked Rooms**| If the PMS database reports a room is sold out, the agent cannot complete the booking. | The agent is graded on *accurately reporting the sold-out status and suggesting alternatives*, rather than forcing a booking. |
| **No-Fault Success** | On a successful, error-free run, no backend errors occur to "recover" from. | The judge awards the full **10/10 points** for Fault Recovery (instead of penalizing the agent for the lack of errors). |
| **Telephony Hang-ups**| In a real call, the guest hanging up closes the stream. In simulation, trailing script turns are logged. | Truncated responses or trailing simulation artifacts are **waived** if the customer already initiated the hang-up. |

---
*Evaluated on Google Gemini Enterprise ADK.*
