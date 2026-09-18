# Sentry and Twilio evidence

Screenshots referenced by the write-ups, captured from the live Heroku
deployment after calls placed over the phone network. **Every call shown is a
test call made by the author** — Ovela has no customers. Dates are the capture
dates; the system has changed since, so read these as the history of a fix, not
as current performance. Current numbers, with sample sizes, are in
[`docs/MEASUREMENTS.md`](../docs/MEASUREMENTS.md).

| file | what it shows | read it as |
|---|---|---|
| `01-trace-waterfall.png` | One voice turn on 19 Aug (trace `660c2ea6`): whole turn 2.02 s — LLM round 1 538.89 ms, `check_availability` 506.18 ms, LLM round 2 407.65 ms, first token → first audio 268.72 ms. | **A single trace, not a median**, and a *tool* turn. The 506 ms availability check ran against an empty rooms table. |
| `02-conversation.png` | Sentry's agent view of a test call: a booking lookup under a misheard name ("Drew Patel") fails repeatedly and the agent offers a transfer after every miss. | The failure that led to spelled-name identity and to gating transfers in code. |
| `03-issue-attributes-typeerror.png` | A Sentry issue: `Span.__init__() got an unexpected keyword argument 'attributes'`, raised on the live `/api/voice/stream` path. | An SDK API mismatch that broke reply generation — the kind of bug that succeeds in tests and fails on a call. |
| `04-before-fat-span.png` | A 5.52 s turn before instrumentation was split: Span 1 is one opaque 5.29 s block and Span 2 reads 0.01 ms. | Why the spans were rebuilt: Span 2 was opened and closed on the same line, and a single fat span says nothing about where the time went. |
| `05-cache-tokens.png` | A `gen_ai.chat` span: 178 input + 8.9K cached tokens. The visible system prompt names Coal Creek Motel. | Evidence the prompt cache hits. The motel is a real business whose public details were used to make the demo realistic; it is not a customer. |
| `06-twilio-566s.png` | Twilio's call log: one call lasting 9 min 26 s (566 s). Caller number redacted. | The agent said goodbye and never hung up: the hang-up action was returned by the tool and nothing acted on it. |
| `07-sentry-gap.png` | Sentry span samples: individual turn durations from 517 ms to 3.60 s within minutes of each other. | The spread a single median hides — why measurements here are reported per day, per turn kind, with n. |
