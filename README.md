<div align="center">
  <img src="images/banner.png" alt="Ovela AI Banner" width="100%" />

  <br />

  **A live voice AI receptionist that answers a real phone number — decoupled, instrumented, and measured turn by turn.**

  <br />

  [![Voice turn](https://img.shields.io/badge/median%20voice%20turn-790ms-success.svg?style=flat-square)](#measured-latency)
  [![Sentry](https://img.shields.io/badge/traced%20with-Sentry-purple?style=flat-square)](#how-the-latency-was-found)
  [![Gemini](https://img.shields.io/badge/diagnosed%20by-Gemini%202.5%20Flash-blue.svg?style=flat-square)](#ai-assisted-diagnosis)
  [![Deployed](https://img.shields.io/badge/deployed-Heroku-79589F?style=flat-square)](#running-it)
</div>

<br />

Call the number and a language model answers. It checks real availability, takes
bookings, transfers you to a human when you ask, and hangs up when you say
goodbye. It has to feel like a phone call — which means it has to be fast, and
it has to let you interrupt it.

It used to run on a vendor's all-in-one voice Agent API: speech in, speech out,
their orchestration. That worked, and it could not be made faster, because every
millisecond that mattered was inside someone else's box. So the pipeline was
taken apart into stages we own and can time individually.

Then it broke in ways that never raised an exception. Fixing those is what this
repository is currently about.

---

## Bug Smash 2026 — what changed

Six stacked pull requests against the pipeline as it stood in `cf99094`.
The diagnostic tooling described further down is deliberately kept out of
them, in its own commit:

| PR | What it fixes | Effect |
|---|---|---|
| **1 — Provider bridges** | Four provider errors, each parsed and dropped by an `if`/`elif` chain with no `else`; plus a `finally` that ran on every `break` | 25s of silence and zero synthesised audio, resolved; the socket stops declaring itself dead after turn one |
| **2 — Stop the agent interrupting itself** | Barge-in armed before any agent audio existed, so the agent cancelled its own replies; chunks from an abandoned turn spoken by the next one | The agent stops talking over itself, and stops finishing a sentence the caller already interrupted |
| **3 — Turn loop into the orchestrator** | Not a bug fix. A design change, labelled as one: the turn moves out of a graph built for background work. `voice_settings` were never read on this path and load with it | The turn can be timed and interrupted; the ADK graph keeps the cold path |
| **4 — Control flow + cold start** | Tool results carrying an `action` field that nothing consumed; a first-call cold start of 4,316ms | Calls now end and transfer for real; cold start 4,316ms → 12ms on the first call |
| **5 — Repair the telemetry** | A span that measured 0.01ms because it was opened and closed on the same line; a stage holding 84% of a turn with no internal detail; then the CallSid as a Sentry conversation id | Latency can be attributed to the stage that causes it, and one call reads as one conversation |
| **6 — Stop paying for work already done** | A volatile header at the front of the prompt, so the cache prefix changed every turn; the same booking queried 8× per call | ~98% of the prompt now served from cache; 3 of 7 booking queries per call stop executing entirely, total query wait 11,049ms → 4,496ms |

The full write-up, with before/after traces, is in the accompanying DEV post.

---

## Measured latency

Measured on live PSTN calls, read from Sentry. The headline figure is the
larger and more conservative of the two samples taken:

| | |
|---|---|
| **Median turn** (caller stops speaking → first audio back) | **790 ms** (28 consecutive turns) |
| Median over an earlier 10-turn sample | 688 ms |
| Best turn | 400 ms |
| Worst conversational turn | 1,541 ms |

Where the time goes, from one analyser run over 20 consecutive turns
(`benchmarks/trace_analysis.json`, medians, sample size per row):

```
whole turn                              952 ms   n=19
  Span 1  speech ended -> first token   838 ms   n=20   (88%)
    LLM round 1  -> first token         434 ms   n=20
    LLM round 2  (tool turns only)      406 ms   n=10
    tool: lookup_booking                505 ms   n=4
    tool: check_availability            506 ms   n=3
    tool: perform_live_search         2,127 ms   n=2    <- largest remaining cost
  Span 3  first token -> first audio    158 ms   n=20
```

That 952 ms median is higher than the 790 ms above because this window mixes
conversational turns with tool-calling ones. Both numbers are real; they count
different populations, and the conservative one is quoted whenever a single
figure is given.

**Two regimes.** Turns with no tool call land at 400-890 ms in the 28-turn
sample, with a tail to 1,541 ms. Turns that call a tool add the tool's own cost
on top; `perform_live_search` — a live web lookup — is the dominant one at
~2.1 s, on only two samples.

The model's own time-to-first-token varies between 574 ms and 1,861 ms on
byte-identical input, so that share is largely not ours to reclaim. Everything on our side of the line — setup,
caching, model selection, synthesis, streaming to Twilio — has been driven down
and is timed per stage.

---

## Architecture

Two paths, with different jobs.

### The live conversation path

```
caller → Twilio Media Streams (WebSocket)
       → local webrtcvad          barge-in detection, 20ms frames
       → Deepgram Flux v2         STT + semantic end-of-turn
       → OpenAI GPT               conversation + 12 tool definitions
       → Cartesia sonic-3         streaming mu-law straight back to Twilio
```

Every stage is a socket this codebase owns, which is what makes per-stage timing
possible at all.

**Turn-taking is two independent signals, deliberately.** The end of a caller's
turn comes only from Deepgram Flux's semantic `EndOfTurn` — silence alone never
triggers the model. Barge-in comes from local `webrtcvad`, and is armed only
once the agent's first audio chunk actually reaches the caller, so the model's
thinking time cannot be interrupted by a cough.

**The conversational model is OpenAI, by measurement.** Under the payload
actually shipped — a ~9,500-token prompt with 12 tool definitions — it reached
first token in 1,040ms against 2,810ms for the alternative. On a bare "hello"
the ranking reverses, which is exactly why the benchmark that matters is the
real payload.

### The reasoning path (Google ADK + Gemini)

A separate multi-agent graph built with **Google's Agent Development Kit** on
**Gemini 2.5 Flash** via Vertex AI (ADC, no API keys): an `OvelaManager` routing
to a `BookingWorker` (availability, holds, Stripe pricing, confirmation emails)
and an `InfoWorker` (policies, amenities, grounded search). Graph state persists
to Appwrite through a custom `AppwriteSessionService`, so a restart mid-call
does not lose context.

---

## How the latency was found

Each stage of a voice turn is wrapped in a Sentry span, so a turn arrives as a
waterfall rather than a single number. That is what located the bottleneck: one
span holding a median **84%** of turn time across 25 turns, which no amount of
reading the code had revealed.

Two of the spans were themselves broken and are fixed in PR3 — one measured a
zero-width interval, and the one that mattered had no internal detail. With the
model wait and tool execution now timed separately, a tool-calling turn shows
something that had been assumed backwards: the model answers in ~340ms while a
single booking lookup cost up to 1,571ms. The database was the bottleneck, not
the model.

### AI-assisted diagnosis

[`backend/scripts/analyze_trace.py`](backend/scripts/analyze_trace.py) pulls the
voice-turn spans from Sentry and has **Gemini 2.5 Flash** return a structured
diagnosis — bottleneck, its share, ranked causes, and remediations with expected
saving and risk.

It runs on its own. A completed call is the only reliable signal that fresh
spans exist, so the Twilio status webhook schedules an analysis two minutes
later and diffs each stage's median against the previous run, raising a Sentry
message when something regresses beyond 40%. That threshold comes from
measurement, not taste: a tighter bound reports the model's own variance as a
regression.

Its record, stated plainly: on the runs so far it has named the dominant span
correctly on data it had not seen, and once flagged a tool I had not examined.
It has not yet found a root cause I did not already have. It reads telemetry in seconds
instead of a day, and it cannot see anything that is not instrumented — which is
precisely why fixing the spans sharpened its answers.

---

## Reliability testing

The agent is exercised against adversarial scenarios spanning three difficulty
levels — happy path, mid-conversation interruptions, then race conditions,
privacy-boundary violations and backend failure recovery — with an independent
LLM judge scoring each against a fixed rubric.

| Artifact | What it does |
|---|---|
| [`run_multi_agent_evaluation.py`](backend/tests/run_multi_agent_evaluation.py) | 14-scenario harness over the full ADK routing graph on Gemini 2.5 Flash |
| [`asr_noise_simulator.py`](backend/tests/asr_noise_simulator.py) | Deterministic speech-recognition noise (light/medium/heavy): phonetic swaps, fillers, distortion |
| [`EVALUATION_METHODOLOGY.md`](docs/EVALUATION_METHODOLOGY.md) | Rubric, sandbox waivers, scenario matrix |

**A caveat this project learned the hard way:** mocked tests at a provider
boundary test your assumption, not the provider's contract. Three tests in this
repository passed while certifying real bugs. Anything touching Deepgram,
Cartesia or Twilio is now proven on a live call.

---

## Running it

**Prerequisites:** Python 3.12, Node 18+, a Google Cloud project with Vertex AI
enabled, an Appwrite project, and keys for Twilio, Deepgram, Cartesia, OpenAI
and Stripe.

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install && npm run dev
```

The backend refuses to start without `OPENAI_API_KEY`, `APPWRITE_PROJECT_ID`,
`APPWRITE_API_KEY`, `SMTP_PASSWORD` and `DEEPGRAM_API_KEY`. Google Cloud uses
Application Default Credentials — no key in the environment. The backend is
deployed to Heroku.

```bash
cd backend && pytest
```

---

## Security & privacy

- **Keyless Google Cloud auth** via Application Default Credentials.
- **Guest data stays in memory** during a live negotiation and is written to the
  database only on explicit verbal confirmation.
- **A Sentry DSN appears in this branch's early history** (before the work
  described above). It has been rotated and is dead; a secret scanner will
  still flag it.
- **Rate limiting** anchored to AEST — 2 calls per 24h per caller, 10 per hour
  globally — to prevent toll fraud and token drain. The numbers exempt from it
  live in the environment, not in this repository.

---

<div align="center">
  </div>
