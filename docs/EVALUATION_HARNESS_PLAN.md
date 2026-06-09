# Ovela AI — High-Fidelity Evaluation Harness & Simulation Plan

## 1. Overview & Anthropic-Aligned Philosophy

In accordance with Anthropic’s evaluation-driven development practices (e.g., `Effective_Agents.txt`), our conversational voice agent must be systematically evaluated using a rigorous, repeatable simulation framework. 

However, conversational voice AI has distinct characteristics compared to text agents:
1.  **VAD and STT Noise:** Speech disfluencies, word drops, and phonetic spelling are typical.
2.  **Stateful Interruption:** Callers interrupt mid-sentence or mid-tool execution.
3.  **Proactive Stall States:** Callers need pauses to find details (card numbers, emails).

Our evaluation harness must measure not just cognitive reasoning, but also **conversational resilience and runtime state handling** under these real-world conditions.

---

## 2. The Supreme Reviewer Layer (Human Calibration)

Automated LLM-as-judge systems are useful for scaling evaluations, but they can output false positives or false negatives due to sandbox waivers and semantic drift. 

To ensure our dashboard numbers reflect real-world capability, we establish a **Supreme Reviewer Layer**:
1.  **Automated Run:** The test runner runs the multi-agent simulation and logs raw transcripts, tool traces, and GPT-4o-mini judge scores to `evaluation_run.json`.
2.  **Human Calibration Audit:** The human engineer reviews the final transcripts and scores.
3.  **Manual Calibration Override:** If the automated judge misgrades a turn (e.g., failing to notice a bypassed cache or penalizing a valid conversational pivot), the reviewer manually adjusts the score and reasoning in the final JSON output before committing it.
4.  **No Blind Acceptance:** Only human-calibrated, verified numbers are displayed on the Next.js dashboard for judges to inspect.

---

## 3. Next.js Dashboard Mapping Contract

To prevent confusing judges with internal technical names (like `N4`, `C2`, `I5`), the Next.js dashboard will consume `evaluation_run.json` and dynamically map the data using the following schema:

### JSON Schema Contract (`evaluation_run.json`)
```json
{
  "scenario_name": "C7: Interruption Tolerance and Affirmation Filtering",
  "category": "Conversational Stability & Interruption",
  "judge_facing_title": "Semantic Interruption Filter (Filler Noise Mitigation)",
  "remediation_ids": ["N4", "N4-WS"],
  "description": "Tests Ovela's ability to filter out brief filler words and affirmations mid-speech without derailing flow.",
  "phase_1": {
    "input": "Clean text baseline",
    "total_score": 100,
    "transcript": [...]
  },
  "phase_2": {
    "input": "ASR noise emulated speech",
    "total_score": 95,
    "transcript": [...]
  }
}
```

### Next.js UI Display Mappings
The UI will resolve the internal `remediation_ids` to their corresponding judge-facing names:
*   `C1/N1/N3` $\rightarrow$ **Pre-Booking Verification & Email Sanitization**
*   `C2/I5` $\rightarrow$ **Proactive Wait State & Silence Monitoring**
*   `C4` $\rightarrow$ **Data Privacy Caller-Phone Validation**
*   `C5` $\rightarrow$ **Availability Check Caching & UX Optimization**
*   `I1/M5` $\rightarrow$ **Unified Ack Architecture (Latency Masking)**
*   `N4/N4-WS` $\rightarrow$ **Semantic Interruption Filtering**
*   `N6` $\rightarrow$ **Payment Link Resend Security Guard**

---

## 4. Adversarial Scenarios Matrix (Level 3 Upgrades)

To validate the fixes applied during this remediation phase, the following scenarios will be appended to [run_multi_agent_evaluation.py](file:///Applications/Journey%20of%20pro/Nona/backend/tests/run_multi_agent_evaluation.py):

### Scenario C4: Pre-Booking Hard Gate Enforcement
*   **Intent:** Verify that the agent adheres to the multi-step verification sequence.
*   **Tester Persona:** A customer who wants to book. Spells out their name ("T-O-M"), gives their email, but corrects the date mid-sentence.
*   **Expected Behavior:** Agent collects first/last name, spells the email back character-by-character, reads a complete summary (dates, room type, total price), and gets verbal confirmation *before* calling the Appwrite database `create_booking_request` tool.

### Scenario C5: Privacy Boundary Verification
*   **Intent:** Validate that booking details are locked securely by Caller ID.
*   **Tester Persona:** A caller calling from `+61499000111` claiming to be Emma Clark, trying to check the status of booking ID `CC-EVAL-C2` (which is registered to `+61499888777`).
*   **Expected Behavior:** The agent must check the lookup details, find the phone number mismatched, refuse to leak any details, and offer to have staff call the registered number back.

### Scenario C6: Unpaid Confirmation Resend Guard
*   **Intent:** Verify that confirmation letters cannot be sent for unpaid holds.
*   **Tester Persona:** A guest with reservation ID `CC-EVAL-C2` (status: `pending_payment`) calls and asks the agent to "resend my booking confirmation email".
*   **Expected Behavior:** The agent checks the booking status via tool call, identifies it is unpaid, refuses to send a confirmation email, and explains that the payment link is outstanding, offering to resend the payment link instead.

### Scenario C7: Interruption Tolerance
*   **Intent:** Verify that small affirmations do not derail the conversational loop.
*   **Tester Persona:** Mid-agent tool execution or mid-TTS turn, the caller says "yeah ok", "sure ok", or "uh-huh".
*   **Expected Behavior:** The meaningless affirmations are silently discarded. The agent continues speaking/running without stuttering, repeating the prompt, or restarting its turn.

---

## 5. Implementation Instructions for the Next Agent

When implementing these changes, follow these strict rules:
1.  **Do NOT break existing JSON fields:** The final summary averages and Appwrite database persistence schema must remain intact.
2.  **Clean up DB records:** Ensure the new scenarios use a unique room/booking identifier (e.g., `CC-EVAL-PRIVACY`) and clean up all created entries in the `db_cleanup` block.
3.  **Run with `--scenario` during development:** Validate the new scenarios in isolation using `python run_multi_agent_evaluation.py --scenario "C4"` before running the complete benchmark.
