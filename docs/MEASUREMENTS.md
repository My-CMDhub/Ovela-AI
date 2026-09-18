# Measurements

What Ovela's latency actually is, how it was read, and — just as important —
which numbers must not be quoted and why.

Every figure here came from one paginated read of Sentry spans on
**2026-09-16** over `--period 30d`, using the fixed trace reader in
`backend/scripts/analyze_trace.py`. Sample sizes are given everywhere because
most of them are small. **All calls are the author's own test calls** — Ovela
has no customers.

Reproduce from `backend/` with the venv active:

```bash
python -m scripts.analyze_trace --period 30d --by-day --by-kind --no-gemini
```

Read the `WINDOW` line it prints, not the `--period` label. See
[How these were read](#how-these-were-read) for why that matters.

---

## Plain turns — inside budget since August

Caller stops speaking → first audio byte, one LLM round, no tool call.

| day | release | p50 | n |
|---|---|---|---|
| 18 Aug | v417 | 706 ms | 12 |
| 19 Aug | v417 | 608 ms | 29 |
| 21 Aug | v417 | 886 ms | 6 |
| 31 Aug | v419/v420 | 670 ms | 13 |
| 1 Sep | v420 | 602 ms | 20 |
| 3 Sep | v421 | 597 ms | 51 |
| 4 Sep | v423 | 551 ms | 25 |
| 16 Sep | v424 | 922 ms | 8 |
| 16 Sep | v425 | 521 ms | 11 |

On the six days with n ≥ 12 the p50 is **551–706 ms**. The two days with n < 10
read 886 and 922 ms — small samples, not a trend.

## Tool turns — never inside budget

A turn that calls a tool costs a second LLM round plus the tool itself.

| day | p50 | n |
|---|---|---|
| 18 Aug | 2172 ms | 3 |
| 19 Aug | 2195 ms | 22 |
| 31 Aug | 1527 ms | 10 |
| 1 Sep | 1735 ms | 4 |
| 3 Sep | 1723 ms | 13 |
| 4 Sep | 2661 ms | 2 |
| 16 Sep | 1696 ms | 3 |

**1.5–2.7 s on every day with more than one sample.** (21 Aug has a single tool
turn at 844 ms — one sample, not a counter-example.) This is where the
remaining latency is: the model is not the problem, the tool round trip is.

## Before and after, split by kind

Comparing 18–21 Aug (v417) with 3–4 Sep (v421/v423):

| | before | after | change | n |
|---|---|---|---|---|
| Plain turn p50 | 647 ms | 594 ms | −8% | 47 → 76 |
| Tool turn p50 | 2180 ms | 1777 ms | −18% | 26 → 15 |
| Speech end → first token, plain | 503 ms | 447 ms | | same traces |
| Speech end → first token, tool | 1968 ms | 1653 ms | | same traces |

**The split matters.** Pooling plain and tool turns once produced a "−27% faster"
headline that was mostly arithmetic: the August sample was 36% tool turns
(26 of 73) and the September one 16% (15 of 91). That figure is withdrawn.

## Where the win came from — and it was not the model

LLM first-token p50 barely moved: 468 ms (3 Sep) → 437 ms (4 Sep) → 420 ms
(16 Sep). The measured gain is a per-call reservation cache:

| | before | after | n |
|---|---|---|---|
| `lookup_booking`, repeat within a call | **1073 ms** (19 Aug) | **0.4 ms** (31 Aug onward) | 15 → 21 across four days |

The first lookup of a call still costs up to 897 ms; every repeat is free.

## Components, v424, 16 Sep (n = 11)

| span | p50 |
|---|---|
| LLM round 1: request → first token | 420 ms |
| Span 1: speech end → first token | 950 ms |
| Span 3: first token → first audio | 240 ms |
| whole turn | 1189 ms |

## Open question: `check_availability`

488–511 ms on 18–19 Aug (n = 4), then 1844 ms (3 Sep, n = 1) and 1708 ms
(16 Sep, n = 1, plus one cache hit at 1.03 ms). The likely explanation is not a
regression: the `motel_rooms` table was **empty** until it was seeded on
31 Aug, so August's ~506 ms was the cost of checking nothing. If so, ~1.7 s is
the true cost of the real query and it owns the tool turn. **n = 2 — not yet
quotable.**

## Turn-taking, v425 (call 2, 16 Sep)

Barge-in now survives a long answer: interruptions landed **6.5, 5.3, 4.9, 4.8,
4.3 and 3.9 s** into a reply. The previous release stopped listening 3–4 s in.

---

## Do not quote

- **Any v425 figure as current.** A turn-taking fault was live in it: the
  Deepgram socket went unread for the whole previous reply, so the pipeline
  was timed from when it *noticed* the caller, not from when they stopped
  speaking. Three times on call 2 the caller waited **~6.0 s** — invisible in
  every latency number above. The fix is written and reviewed but **not yet
  deployed**; the first release where measured and perceived latency are the
  same thing has no data yet.
- **5 September.** 130 turns and every one unusable: Span 3 reports **1 ms**,
  which is not a synthesis time, and not one tool span exists across all 130.
  Whole-turn p50 reads 1593 ms and LLM round 1 reads 1586 ms — flat across 10
  separate sessions and 68 minutes (p50 per quarter 1587 / 1595 / 1537 /
  1576 ms), so it is neither warm-up nor drift. **Cause not established.**
  Those 130 turns are more than half the fortnight's sample, so any
  period-wide median is really a median of that one day.
- **[`benchmarks/trace_analysis.json`](../benchmarks/trace_analysis.json)** and
  the figures in the Bug Smash write-ups — 538.89 / 506.18 / 407.65 / 268.72 /
  2018.7 ms. Those are **single traces**, not medians, and the file's
  `span_count` of exactly 100 is the old pagination cap, so its "2h" label was
  never verified. It is kept exactly as it was because published posts link it.
- **Anything from `scripts/probe_*` run on a laptop.** Those include
  residential round-trip time and are not product figures.
- **The 92.8/100 harness score** from the Google-hackathon evaluation. It was
  measured on 2026-08-15, predates every change since, and scored a different
  conversational driver. See
  [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md) for what it measured.

---

## How these were read

`analyze_trace.py` used to request 100 rows sorted newest-first and read **one
page**, so `--period 14d` meant "the newest 100 turns" — once a 7-minute window,
reported as two weeks, which read as a 3× regression that had not happened.
It now:

- pages until the period is exhausted and prints the **window it actually
  read** above every table;
- reports Sentry's `meta.dataScanned: "partial"` — a long query that hits
  Sentry's scan budget returns a *sample* and then claims there are no more
  pages (200 rows for 90 days against 1530 for 30 days over the same calls),
  so a row count is only a turn count when the scan was full;
- flags any stage whose p50 is under 10 ms as instrumentation, not work;
- splits turns by day (`--by-day`) and by kind (`--by-kind`), because a
  period median mixes releases and pooling plain with tool turns manufactures
  improvements.

Pinned by `backend/tests/test_analyze_trace.py`.
