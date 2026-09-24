<div align="center">
  <img src="images/banner.png" alt="Ovela" width="100%" />

  <br />

  **A voice receptionist on a real phone line, built for the parts of a phone call that usually go wrong.**

  <br />

  [![Stack](https://img.shields.io/badge/stack-Python%20·%20FastAPI%20·%20asyncio-3776AB?style=flat-square)](#architecture)
  [![Voice](https://img.shields.io/badge/voice-Twilio%20·%20Deepgram%20Flux%20·%20Cartesia-6b46c1?style=flat-square)](#architecture)
  [![LLM](https://img.shields.io/badge/LLM-gpt-10a37f?style=flat-square)](#decisions-that-make-it-different)
  [![Reply](https://img.shields.io/badge/reply%20(no%20tool)-0.76--0.91%20s%20·%202%20calls-success?style=flat-square)](#measurements)
  [![Tests](https://img.shields.io/badge/tests-1%2C934%20passing-success?style=flat-square)](#running-it)
  [![Status](https://img.shields.io/badge/status-personal%20project-lightgrey?style=flat-square)](#why-this-exists)
</div>

<br />

## Why this exists

There are hundreds of voice-agent demos online, and nearly all of them show the
happy path: the caller asks, the agent answers, everyone waits their turn. Real
calls aren't like that. People talk over you, say "mhmm" while you're
mid-sentence, spell their name because they know you'll mishear it, say "yes" to
the wrong question, and expect you to remember at minute six what they told you
at minute one.

A good receptionist handles all of that without thinking. Ovela is my attempt to
turn those human habits — taking turns, being interrupted, remembering what was
settled, asking before acting — into a system reliable enough to trust. It is
built and measured around the failure modes, not the demo.

It is a personal engineering project running on a real phone line. It is not a
business and has no customers: every call behind the numbers below is one of my
own test calls, Stripe runs in test mode, and no third-party booking system is
connected — the demo motel runs on its own booking store.

## Architecture

A cascaded pipeline: speech-to-text, the language model and text-to-speech are
separate streaming providers, and a Python orchestrator owns the conversation —
when a turn ends, when the caller has taken the floor, what the call has
established, and what the agent is allowed to do.

```mermaid
flowchart LR
    classDef caller fill:#6b46c1,stroke:#4c1d95,stroke-width:2px,color:#fff
    classDef voice fill:#1f2937,stroke:#60a5fa,stroke-width:2px,color:#fff
    classDef core fill:#1f2937,stroke:#10b981,stroke-width:2px,color:#fff
    classDef gate fill:#7c2d12,stroke:#f59e0b,stroke-width:2px,color:#fff
    classDef store fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff

    C((Caller)):::caller <-->|phone network| T[Twilio Media Streams]:::voice
    T <-->|8 kHz audio| O[Orchestrator<br/>FastAPI · asyncio]:::core

    subgraph LISTEN [Listening]
        V[webrtcvad<br/>barge-in, 20 ms frames]:::voice
        D[Deepgram Flux<br/>transcript + end of turn]:::voice
    end

    subgraph THINK [One turn at a time]
        Q[(turn queue)]:::store
        W[turn worker]:::core
        S[Call state<br/>settled · heard · perishable]:::store
        L[gpt]:::core
        G{Code gates}:::gate
    end

    O --> V -->|caller took the floor| O
    O --> D -->|turn ended| Q --> W
    S -->|facts every turn| L
    W --> L -->|tool call| G --> X[Tools]:::core
    X --> A[(Appwrite)]:::store
    X --> P[Stripe · test mode]:::store
    X -->|results| S
    L -->|streamed text| K[Cartesia]:::voice -->|audio| O
```

| Layer | Technology | Job |
| --- | --- | --- |
| Telephony | Twilio Media Streams | Real number, two-way μ-law 8 kHz audio over WebSocket |
| Orchestrator | Python, FastAPI, asyncio on Heroku | Turn-taking, interruption, call state, tool gating, tracing |
| Speech-to-text | Deepgram Flux | Streaming transcript and semantic end-of-turn |
| Barge-in | webrtcvad (local) | Detects the caller speaking over the agent |
| Reasoning | OpenAI `gpt` | Replies and tool calls, streamed |
| Text-to-speech | Cartesia | Speech synthesis, starting on the first phrase |
| Data | Appwrite | Bookings, tenant configuration, call transcripts |
| Web | Next.js | Public site and staff dashboard |

Voice, speaking speed, model and turn-taking thresholds come from a per-tenant
configuration record, not from code.

## One call, turn by turn

1. **Before the caller speaks**, the booking attached to their number is fetched
   in the background — but only the fact that a reservation exists is shared. The
   guest's name stays out of the conversation.
2. **Deepgram Flux decides when the caller has finished.** Pauses and "um"s don't
   end a turn, and silence alone never triggers a reply.
3. **The finished turn goes onto a queue, and one worker answers it.** The next
   thing the caller says is read immediately, and two replies are never live at
   once.
4. **The model gets the recent transcript plus the call state** — what's settled,
   what was only heard, and what may have changed since.
5. **Four actions are gated in code**: transferring to a person, creating a
   booking, writing a spelled name, and changing a reservation before the caller
   is identified. Read-only lookups are not gated.
6. **The reply streams to Cartesia phrase by phrase**, so the caller hears the
   first words while the rest is still being written. If the model goes
   straight to a tool, code says a short line first ("Let me have a look.") so
   the wait is never silent.
7. **If the caller talks over the agent**, audio stops, the part they heard is
   kept in the agent's memory, and the new question is answered. "Mhmm" and
   "go on" are recognised and the agent carries on.
8. **When the call ends**, the transcript is saved with its barge-ins,
   backchannels, tools called, gate refusals, and any number the agent said that
   no tool supplied.

## Decisions that make it different

**Agreeing to one thing isn't agreeing to everything.**
The booking tool used to trust a flag the model filled in to say the summary had
been read back. In 4 of 7 booking attempts it claimed a confirmation the caller
never gave — in one, a "yes" to an email spelling became a booked room. The gate
now reads the transcript: a name, a price and dates spoken by the agent, followed
by the caller agreeing to *that*. Transfers to a person work the same way and need
the caller to ask for one or accept the offer.

**A receptionist doesn't read out someone's details before knowing who's calling.**
With the guest's name in the prompt behind a "do not reveal" rule, the agent
volunteered it on the first turn in **4 of 5** replays. Now the lookup tool
withholds it and code releases it only after identity is confirmed: **0 of 5**.
Anything that could cost data, money or a promise is enforced this way; tone and
phrasing stay in the prompt and are measured as rates over repeated runs.

**When someone spells their name, the letters win.**
Speech recognition transcribed "s i o b h a n" perfectly, and the booking was
still written as "Cyborn". Spelled letters are now captured from the caller's own
words, and any booking or update that doesn't contain them is refused.

**Being unsure is better than guessing.**
Name matching answers only when one guest is clearly ahead of every other. If two
guests both fit — Katherine Smyth and Catherine Smith — it declines and asks for
a phone number, reference or email, even when one of them matches exactly.

**Remember what was settled, and know the difference between knowing and hearing.**
Tool results leave the model's context after each turn, so a long call used to
forget a booking reference it had looked up on turn 2. The orchestrator now keeps
the facts itself in three labelled tiers, re-sent every turn: *settled* (a tool
confirmed it), *heard* (the caller said it, nothing has checked it) and
*perishable* (availability, re-checked before any promise).

**The question isn't "can the agent stop talking?" — it's "what did the caller actually hear?"**
Text is generated faster than it is spoken, so when a caller cuts in, the model
has already "said" words the caller never heard. Ovela keeps only the part that
played — estimated from audio Twilio confirms it delivered, trimmed to the last
full sentence — so the agent doesn't assume context the caller never received.
And "mhmm" isn't an interruption: cutting in takes about half a second of
sustained speech or words that aren't continuers.

**A receptionist picks up the phone already ready to talk.**
The first reply of every call was the slowest — 3.7 s — because the caller's
first question paid for a cold connection to the model and an extra lookup the
agent didn't need. Now the orchestrator sends that first request once while the
greeting plays and throws the answer away, the agent asks who's calling before
looking anything up, and whenever it does reach for a tool, code says a short
line first so the wait is never silence. First reply: **3.7 s → 0.9 s**, one
call each side.

**Models are compared on the real workload, and re-measured.**
Speed is benchmarked under the production prompt (~8,900 tokens, 12 tools) from
the server's own region, never on a bare "hello"
([`bench_llm.py`](backend/scripts/bench_llm.py)). Re-run in September 2026,
`gpt` and `gpt` both reach a first token in about **0.5 s**, so
speed no longer separates them; `gpt` stays on cost, and a switch would
need a scored behaviour eval rather than a latency number.

## What works today

- Answers questions about rooms, rates, availability and the property.
- Finds a caller's booking from their number, a reference, their email, their
  name, or a name spelled letter by letter.
- Takes a booking request after reading it back and hearing agreement, then
  creates a payment link (Stripe test mode).
- Transfers to a person only with the caller's consent.
- Resolves relative dates — "this weekend" and "next weekend" are different
  weekends.
- Staff dashboard for reservations, call logs and guests.

## Measurements

Measured on my own test calls over the phone network, August–September 2026,
from the call traces. Updated after significant changes, not continuously.

| Measure | Result | Sample |
| --- | --- | --- |
| First reply of a call: turn end detected → first audio sent | **3.7 s → 0.9 s** | one call before, one after the greeting warm-up (18 Sep) |
| Replies with no tool, median per call | **0.76 s** and **0.91 s** | last two calls, 20 and 14 turns |
| First words when a tool runs | **2.3–4.3 s → 0.7–0.8 s** | 4 tool turns before, 2 after the in-code acknowledgement |
| Full answer when a tool runs: turn end → answer starts generating | **1.5–4.0 s** (median 3.2 s) **→ 1.1–1.7 s** | 5 tool turns before, 2 after; from the call logs |
| Repeat booking lookup within a call | **1,073 ms → 0.4 ms** (per-call cache) | 15 → 21 lookups |
| Finding a guest from misheard details | **24 of 28** real guests found; **0** of 8 non-guests invented; **0** wrong guest | 36 transcription-style queries ([`eval_identity.py`](backend/scripts/eval_identity.py)) |
| Guest name volunteered before identification | **4 of 5 → 0 of 5** | scripted replays ([`replay_conversation.py`](backend/scripts/replay_conversation.py)) |
| Interrupting a long reply | caught up to **6.5 s** into an answer | 6 interruptions |
| Automated tests | **1,934** passing | tracked backend suite |

Reply time starts when Deepgram reports the end of turn, so it excludes
Deepgram's own end-of-turn decision. Replies without a tool are under a second.
When a tool runs, the caller now hears a short acknowledgement in under a
second; the answer itself still waits on the tool and a second model round,
speech synthesis adds about 0.2 s to it, and it plays once the acknowledgement
has finished. Every before/after row here is one call each side of the change —
directionally clear, not yet a large sample.

## Known limits

- **Not yet:** <!-- not-yet -->under a second from the caller's last word · 1.5–1.7 s<!-- /not-yet -->
  on real calls, measured from the two-channel call recordings, not the logs. Deepgram's
  end-of-turn decision and the audio's round trip between Australia and the US
  server take about 0.8 s before the model starts, so a faster model alone
  cannot close it. (dhruvpatel.net shows this line.)
- **Identity is confirmed on one matching word of the name.** A relative on the
  same phone who shares the surname passes.
- **The gates judge agreement from word patterns in the transcript**, not full
  understanding, so an unusual way of saying yes can be refused.
- **Reply time is measured to audio sent**, and excludes Deepgram's own
  end-of-turn decision.
- **One tenant, and every call is my own** — nothing here has met a real
  customer yet.

## Try it

**[ovela.dev](https://ovela.dev)** — the demo opens from the landing page.

## Running it

Backend (Python 3.12), from `backend/`:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
pytest
```

Needs `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`,
`APPWRITE_PROJECT_ID`, `APPWRITE_API_KEY` and `SMTP_PASSWORD` in `backend/.env`,
plus Twilio credentials for real calls.

Frontend (Node 20+), from `frontend/`:

```bash
npm install
npm run dev
```

---

<p align="center"><i>Ovela is not a finished answer to human conversation. It’s an ongoing attempt to understand it—one call, one interaction, and one lesson at a time. ✧</i></p>
